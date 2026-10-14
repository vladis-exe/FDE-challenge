"""The eval harness, offline: the CLI's keyword stub as the engine LLM, facts as the candidate.

Timers are pure code, so the silence scenarios check reminders, quiet hours and
abandonment against the real engine here.
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from evals import run as run_module
from evals.fake import FactsCandidate
from evals.pricing import call_cost
from evals.scenario import SCENARIOS_DIR, load_scenario
from evals.scoring import _rules, _same, detect_language, score
from evals.simulator import Line, Persona, SimResult, as_chat, simulate
from screening.cli import fake_llm
from screening.config import load_config
from screening.engine import EngineContext
from screening.llm import FakeLLM

MADRID = ZoneInfo("Europe/Madrid")


@pytest.fixture
def config(monkeypatch):
    monkeypatch.delenv("DEMO_TIME_SCALE", raising=False)  # the fake clock needs real timings
    return load_config()


def offline(scenario_id: str, config) -> tuple[SimResult, object]:
    scenario = load_scenario(SCENARIOS_DIR / f"{scenario_id}.yaml")
    ctx = EngineContext(config=config, llm=fake_llm())
    result = simulate(scenario, ctx, FactsCandidate(scenario))
    return result, score(scenario, result, config)


def test_abandonment_with_a_deferred_last_reminder(config) -> None:
    run, scored = offline("20_abandoned_monterrey", config)
    assert run.state.status == "abandoned"
    assert scored.passed, scored
    assert {c.name: c.passed for c in scored.checks} == {
        "reminders_sent": True,
        "quiet_hours_respected": True,
        "no_messages_after_close": True,
    }


def test_night_silence_reminders_wait_for_morning(config) -> None:
    run, scored = offline("16_silence_late_reply_barcelona", config)
    reminders = [line.at.astimezone(MADRID) for line in run.lines if line.kind == "reminder"]
    assert [(r.day, r.hour) for r in reminders] == [(22, 20), (23, 9)]
    assert reminders[1].minute == 0  # deferred to the end of quiet hours
    assert all(c.passed for c in scored.checks)


def test_burst_delivers_only_the_last_reply(config) -> None:
    run, _ = offline("04_code_switch_monterrey", config)
    burst = [i for i, line in enumerate(run.lines) if line.text == "full time bro"]
    assert burst, "the scripted burst was not sent"
    replies_to_first = run.lines[burst[0] + 1]
    assert replies_to_first.role == "agent" and replies_to_first.suppressed
    assert not any(line.suppressed for line in run.lines if line.kind == "close")


def test_scripted_media_turn_and_surname_reask(config) -> None:
    run, scored = offline("09_voice_note_emoji_cdmx", config)
    assert run.lines[1].media == "audio" and run.lines[1].scripted
    assert {c.name: c.passed for c in scored.checks}["media_asks_for_text"]


def test_persona_sees_only_delivered_messages_and_gets_the_directive() -> None:
    scenario = load_scenario(SCENARIOS_DIR / "01_es_happy_madrid.yaml")
    at = datetime(2026, 10, 20, 11, 5, tzinfo=MADRID)
    lines = [
        Line(role="agent", at=at, text="¡Hola! ¿Empezamos?", kind="reply"),
        Line(role="candidate", at=at, text="si"),
        Line(role="candidate", at=at, text="vale"),
        Line(role="agent", at=at, text="stale question", kind="reply", suppressed=True),
        Line(role="agent", at=at, text="¿Cómo te llamas?", kind="reply"),
    ]
    assert as_chat(lines) == [
        {"role": "user", "content": "¡Hola! ¿Empezamos?"},
        {"role": "assistant", "content": "si\nvale"},
        {"role": "user", "content": "¿Cómo te llamas?"},
    ]
    llm = FakeLLM({"simulate": lambda system, messages: '"carlos mendez ruiz"'})
    persona = Persona(scenario, llm)
    reply = persona.reply(lines, "Include one realistic typo.", "name", at)
    assert reply == "carlos mendez ruiz"
    call = llm.calls_for("simulate")[0]
    assert "Carlos Méndez Ruiz" in call.system and "Vallecas" in call.system
    assert call.messages[-1]["content"].endswith(
        "[It is Tuesday 20 October 2026, 11:05 where you are. "
        "Director's note, this message only: Include one realistic typo.]"
    )


@pytest.mark.parametrize(
    ("text", "problems"),
    [
        ("¡Genial, Laura! ¿En qué ciudad y barrio vives?", ""),
        ("Vale. Perfecto. ¿Dónde vives?", "3 sentences"),
        ("¿Dónde vives? ¿Y desde cuándo?", "2 questions"),
        ("Hola 👋🎉 ¿seguimos?", "emojis"),
        ("**Genial** ¿dónde vives?", "formatting"),
        ("x" * 301, "301 chars"),
    ],
)
def test_message_rules(text: str, problems: str) -> None:
    assert _rules(text) == problems


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("tengo carnet desde hace años", "es"),
        ("yeah got a spanish one now", "en"),
        ("👍", None),
        ("Tom Whitaker", None),
    ],
)
def test_detect_language(text: str, language: str | None) -> None:
    assert detect_language(text) == language


def test_field_comparison_is_lenient_only_where_it_should_be() -> None:
    assert _same("full_name", "Rocío Fernández Vega", "rocio  fernandez vega")
    assert not _same("full_name", "Rocío Fernández Vega", "Rocío Fernández")
    assert _same("availability", ["part_time", "weekends"], ["weekends", "part_time"])
    experience = [{"platform": "glovo", "years": 2.0}, {"platform": "just_eat", "years": 0.5}]
    assert _same("delivery_experience", experience, list(reversed(experience)))
    assert not _same("delivery_experience", experience, experience[:1])
    assert _same("start_date", None, None) and not _same("start_date", "2026-10-26", None)


def test_cost_counts_cache_reads_and_writes() -> None:
    data = {
        "model": "claude-haiku-5-5",
        "input_tokens": 6000,
        "output_tokens": 100,
        "cache_read_tokens": 5000,
        "cache_write_tokens": 0,
    }
    # 1,000 uncached × $0.10 + 5,000 read × $0.01 + 100 out × $0.50, per million
    assert call_cost(data) == pytest.approx((100 + 50 + 50) / 1_000_000)
    assert call_cost({**data, "model": "unknown"}) == 0


def test_cli_writes_a_named_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_module, "EVALS_DIR", tmp_path)
    monkeypatch.delenv("DEMO_TIME_SCALE", raising=False)
    assert run_module.main(["--fake", "--only", "20_abandoned_monterrey", "--name", "t"]) == 0
    report = (tmp_path / "reports" / "t.md").read_text()
    assert "Scenarios passed | 1/1" in report
    assert "(t/20_abandoned_monterrey.md)" in report
    assert (tmp_path / "reports" / "t" / "20_abandoned_monterrey.md").exists()
    assert len(list((tmp_path / "runs").glob("*/scores.json"))) == 1
