import io
import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.dashboard.management.commands.seed_demo import FIXTURE
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
    call_command("seed_demo", "--from-run", str(run_dir), "--fixture", str(fixture))
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


def test_refuses_a_fixture_from_an_older_engine(db):
    """The shipped fixture predates CONTRACTS v4 until A12 rebuilds it from a live run."""
    with pytest.raises(CommandError, match="schema_version"):
        seed("--fixture", str(FIXTURE), "--password", "x")
    assert not Conversation.objects.exists()


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

    seed("--from-run", str(run_dir), "--fixture", str(fixture))

    built = json.loads(fixture.read_text(encoding="utf-8"))
    assert [b["scenario_id"] for b in built] == [item["scenario_id"]]
    assert set(built[0]["lines"][0]) == {"role", "at", "text", "kind", "media", "suppressed"}
