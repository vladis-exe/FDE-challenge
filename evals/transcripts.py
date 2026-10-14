"""Markdown views of a run: one transcript per scenario, and the run report."""

import json
from zoneinfo import ZoneInfo

from evals.scenario import Scenario
from evals.scoring import DEFINITIONS, ScenarioScore, Summary
from evals.simulator import SimResult

MEDIA_LABEL = {"audio": "🎤 voice note", "image": "🖼 image", "sticker": "sticker", "other": "file"}


def transcript_md(scenario: Scenario, run: SimResult, score: ScenarioScore, zone: str) -> str:
    tz = ZoneInfo(zone)
    verdict = "PASS" if score.passed else "FAIL"
    out = [
        f"# {scenario.id}: {scenario.title}",
        "",
        f"**{verdict}** · expected `{score.expected_status}`, got `{score.status}` · "
        f"{score.turns} candidate messages · {score.duration_min} min · ${score.cost_usd:.4f}",
        "",
    ]
    if score.field_errors or not all(c.passed for c in score.checks) or score.error:
        out += [f"- {e}" for e in score.field_errors]
        out += [f"- check `{c.name}` failed: {c.detail}" for c in score.checks if not c.passed]
        out += [f"- error: {score.error}"] if score.error else []
        out.append("")
    out += conversation_md(run, tz)
    out += ["## Final record", "", "```json", _json(run.record), "```", ""]
    return "\n".join(out)


def conversation_md(run: SimResult, tz: ZoneInfo) -> list[str]:
    """The messages as Markdown lines: the candidate quoted, Alex plain, a heading per day."""
    out: list[str] = []
    day = None
    for line in run.lines:
        local = line.at.astimezone(tz)
        if local.date() != day:
            day = local.date()
            out += [f"*{local:%A %d %B %Y}*", ""]
        stamp = f"{local:%H:%M}"
        if line.role == "candidate":
            text = line.text or ""
            if line.media != "none":
                text = f"[{MEDIA_LABEL.get(line.media, line.media)}] {text}".strip()
            out.append(f"> **Candidate** · {stamp}  \n> {text}")
        else:
            tags = [] if line.kind == "reply" else [line.kind]
            if line.suppressed:
                tags.append("not delivered: a newer message was waiting")
            label = f" *({', '.join(tags)})*" if tags else ""
            out.append(f"**Alex** · {stamp}{label}  \n{line.text}")
        out.append("")
    return out


def report_md(
    title: str,
    models: dict[str, str],
    summary: Summary,
    scores: list[ScenarioScore],
    *,
    links: str,  # directory, relative to the report, that holds the transcripts
    crashed: list[str],
) -> str:
    pct = _pct
    out = [
        f"# {title}",
        "",
        "Models: " + ", ".join(f"{tier} = `{model}`" for tier, model in models.items()),
        "",
        "## Summary",
        "",
        "| Metric | Value | What it means |",
        "| --- | --- | --- |",
        f"| Scenarios passed | {summary.passed}/{summary.scenarios} | {DEFINITIONS['passed']} |",
        f"| Outcome accuracy | {pct(summary.outcome)} | {DEFINITIONS['outcome']} |",
        f"| Knockout correctness | {pct(summary.knockout)} | {DEFINITIONS['knockout']} |",
        f"| Field accuracy | {pct(summary.fields)} | {DEFINITIONS['fields']} |",
        f"| Message rules | {pct(summary.rules)} | {DEFINITIONS['rules']} |",
        f"| Language match | {pct(summary.language)} | {DEFINITIONS['language']} |",
        f"| AI disclosure | {pct(summary.disclosure)} | {DEFINITIONS['disclosure']} |",
        f"| Guard retries | {pct(summary.retries)} | {DEFINITIONS['retries']} |",
        f"| Turns (mean) | {summary.turns_mean:.1f} | {DEFINITIONS['turns']} |",
        f"| Cost per conversation | ${summary.cost_mean_usd:.4f} "
        f"(total ${summary.cost_total_usd:.3f}) | {DEFINITIONS['cost']} |",
        f"| Latency p50 / p95 | {_ms(summary.latency_p50_ms)} / {_ms(summary.latency_p95_ms)} "
        f"| {DEFINITIONS['latency']} |",
        "",
        "## Per scenario",
        "",
        "| Scenario | Result | Expected → got | Fields | Rules | Lang | Checks | Turns "
        "| Cost | p50 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s in scores:
        checks = f"{sum(c.passed for c in s.checks)}/{len(s.checks)}" if s.checks else "–"
        p50 = _ms(sorted(s.latency_ms)[len(s.latency_ms) // 2] if s.latency_ms else None)
        out.append(
            f"| [{s.scenario_id}]({links}/{s.scenario_id}.md) "
            f"| {'✅' if s.passed else '❌'} | {s.expected_status} → {s.status} "
            f"| {pct(s.fields)} | {pct(s.rules)} | {pct(s.language)} | {checks} | {s.turns} "
            f"| ${s.cost_usd:.4f} | {p50} |"
        )
    failures = [s for s in scores if not s.passed]
    if failures:
        out += ["", "## Why scenarios failed", ""]
        for s in failures:
            reasons = s.field_errors + [
                f"check {c.name}: {c.detail}" for c in s.checks if not c.passed
            ]
            if not s.outcome:
                reasons.insert(0, f"outcome: expected {s.expected_status}, got {s.status}")
            if s.hit_max_turns:
                reasons.append("hit the turn limit while still in progress")
            if s.error:
                reasons.append(s.error)
            out.append(f"- **{s.scenario_id}**: " + "; ".join(reasons))
    violations = [(s.scenario_id, v) for s in scores for v in s.rule_violations]
    if violations:
        out += ["", "## Message-rule violations", ""]
        out += [f"- {sid}: {v}" for sid, v in violations]
    if crashed:
        out += ["", f"Crashed (harness error, not scored): {', '.join(crashed)}"]
    unpriced = sorted({m for s in scores for m in s.unpriced_models})
    if unpriced:
        out += ["", f"Not priced (cost counted as 0): {', '.join(unpriced)}"]
    return "\n".join(out) + "\n"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def _ms(value: int | None) -> str:
    return "–" if value is None else f"{value / 1000:.1f} s"


def _json(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2)
