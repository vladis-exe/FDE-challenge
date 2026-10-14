"""Compare model configurations across repeated eval runs (V4).

    uv run python -m evals.compare \
        --config "haiku=evals/runs/<a>,evals/runs/<b>" \
        --config "sonnet=evals/runs/<c>,evals/runs/<d>"

Each run directory holds a scores.json from `evals.run`. Repeats of the same configuration
show how much a result moves between runs: a scenario that passes in one repeat and fails
in another is listed as unstable rather than counted as a win or a loss.
Prints a Markdown table; the decision write-up goes around it in evals/reports/.
"""

import argparse
import json
import statistics
from pathlib import Path

from pydantic import BaseModel

WEEKLY_APPLICATIONS = 1_000  # Grupo Sazón's volume from the brief


class ConfigResult(BaseModel):
    name: str
    models: dict[str, str]
    repeats: int
    pass_rates: list[float]
    outcome: float
    fields: float
    rules: float | None
    language: float | None
    retries: float | None
    cost_mean_usd: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    unstable: list[str]  # scenarios that passed in some repeats and failed in others
    always_failed: list[str]


def load(name: str, run_dirs: list[Path]) -> ConfigResult:
    runs = [json.loads((d / "scores.json").read_text()) for d in run_dirs]
    summaries = [r["summary"] for r in runs]
    outcomes: dict[str, list[bool]] = {}
    for r in runs:
        for s in r["scores"]:
            outcomes.setdefault(s["scenario_id"], []).append(s["passed"])

    def mean(key: str) -> float | None:
        values = [s[key] for s in summaries if s[key] is not None]
        return statistics.fmean(values) if values else None

    return ConfigResult(
        name=name,
        models=runs[0]["models"],
        repeats=len(runs),
        pass_rates=[s["passed"] / s["scenarios"] for s in summaries],
        outcome=mean("outcome") or 0.0,
        fields=mean("fields") or 0.0,
        rules=mean("rules"),
        language=mean("language"),
        retries=mean("retries"),
        cost_mean_usd=mean("cost_mean_usd") or 0.0,
        latency_p50_ms=mean("latency_p50_ms"),
        latency_p95_ms=mean("latency_p95_ms"),
        unstable=sorted(sid for sid, p in outcomes.items() if any(p) and not all(p)),
        always_failed=sorted(sid for sid, p in outcomes.items() if not any(p)),
    )


def table(results: list[ConfigResult]) -> str:
    def pct(value: float | None) -> str:
        return "–" if value is None else f"{value:.0%}"

    def sec(ms: float | None) -> str:
        return "–" if ms is None else f"{ms / 1000:.1f} s"

    out = [
        "| Config | Models | Pass rate (per repeat) | Outcome | Fields | Rules | Language "
        "| Guard retries | Cost / conversation | Cost / week* | Latency p50 / p95 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        models = ", ".join(f"{k}: `{v}`" for k, v in r.models.items() if k != "candidate")
        rates = " / ".join(pct(p) for p in r.pass_rates)
        out.append(
            f"| **{r.name}** | {models} | {pct(statistics.fmean(r.pass_rates))} ({rates}) "
            f"| {pct(r.outcome)} | {pct(r.fields)} | {pct(r.rules)} | {pct(r.language)} "
            f"| {pct(r.retries)} | ${r.cost_mean_usd:.4f} "
            f"| ${r.cost_mean_usd * WEEKLY_APPLICATIONS:.2f} "
            f"| {sec(r.latency_p50_ms)} / {sec(r.latency_p95_ms)} |"
        )
    out += [
        "",
        f"\\* {WEEKLY_APPLICATIONS:,} screenings a week, LLM cost only.",
        "",
        "| Config | Unstable across repeats | Failed in every repeat |",
        "| --- | --- | --- |",
    ]
    for r in results:
        unstable = ", ".join(r.unstable) or "none"
        out.append(f"| {r.name} | {unstable} | {', '.join(r.always_failed) or 'none'} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.compare", description=__doc__.split("\n")[0])
    parser.add_argument(
        "--config", action="append", required=True, metavar="NAME=DIR[,DIR...]",
        help="a configuration and its run directories (repeat the flag per configuration)",
    )  # fmt: skip
    args = parser.parse_args(argv)
    results = []
    for spec in args.config:
        name, _, dirs = spec.partition("=")
        results.append(load(name, [Path(d) for d in dirs.split(",") if d]))
    print(table(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
