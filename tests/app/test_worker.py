"""The reliability rules listed in apps/messaging/services.py, one test group per rule."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.messaging import services
from apps.messaging.models import Event, Message
from screening.schemas import Status


@pytest.fixture
def conversation(db, engine, channel) -> Conversation:
    candidate = Candidate.objects.create(phone="+34600111222")
    conversation = services.start_conversation(
        candidate, Conversation.Channel.WHATSAPP, vacancy_id="driver"
    )
    channel.sent.clear()
    return conversation


def drain() -> None:
    for _ in range(50):
        if not services.work_once():
            return
    raise AssertionError("worker never went idle")


def replies(conversation: Conversation) -> list[Message]:
    return list(
        conversation.messages.filter(direction="out").exclude(kind="reply", text__startswith="Hola")
    )


# Starting a conversation


def test_start_persists_opening_message_state_and_events(db, engine, channel):
    candidate = Candidate.objects.create()
    conversation = services.start_conversation(
        candidate, Conversation.Channel.WEB, vacancy_id="driver", language="en", country="MX"
    )
    conversation.refresh_from_db()
    assert conversation.language == "en"
    assert conversation.country == "MX"
    assert conversation.state["conversation_id"] == str(conversation.pk)
    assert [m.text for m in conversation.messages.all()] == ["Hola, soy Alex (IA)"]
    assert list(conversation.events.values_list("type", flat=True)) == ["conversation_started"]
    assert [s.text for s in channel.sent] == ["Hola, soy Alex (IA)"]


# 1. Per-conversation ordering


def test_messages_are_processed_one_at_a_time_oldest_first(conversation, engine):
    for text in ["uno", "dos", "tres"]:
        services.store_inbound(conversation, text)

    assert services.process_next_inbound()
    assert engine.seen == ["uno"]
    drain()

    assert engine.seen == ["uno", "dos", "tres"]
    conversation.refresh_from_db()
    tail = [line["text"] for line in conversation.state["transcript_tail"]]
    assert tail == ["uno", "dos", "tres"]
    assert not conversation.messages.filter(direction="in", processed_at__isnull=True).exists()


def test_oldest_waiting_message_across_conversations_goes_first(conversation, engine, channel):
    other = services.start_conversation(
        Candidate.objects.create(), Conversation.Channel.WEB, vacancy_id="driver"
    )
    services.store_inbound(conversation, "first")
    services.store_inbound(other, "second")
    services.store_inbound(conversation, "third")
    drain()
    assert engine.seen == ["first", "second", "third"]


# 2. Reply-to-latest


def test_reply_is_suppressed_when_a_newer_message_is_waiting(conversation, engine, channel):
    services.store_inbound(conversation, "soy Laura")
    services.store_inbound(conversation, "Pérez")
    drain()

    assert engine.seen == ["soy Laura", "Pérez"]  # both state updates happened
    out = replies(conversation)
    assert [(m.text, m.suppressed) for m in out] == [
        ("echo: soy Laura", True),
        ("echo: Pérez", False),
    ]
    assert [s.text for s in channel.sent] == ["echo: Pérez"]


def test_close_is_never_suppressed(conversation, engine, channel):
    services.store_inbound(conversation, "bye")
    services.store_inbound(conversation, "one more thing")
    drain()
    assert [s.text for s in channel.sent] == ["echo: bye", "echo: one more thing"]


# 3. Idempotency on the provider SID


def test_inbound_with_same_provider_sid_is_stored_once(conversation):
    first, created = services.store_inbound(conversation, "hola", provider_sid="SM123")
    again, created_again = services.store_inbound(conversation, "hola", provider_sid="SM123")
    assert created and not created_again
    assert again.pk == first.pk
    assert conversation.messages.filter(direction="in").count() == 1


def test_inbound_without_sid_is_always_stored(conversation):
    services.store_inbound(conversation, "hola")
    services.store_inbound(conversation, "hola")
    assert conversation.messages.filter(direction="in").count() == 2


# 4. Persist in one transaction, then send


@pytest.mark.django_db(transaction=True)
def test_send_happens_after_the_turn_is_committed(engine, channel):
    conversation = services.start_conversation(
        Candidate.objects.create(), Conversation.Channel.WEB, vacancy_id="driver"
    )
    services.store_inbound(conversation, "hola")
    drain()

    record = channel.sent[-1]
    assert record.text == "echo: hola"
    assert not record.in_transaction
    assert record.row_committed


def test_turn_writes_state_mirror_events_and_outbound_together(conversation, engine):
    message, _ = services.store_inbound(conversation, "bye")
    drain()

    conversation.refresh_from_db()
    message.refresh_from_db()
    assert message.processed_at is not None
    assert conversation.status == Conversation.Status.QUALIFIED
    assert conversation.summary == "Qualified."
    assert conversation.final_record["status"] == "qualified"
    assert conversation.final_record["vacancy_id"] == conversation.vacancy_id == "driver"
    assert conversation.completed_at is not None
    assert conversation.next_tick_at is None
    assert conversation.events.filter(type="field_accepted").exists()


# 5. Failures are recorded and the loop keeps going


def test_send_failure_is_recorded_and_processing_continues(conversation, engine, channel):
    channel.fail = True
    services.store_inbound(conversation, "uno")
    drain()
    channel.fail = False
    services.store_inbound(conversation, "dos")
    drain()

    failed, ok = replies(conversation)
    assert failed.send_error == "ConnectionError: provider down"
    assert failed.provider_sid is None
    assert ok.send_error == "" and ok.provider_sid.startswith("SM-out-")


def test_engine_error_marks_message_processed_and_moves_on(conversation, engine, channel):
    bad, _ = services.store_inbound(conversation, "boom")
    services.store_inbound(conversation, "hola")
    drain()

    bad.refresh_from_db()
    assert bad.processed_at is not None
    error = Event.objects.get(conversation=conversation, type="worker_error")
    assert error.data == {"message_id": bad.pk, "error": "RuntimeError: engine bug"}
    assert engine.seen == ["boom", "hola"]
    assert [s.text for s in channel.sent] == ["echo: hola"]


def test_run_worker_once_drains_the_queue(conversation, engine):
    services.store_inbound(conversation, "uno")
    services.store_inbound(conversation, "dos")
    call_command("run_worker", "--once")
    assert engine.seen == ["uno", "dos"]


# Reminders via next_tick_at


def make_due(conversation: Conversation) -> None:
    Conversation.objects.filter(pk=conversation.pk).update(
        next_tick_at=timezone.now() - timedelta(seconds=1)
    )


def test_due_tick_sends_reminder_and_reschedules(conversation, engine, channel):
    make_due(conversation)
    assert services.process_due_tick()

    conversation.refresh_from_db()
    assert [s.kind for s in channel.sent] == ["reminder"]
    assert conversation.state["reminders_sent"] == 1
    assert conversation.next_tick_at > timezone.now()
    assert not services.process_due_tick()


def test_tick_that_does_nothing_is_retried_later_not_immediately(conversation, engine, channel):
    engine.remind = False
    make_due(conversation)
    before = timezone.now()
    assert services.process_due_tick()

    conversation.refresh_from_db()
    assert channel.sent == []
    assert conversation.next_tick_at >= before + services.TICK_RETRY
    assert not services.process_due_tick()


def test_waiting_message_is_processed_before_any_tick(conversation, engine, channel):
    make_due(conversation)
    services.store_inbound(conversation, "hola")
    assert not services.process_due_tick()
    assert services.work_once()
    assert engine.seen == ["hola"]


def test_finished_conversations_are_never_ticked(conversation, engine, channel):
    Conversation.objects.filter(pk=conversation.pk).update(status=Status.QUALIFIED)
    make_due(conversation)
    assert not services.process_due_tick()
