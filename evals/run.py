"""Run eval scenarios against the engine and write transcripts, scores and a report.

    uv run python -m evals.run                          # all scenarios
    uv run python -m evals.run --suite smoke            # 5 quick regression scenarios
    uv run python -m evals.run --only 13_expired_license_bilbao
    uv run python -m evals.run --name haiku --fast-model claude-haiku-5-5
    uv run python -m evals.run --fake                   # offline: no API key, no cost

Writes evals/runs/<timestamp>/ (per scenario: JSON and Markdown transcript; scores.json;
report.md). With --name, the report also goes to evals/reports/<name>.md with its
transcripts in evals/reports/<name>/, so it can be committed.
"""

import argparse
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from pydantic_core import to_json

from evals.fake import FactsCandidate
from evals.scenario import Scenario, load_all
from evals.scoring import ScenarioScore, score, summarize
from evals.simulator import Candidate, Persona, simulate
from evals.transcripts import report_md, transcript_md
from screening.cli import fake_llm
from screening.config import ScreeningConfig, load_config
from screening.engine import EngineContext
from screening.llm import AnthropicClient, LLMClient

EVALS_DIR = Path(__file__).parent
SIM_MODEL = "claude-sonnet-5-5"  # the simulated candidate: smart tier, fixed across configs
SUITES = {
    # One per risk area: ES and EN happy paths, a knockout, the review path, timers.
    "smoke": [
        "01_es_happy_madrid",
        "03_en_happy_valencia",
        "10_no_license_puebla",
        "13_expired_license_bilbao",
        "16_silence_late_reply_barcelona",
    ],
}


class Settings(BaseModel):
    fake: bool
    fast_model: str | None
    smart_model: str | None
    sim_model: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.run", description=__doc__.split("\n")[0])
    parser.add_argument("--suite", choices=["full", *SUITES], default="full")
    parser.add_argument("--only", nargs="+", metavar="ID", help="scenario ids (overrides --suite)")
    parser.add_argument("--name", help="report name: writes evals/reports/<name>.md")
    parser.add_argument("--fast-model", help="engine fast tier (extract, compose)")
    parser.add_argument("--smart-model", help="engine smart tier (summary)")
    parser.add_argument("--sim-model", default=SIM_MODEL, help="simulated candidate's model")
    parser.add_argument("--workers", type=int, default=4, help="scenarios run in parallel")
    parser.add_argument("--fake", action="store_true", help="offline: keyword stub + facts")
    args = parser.parse_args(argv)

    config = load_config()
    if config.time_scale != 1:
        # The fake clock already skips waiting; scaled timings would break the timer checks.
        parser.error("unset DEMO_TIME_SCALE: evals run real timings on a fake clock")
    settings = Settings(
        fake=args.fake,
        fast_model=args.fast_model,
        smart_model=args.smart_model,
        sim_model=args.sim_model,
    )
    scenarios = _select(args.suite, args.only)
    models = (
        {"engine": "fake keyword stub", "candidate": "facts"}
        if args.fake
        else {
            **AnthropicClient(fast_model=args.fast_model, smart_model=args.smart_model).models,
            "candidate": args.sim_model,
        }  # fmt: skip
    )
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = EVALS_DIR / "runs" / (f"{stamp}-{args.name}" if args.name else stamp)
    run_dir.mkdir(parents=True)
    print(f"{len(scenarios)} scenarios → {run_dir.relative_to(EVALS_DIR.parent)}")

    def one(scenario: Scenario) -> ScenarioScore | None:
        try:
            return _run_one(scenario, config, settings, run_dir)
        except Exception:  # a harness bug in one scenario must not lose the whole paid run
            (run_dir / f"{scenario.id}.error.txt").write_text(traceback.format_exc())
            print(f"  {scenario.id}: CRASHED, see {scenario.id}.error.txt", file=sys.stderr)
            return None

    workers = 1 if args.fake else max(1, args.workers)  # FakeLLM keeps per-call state
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, scenarios))
    scores = [s for s in results if s is not None]
    crashed = [sc.id for sc, s in zip(scenarios, results, strict=True) if s is None]
    if not scores:
        return 1

    summary = summarize(scores)
    (run_dir / "scores.json").write_text(
        _dump({"models": models, "summary": summary, "scores": scores, "crashed": crashed})
    )
    title = f"Eval report: {args.name}" if args.name else f"Eval run {stamp}"
    report = report_md(title, models, summary, scores, links=".", crashed=crashed)
    (run_dir / "report.md").write_text(report)
    if args.name:
        published = EVALS_DIR / "reports" / args.name
        shutil.rmtree(published, ignore_errors=True)
        published.mkdir(parents=True)
        for path in run_dir.glob("*.md"):
            if path.name != "report.md":
                shutil.copy(path, published / path.name)
        named = report_md(title, models, summary, scores, links=args.name, crashed=crashed)
        (EVALS_DIR / "reports" / f"{args.name}.md").write_text(named)
    print(
        f"passed {summary.passed}/{summary.scenarios} · outcome {summary.outcome:.0%} · "
        f"fields {summary.fields:.0%} · ${summary.cost_mean_usd:.4f}/conversation · "
        f"p50 {summary.latency_p50_ms} ms"
        + (f" · crashed: {', '.join(crashed)}" if crashed else "")
    )
    # Non-zero when anything failed, so a smoke run can gate a prompt change.
    return 0 if summary.passed == summary.scenarios and not crashed else 1


def _run_one(
    scenario: Scenario, config: ScreeningConfig, settings: Settings, run_dir: Path
) -> ScenarioScore:
    engine_llm: LLMClient
    candidate: Candidate
    if settings.fake:
        engine_llm, candidate = fake_llm(), FactsCandidate(scenario)
    else:
        engine_llm = AnthropicClient(
            fast_model=settings.fast_model, smart_model=settings.smart_model
        )
        candidate = Persona(scenario, AnthropicClient(smart_model=settings.sim_model))
    run = simulate(scenario, EngineContext(config=config, llm=engine_llm), candidate)
    result = score(scenario, run, config)
    zone = config.timezone_for(scenario.country)
    (run_dir / f"{scenario.id}.json").write_text(_dump({"run": run, "score": result}))
    (run_dir / f"{scenario.id}.md").write_text(transcript_md(scenario, run, result, zone))
    if run.error:
        # The simulated candidate's own API call failed (rate limit, credits): the engine
        # wasn't tested, so this is a crash, kept out of the scores, not an engine failure.
        raise RuntimeError(run.error)
    print(f"  {scenario.id}: {'PASS' if result.passed else 'FAIL'} ({result.status})")
    return result


def _select(suite: str, only: list[str] | None) -> list[Scenario]:
    scenarios = load_all()
    wanted = only or SUITES.get(suite)
    if wanted is None:
        return scenarios
    by_id = {s.id: s for s in scenarios}
    missing = [i for i in wanted if i not in by_id]
    if missing:
        raise SystemExit(f"unknown scenario ids: {', '.join(missing)}")
    return [by_id[i] for i in wanted]


def _dump(data: dict) -> str:
    return to_json(data, indent=2).decode() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
