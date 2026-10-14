import io
import json
from collections import Counter

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.dashboard.management.commands.seed_demo import FIXTURE
from apps.messaging.models import Message


def seed(*args: str) -> str:
    out = io.StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


def test_seeds_every_fixture_conversation_with_a_recruiter_login(db):
    output = seed("--password", "pw-for-tests-only")

    total = len(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert Conversation.objects.count() == total
    statuses = Counter(Conversation.objects.values_list("status", flat=True))
    assert {"qualified", "needs_review", "disqualified"} <= set(statuses)
    assert get_user_model().objects.get(username="recruiter").check_password("pw-for-tests-only")
    assert "pw-for-tests-only" not in output  # a given password is never echoed


def test_seeded_data_is_consistent(db):
    seed("--password", "x")
    now = timezone.now()
    assert not Conversation.objects.filter(started_at__gt=now).exists()
    assert not Message.objects.filter(created_at__gt=now).exists()
    for conversation in Conversation.objects.all():
        assert conversation.state["conversation_id"] == str(conversation.pk)
        assert conversation.state["status"] == conversation.status
        if conversation.status != "in_progress":
            assert conversation.final_record["conversation_id"] == str(conversation.pk)
        # Provenance links point at this conversation's inbound messages.
        sources = {f["source_message_id"] for f in conversation.state["profile"].values()}
        inbound_pks = conversation.messages.filter(direction="in").values_list("pk", flat=True)
        inbound = {str(pk) for pk in inbound_pks}
        assert sources - {None} <= inbound


def test_whatsapp_candidates_get_phones_and_web_candidates_none(db):
    seed("--password", "x")
    for conversation in Conversation.objects.select_related("candidate"):
        has_phone = conversation.candidate.phone is not None
        assert has_phone == (conversation.channel == Conversation.Channel.WHATSAPP)


def test_refuses_to_seed_over_existing_data_unless_reset(db):
    seed("--password", "x")
    with pytest.raises(CommandError):
        seed("--password", "x")
    seed("--reset", "--password", "x")
    assert Candidate.objects.count() == Conversation.objects.count()


def test_generates_and_prints_a_password_when_none_is_given(db, monkeypatch):
    monkeypatch.delenv("DEMO_RECRUITER_PASSWORD", raising=False)
    output = seed()
    password = output.strip().rsplit(" / ", 1)[1]
    assert get_user_model().objects.get(username="recruiter").check_password(password)


def test_fixture_is_rebuilt_from_an_eval_run(tmp_path):
    item = json.loads(FIXTURE.read_text(encoding="utf-8"))[0]
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
