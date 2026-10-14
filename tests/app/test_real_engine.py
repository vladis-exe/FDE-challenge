"""The worker wired to the real screening engine, with a scripted LLM (never the network)."""

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services

T0 = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)  # Wednesday, midday in Madrid


def extraction(**fields) -> dict:
    top = {key: fields.pop(key) for key in ("consent",) if key in fields}
    return {"intent": "answer", "language": "es", "fields": fields, **top}


@pytest.fixture
def llm(fake_llm):
    fake_llm.scripts.update(
        {
            "extract": [],
            "compose": lambda system, messages: "Vale. ¿Seguimos?",
            "summary": lambda system, messages: "Resumen para el reclutador.",
        }
    )
    return fake_llm


def drain() -> None:
    for _ in range(20):
        if not services.work_once():
            return
    raise AssertionError("worker never went idle")


@time_machine.travel(T0, tick=False)
def test_knockout_turn_is_persisted_and_the_close_is_sent(db, llm, channel):
    candidate = Candidate.objects.create(phone="+34600111222")
    conversation = services.start_conversation(candidate, Conversation.Channel.WHATSAPP)
    assert conversation.next_tick_at is not None  # first reminder scheduled by the engine

    llm.scripts["extract"].append(extraction(consent="yes", full_name="Pedro Gómez", license="no"))
    services.store_inbound(conversation, "sí, soy Pedro Gómez y no tengo carnet")
    drain()

    conversation.refresh_from_db()
    candidate.refresh_from_db()
    assert conversation.status == Conversation.Status.DISQUALIFIED
    assert conversation.final_record["disqualify_reason"] == "no_license"
    assert conversation.final_record["full_name"] == "Pedro Gómez"
    assert conversation.summary == "Resumen para el reclutador."
    assert conversation.completed_at is not None
    assert conversation.next_tick_at is None
    assert candidate.name == "Pedro Gómez"
    assert channel.sent[-1].kind == "close"
    assert conversation.events.filter(type="llm_call").exists()


def test_silence_gets_the_first_reminder_from_the_real_timers(db, llm, channel):
    with time_machine.travel(T0, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111333"), Conversation.Channel.WHATSAPP
        )
    with time_machine.travel(T0 + timedelta(minutes=14), tick=False):
        assert not services.process_due_tick()
    with time_machine.travel(T0 + timedelta(minutes=16), tick=False):
        assert services.process_due_tick()

    conversation.refresh_from_db()
    assert channel.sent[-1].kind == "reminder"
    assert conversation.state["reminders_sent"] == 1
    assert conversation.next_tick_at > T0 + timedelta(minutes=16)
