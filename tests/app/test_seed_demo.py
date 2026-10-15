import io
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.messaging.models import Message
from evals.scenario import SCENARIOS_DIR, load_scenario
from evals.simulator import simulate
from screening.cli import fake_llm
from screening.config import load_config
from screening.engine import EngineContext

# Each job, and a different outcome: a driver without a license (knockout), and a kitchen
# hire without one (preferred only). One line per turn, worded for the engine's keyword stub.
RUNS = {
    "01_es_happy_madrid": ["sí", "Pedro Gómez", "no"],
    "21_kitchen_no_license_madrid": [
        "sí", "Marta Gil", "Lavapiés", "media jornada", "por las tardes", "el lunes que viene",
        "no", "sí", "sí",
    ],
}  # fmt: skip


class ScriptedCandidate:
    tokens = {"input": 0, "output": 0}

    def __init__(self, lines: list[str]) -> None:
        self.lines = iter(lines)

    def reply(self, lines, directive, stage, now) -> str:
        return next(self.lines)


@pytest.fixture(scope="module")
def v4_fixture(tmp_path_factory) -> Path:
    """A fixture built the real way (an eval run, then --from-run), offline: the engine's
    keyword-stub LLM and scripted candidates stand in for the live models."""
    config = load_config()
    run_dir = tmp_path_factory.mktemp("run")
    for n, (scenario_id, lines) in enumerate(RUNS.items(), start=1):
        scenario = load_scenario(SCENARIOS_DIR / f"{scenario_id}.yaml", config)
        scenario = scenario.model_copy(update={"script": [], "pauses": [], "max_turns": len(lines)})
        ctx = EngineContext(config=config, llm=fake_llm(config.vacancy(scenario.vacancy)))
        result = simulate(scenario, ctx, ScriptedCandidate(lines))
        run = {"run": result.model_dump(mode="json"), "score": {}}
        (run_dir / f"{n:02d}_{scenario_id}.json").write_text(json.dumps(run))
    fixture = run_dir / "fixture.json"
    call_command("seed_demo", "--from-run", str(run_dir), "--fixture", str(fixture), "--build-only")
    return fixture


def seed(*args: str) -> str:
    out = io.StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


def test_seeds_every_fixture_conversation_with_a_recruiter_login(db, v4_fixture):
    output = seed("--fixture", str(v4_fixture), "--password", "pw-for-tests-only")

    assert Conversation.objects.count() == len(RUNS)
    assert dict(Conversation.objects.values_list("vacancy_id", "status")) == {
        "driver": "disqualified",
        "kitchen_prep": "qualified",
    }
    assert get_user_model().objects.get(username="recruiter").check_password("pw-for-tests-only")
    assert "pw-for-tests-only" not in output  # a given password is never echoed


def test_seeded_data_is_consistent(db, v4_fixture):
    seed("--fixture", str(v4_fixture), "--password", "x")
    now = timezone.now()
    assert not Conversation.objects.filter(started_at__gt=now).exists()
    assert not Message.objects.filter(created_at__gt=now).exists()
    for conversation in Conversation.objects.all():
        assert conversation.state["conversation_id"] == str(conversation.pk)
        assert conversation.state["status"] == conversation.status
        assert conversation.state["vacancy_id"] == conversation.vacancy_id
        assert conversation.state["preference_score"] == conversation.preference_score
        assert conversation.final_record["conversation_id"] == str(conversation.pk)
        # Provenance links point at this conversation's inbound messages.
        fields = conversation.state["profile"]["fields"].values()
        sources = {f["source_message_id"] for f in fields}
        inbound_pks = conversation.messages.filter(direction="in").values_list("pk", flat=True)
        assert sources - {None} <= {str(pk) for pk in inbound_pks}
    kitchen = Conversation.objects.get(vacancy_id="kitchen_prep")
    assert (kitchen.city, kitchen.candidate.name) == ("madrid", "Marta Gil")
    assert kitchen.preference_score == 1.0  # the certificate; no license


