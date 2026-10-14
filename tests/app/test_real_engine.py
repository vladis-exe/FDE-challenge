"""The worker wired to the real screening engine, with a scripted LLM (never the network)."""

from datetime import UTC, datetime, timedelta

import pytest
import time_machine

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services
from screening.config import load_config
from screening.engine import EngineContext

T0 = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)  # Wednesday, midday in Madrid


def extraction(**fields) -> dict:
    top = {key: fields.pop(key) for key in ("consent", "confirmation") if key in fields}
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
    conversation = services.start_conversation(
        candidate, Conversation.Channel.WHATSAPP, vacancy_id="driver"
    )
    assert conversation.next_tick_at is not None  # first reminder scheduled by the engine

    llm.scripts["extract"].append(
        extraction(consent="yes", full_name="Pedro Gómez", has_driver_license="no")
    )
    services.store_inbound(conversation, "sí, soy Pedro Gómez y no tengo carnet")
    drain()

    conversation.refresh_from_db()
    candidate.refresh_from_db()
    assert conversation.status == Conversation.Status.DISQUALIFIED
    assert conversation.final_record["disqualify_reason"] == "no_license"
    assert conversation.final_record["fields"]["full_name"] == "Pedro Gómez"
    assert conversation.summary == "Resumen para el reclutador."
    assert conversation.completed_at is not None
    assert conversation.next_tick_at is None
    assert candidate.name == "Pedro Gómez"
    assert channel.sent[-1].kind == "close"
    assert conversation.events.filter(type="llm_call").exists()


@time_machine.travel(T0, tick=False)
def test_kitchen_screening_without_a_license_qualifies_and_mirrors_its_score(db, llm, channel):
    """D25 through the worker: a preferred field never disqualifies, it only scores."""
    conversation = services.start_conversation(
        Candidate.objects.create(phone="+34600111999"),
        Conversation.Channel.WHATSAPP,
        vacancy_id="kitchen_prep",
    )
    answers = [
        extraction(consent="yes"),
        extraction(full_name="Ana Ruiz"),
        extraction(location="Malasaña"),
        extraction(availability=["full_time"]),
        extraction(schedule=["morning"]),
        extraction(start_date={"kind": "asap"}),
        extraction(has_driver_license="no"),
        extraction(food_handler_certificate="yes"),
        extraction(confirmation="confirm"),
    ]
    for answer in answers:
        llm.scripts["extract"].append(answer)
        services.store_inbound(conversation, "respuesta")
        drain()

    conversation.refresh_from_db()
    assert conversation.status == Conversation.Status.QUALIFIED
    assert (conversation.vacancy_id, conversation.city) == ("kitchen_prep", "madrid")
    assert conversation.preference_score == 1.0  # the certificate's weight; no license, no 1.5
    record = conversation.final_record
    assert record["fields"]["has_driver_license"] is False
    assert record["preference_score"] == 1.0 and record["disqualify_reason"] is None


def test_silence_gets_the_first_reminder_from_the_real_timers(db, llm, channel):
    with time_machine.travel(T0, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111333"),
            Conversation.Channel.WHATSAPP,
            vacancy_id="driver",
        )
    with time_machine.travel(T0 + timedelta(minutes=14), tick=False):
        assert not services.process_due_tick()
    with time_machine.travel(T0 + timedelta(minutes=16), tick=False):
        assert services.process_due_tick()

    conversation.refresh_from_db()
    assert channel.sent[-1].kind == "reminder"
    assert conversation.state["reminders_sent"] == 1
    assert conversation.next_tick_at > T0 + timedelta(minutes=16)


# Reminder scheduling through the worker (real timers: schedule, quiet hours, abandonment)


def tick_at(moment: datetime) -> bool:
    with time_machine.travel(moment, tick=False):
        return services.process_due_tick()


def test_full_silence_sends_three_reminders_then_abandons(db, llm, channel):
    with time_machine.travel(T0, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111444"),
            Conversation.Channel.WHATSAPP,
            vacancy_id="driver",
        )

    # Follow next_tick_at exactly as the worker would, until there is nothing left to do.
    for _ in range(10):
        conversation.refresh_from_db()
        if conversation.next_tick_at is None:
            break
        assert tick_at(conversation.next_tick_at)

    conversation.refresh_from_db()
    assert [s.kind for s in channel.sent] == ["reply", "reminder", "reminder", "reminder"]
    assert conversation.status == Conversation.Status.ABANDONED
    assert conversation.completed_at is not None
    assert conversation.final_record["status"] == "abandoned"


def test_reminder_due_in_quiet_hours_is_scheduled_for_the_morning(db, llm, channel):
    evening = datetime(2026, 10, 14, 18, 50, tzinfo=UTC)  # 20:50 in Madrid (CEST)
    with time_machine.travel(evening, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111555"),
            Conversation.Channel.WHATSAPP,
            vacancy_id="driver",
        )
    # 15 min later is 21:05 local: deferred to 09:00 local, 07:00 UTC.
    assert conversation.next_tick_at == datetime(2026, 10, 15, 7, 0, tzinfo=UTC)
    assert not tick_at(evening + timedelta(minutes=20))


def test_demo_time_scale_compresses_the_schedule(db, llm, channel, monkeypatch):
    monkeypatch.setenv("DEMO_TIME_SCALE", "60")
    context = EngineContext(config=load_config(), llm=llm)
    monkeypatch.setattr(services, "engine_context", lambda: context)

    with time_machine.travel(T0, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111666"),
            Conversation.Channel.WHATSAPP,
            vacancy_id="driver",
        )
    assert conversation.next_tick_at == T0 + timedelta(seconds=15)  # 15 min / 60
    assert tick_at(T0 + timedelta(seconds=16))
    assert channel.sent[-1].kind == "reminder"


def test_a_reply_resets_the_reminder_clock(db, llm, channel):
    with time_machine.travel(T0, tick=False):
        conversation = services.start_conversation(
            Candidate.objects.create(phone="+34600111777"),
            Conversation.Channel.WHATSAPP,
            vacancy_id="driver",
        )
    assert tick_at(T0 + timedelta(minutes=16))  # first reminder

    llm.scripts["extract"].append(extraction(consent="yes"))
    reply_at = T0 + timedelta(minutes=30)
    with time_machine.travel(reply_at, tick=False):
        services.store_inbound(conversation, "sí")
        drain()

    conversation.refresh_from_db()
    assert conversation.state["reminders_sent"] == 0
    assert conversation.next_tick_at == reply_at + timedelta(minutes=15)
