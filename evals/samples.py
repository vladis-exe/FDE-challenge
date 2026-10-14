"""Render the curated sample conversations (V5) from an eval run.

    uv run python -m evals.samples evals/runs/<run dir>

Which scenarios to show, and what to point out in each, live in samples.yaml; the
conversations themselves come straight from the run, unedited, so every sample is a real
engine transcript that can be regenerated.
"""

import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict

from evals.scenario import SCENARIOS_DIR, Scenario, load_scenario
from evals.simulator import SimResult
from evals.transcripts import conversation_md
from screening.config import load_config

SAMPLES_FILE = Path(__file__).parent / "samples.yaml"
OUT_DIR = Path(__file__).parent.parent / "docs" / "sample-conversations"


class Sample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    scenario: str
    title: str
    context: str  # who the candidate is and what makes the case hard
    notes: list[str]  # what to notice, in conversation order


def sample_md(sample: Sample, scenario: Scenario, run: SimResult, zone: str) -> str:
    channel = {"ES": "Spain", "MX": "Mexico"}[scenario.country]
    out = [
        f"# {sample.title}",
        "",
        f"*{channel} · outcome `{run.record['status']}` · {run.candidate_turns} candidate "
        f"messages · eval scenario `{scenario.id}`*",
        "",
        sample.context.strip(),
        "",
        "**What to notice**",
        "",
        *[f"- {note}" for note in sample.notes],
        "",
        "## Conversation",
        "",
        *conversation_md(run, ZoneInfo(zone)),
        "## What the recruiter gets",
        "",
    ]
    record = dict(run.record)
    summary = record.pop("summary", None)
    if summary:
        out += [f"> {summary}", ""]
    out += ["```json", json.dumps(record, ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(out)


def index_md(samples: list[Sample], run_dir: Path) -> str:
    out = [
        "# Sample conversations",
        "",
        "Real transcripts from the eval suite: a simulated candidate (Sonnet 5.5 playing a "
        "persona) against the production engine, unedited. Each opens with what makes the "
        "case hard and what to notice. Times are the candidate's local time on the eval's "
        "fake clock.",
        "",
        f"Source run: `{run_dir.name}`. Regenerate with "
        "`uv run python -m evals.samples <run dir>`.",
        "",
        "| Sample | Shows |",
        "| --- | --- |",
    ]
    out += [f"| [{s.title}]({s.file}) | {s.context.split('. ')[0].strip()}. |" for s in samples]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals.samples", description=__doc__.split("\n")[0])
    parser.add_argument("run_dir", type=Path, help="an evals/runs/<stamp> directory")
    args = parser.parse_args(argv)
    config = load_config()
    samples = [Sample(**item) for item in yaml.safe_load(SAMPLES_FILE.read_text())]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sample in samples:
        data = json.loads((args.run_dir / f"{sample.scenario}.json").read_text())
        run = SimResult.model_validate(data["run"])
        scenario = load_scenario(SCENARIOS_DIR / f"{sample.scenario}.yaml")
        zone = config.timezone_for(scenario.country)
        (OUT_DIR / sample.file).write_text(sample_md(sample, scenario, run, zone))
        print(f"  {sample.file}")
    (OUT_DIR / "README.md").write_text(index_md(samples, args.run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