def test_whatsapp_candidates_get_phones_and_web_candidates_none(db, v4_fixture):
    seed("--fixture", str(v4_fixture), "--password", "x")
    for conversation in Conversation.objects.select_related("candidate"):
        has_phone = conversation.candidate.phone is not None
        assert has_phone == (conversation.channel == Conversation.Channel.WHATSAPP)


def test_refuses_to_seed_over_existing_data_unless_reset(db, v4_fixture):
    seed("--fixture", str(v4_fixture), "--password", "x")
    with pytest.raises(CommandError):
        seed("--fixture", str(v4_fixture), "--password", "x")
    seed("--fixture", str(v4_fixture), "--reset", "--password", "x")
    assert Candidate.objects.count() == Conversation.objects.count()


def test_generates_and_prints_a_password_when_none_is_given(db, monkeypatch, v4_fixture):
    monkeypatch.delenv("DEMO_RECRUITER_PASSWORD", raising=False)
    output = seed("--fixture", str(v4_fixture))
    password = output.strip().rsplit(" / ", 1)[1]
    assert get_user_model().objects.get(username="recruiter").check_password(password)


def test_refuses_a_fixture_from_an_older_engine(db, tmp_path, v4_fixture):
    items = json.loads(v4_fixture.read_text(encoding="utf-8"))
    items[0]["state"]["schema_version"] = 1
    old = tmp_path / "old.json"
    old.write_text(json.dumps(items))
    with pytest.raises(CommandError, match="schema_version"):
        seed("--fixture", str(old), "--password", "x")
    assert not Conversation.objects.exists()


def test_shipped_fixture_covers_both_jobs_and_every_outcome(db):
    seed("--password", "x")
    assert set(Conversation.objects.values_list("vacancy_id", flat=True)) == {
        "driver",
        "kitchen_prep",
    }
    statuses = set(Conversation.objects.values_list("status", flat=True))
    assert {"qualified", "needs_review", "disqualified", "abandoned", "opted_out"} <= statuses
    # The D25 tie-break is visible in the demo: qualified kitchen hires with different scores.
    scores = Conversation.objects.filter(vacancy_id="kitchen_prep", status="qualified")
    assert len(set(scores.values_list("preference_score", flat=True))) > 1


def test_fixture_is_rebuilt_from_an_eval_run(tmp_path, v4_fixture):
    item = json.loads(v4_fixture.read_text(encoding="utf-8"))[0]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    simulator_line = {**item["lines"][0], "latency_ms": 5, "scripted": False}
    good = {**item, "lines": [simulator_line], "error": None, "candidate_turns": 1}
    (run_dir / "01_ok.json").write_text(json.dumps({"run": good, "score": {}}))
    (run_dir / "02_crashed.json").write_text(json.dumps({"run": {**good, "error": "boom"}}))
    (run_dir / "scores.json").write_text("{}")
    fixture = tmp_path / "fixture.json"

    seed("--from-run", str(run_dir), "--fixture", str(fixture), "--build-only")

    built = json.loads(fixture.read_text(encoding="utf-8"))
    assert [b["scenario_id"] for b in built] == [item["scenario_id"]]
    assert set(built[0]["lines"][0]) == {"role", "at", "text", "kind", "media", "suppressed"}


def test_from_run_rebuilds_and_seeds_in_one_command(db, tmp_path, v4_fixture):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for path in v4_fixture.parent.glob("0*.json"):  # the eval run v4_fixture was built from
        (run_dir / path.name).write_text(path.read_text())
    fixture = tmp_path / "fixture.json"
    args = ("--from-run", str(run_dir), "--fixture", str(fixture), "--password", "pw-for-tests")
    seed(*args)
    assert Conversation.objects.count() == len(RUNS)

    with pytest.raises(CommandError, match="--reset"):
        seed(*args)
    seed(*args, "--reset")
    assert Conversation.objects.count() == len(RUNS)
