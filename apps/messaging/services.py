"""The processing pipeline (CONTRACTS §5): store inbound, run engine turns, persist, then send.

Reliability rules this module guarantees (each one has a test in tests/app/test_worker.py):
1. Per-conversation ordering: a conversation's inbound messages go through the engine one at a
   time, oldest first. The conversation row stays locked for the whole turn, so no other worker
   can process the same conversation at the same time.
2. Reply-to-latest: if a newer inbound message is already waiting when a turn finishes, that
   turn's state is kept but its reply/reminder is stored as suppressed and never sent. `close`
   messages are always sent.
3. Idempotency: an inbound message with a provider SID (Twilio MessageSid) is stored once, however
   many times the webhook delivers it.
4. Persist before send: state, mirrored columns, outbound messages and events are written in one
   transaction. Sending happens only after it commits, so a crash never leaves a sent message
   without a record.
5. Failures stay local: a send failure is recorded on its message, and an engine or persist error
   marks the message processed with a `worker_error` event. Neither stops the worker loop.
"""

import logging
from datetime import datetime, timedelta
from functools import cache

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Subquery
from django.utils import timezone

from apps.candidates.models import Candidate, Conversation
from apps.messaging import channels
from apps.messaging.models import Event, Message
from screening import engine
from screening.config import load_config
from screening.engine import EngineContext
from screening.llm import AnthropicClient
from screening.record import final_record
from screening.schemas import (
    Channel,
    ConversationState,
    FieldStatus,
    InboundMessage,
    OutboundMessage,
    Status,
    TurnResult,
)

log = logging.getLogger(__name__)

# `next_due_at` already skips quiet hours, so a tick that does nothing should not happen. If it
# does, wait this long (unscaled) before trying again rather than re-ticking in a hot loop.
TICK_RETRY = timedelta(minutes=1)


@cache
def engine_context() -> EngineContext:
    # Built on first use, so importing this module (tests, migrations) never needs an API key.
    return EngineContext(config=load_config(), llm=AnthropicClient())


def start_conversation(
    candidate: Candidate,
    channel: Conversation.Channel,
    *,
    language: str | None = None,
    country: str | None = None,
) -> Conversation:
    """Create a conversation and send the opening message (AI disclosure + consent question)."""
    now = timezone.now()
    conversation = Conversation(candidate=candidate, channel=channel)
    state = engine.new_conversation(
        str(conversation.id), Channel(channel), phone=candidate.phone, language=language, now=now
    )
    if country:
        state.country_hint = country
    # The engine may call the LLM, so it runs before the transaction opens.
    result = engine.start(state, now=now, ctx=engine_context())
    with transaction.atomic():
        outbound = _persist_turn(conversation, result, now=now)
    _send(outbound)
    return conversation


def store_inbound(
    conversation: Conversation,
    text: str,
    *,
    media: str = Message.Media.NONE,
    provider_sid: str | None = None,
) -> tuple[Message, bool]:
    """Queue an inbound message for the worker. Returns (message, created)."""
    try:
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                direction=Message.Direction.IN,
                kind=Message.Kind.INBOUND,
                text=text,
                media=media,
                provider_sid=provider_sid,
            )
    except IntegrityError:
        if provider_sid is None:
            raise
        # Twilio retried a delivery we already stored.
        return Message.objects.get(provider_sid=provider_sid), False
    return message, True


def work_once() -> bool:
    """Do one unit of work. Inbound messages go before reminders. False means idle."""
    return process_next_inbound() or process_due_tick()


def process_next_inbound() -> bool:
    """Run one engine turn for the oldest waiting message of an unlocked conversation."""
    pending = Message.objects.filter(direction=Message.Direction.IN, processed_at__isnull=True)
    with transaction.atomic():
        conversation = (
            Conversation.objects.select_for_update(skip_locked=True)
            .filter(pk__in=pending.values("conversation_id"))
            .annotate(
                first_pending=Subquery(
                    pending.filter(conversation=OuterRef("pk")).order_by("id").values("id")[:1]
                )
            )
            .order_by("first_pending")
            .select_related("candidate")
            .first()
        )
        if conversation is None:
            return False
        message = pending.filter(conversation=conversation).order_by("id").first()
        now = timezone.now()
        try:
            result = engine.handle_message(
                ConversationState.model_validate(conversation.state),
                InboundMessage(
                    id=str(message.pk),
                    text=message.text,
                    received_at=message.created_at,
                    media=message.media,
                ),
                ctx=engine_context(),
            )
            # Checked after the engine call, as close to sending as possible.
            newer_waiting = pending.filter(conversation=conversation, id__gt=message.pk).exists()
            with transaction.atomic():  # savepoint: a failed persist rolls back alone
                outbound = _persist_turn(
                    conversation, result, now=now, inbound=message, suppress=newer_waiting
                )
        except Exception as exc:
            log.exception("turn failed for message %s", message.pk)
            message.processed_at = now
            message.save(update_fields=["processed_at"])
            _record_worker_error(conversation, exc, now, message_id=message.pk)
            return True
    _send(outbound)
    return True


def process_due_tick() -> bool:
    """Run `handle_tick` for one conversation whose `next_tick_at` has passed."""
    now = timezone.now()
    has_pending = Message.objects.filter(
        conversation=OuterRef("pk"), direction=Message.Direction.IN, processed_at__isnull=True
    )
    with transaction.atomic():
        conversation = (
            Conversation.objects.select_for_update(skip_locked=True)
            .filter(status=Conversation.Status.IN_PROGRESS, next_tick_at__lte=now)
            # A waiting message resets the reminder clock, so it goes first.
            .exclude(Exists(has_pending))
            .order_by("next_tick_at")
            .select_related("candidate")
            .first()
        )
        if conversation is None:
            return False
        retry_at = now + TICK_RETRY / engine_context().config.time_scale
        outbound: list[Message] = []
        try:
            state = ConversationState.model_validate(conversation.state)
            result = engine.handle_tick(state, now=now, ctx=engine_context())
            if result.changed:
                with transaction.atomic():
                    outbound = _persist_turn(conversation, result, now=now)
            if conversation.next_tick_at and conversation.next_tick_at <= now:
                # Still due although the engine had nothing to do: back off, don't spin.
                Conversation.objects.filter(pk=conversation.pk).update(next_tick_at=retry_at)
        except Exception as exc:
            log.exception("tick failed for conversation %s", conversation.pk)
            outbound = []
            Conversation.objects.filter(pk=conversation.pk).update(next_tick_at=retry_at)
            _record_worker_error(conversation, exc, now)
    _send(outbound)
    return True


def _persist_turn(
    conversation: Conversation,
    result: TurnResult,
    *,
    now: datetime,
    inbound: Message | None = None,
    suppress: bool = False,
) -> list[Message]:
    """Write one turn's results. Call inside a transaction. Returns the messages to send."""
    state = result.state
    location = state.profile.location.value
    conversation.state = state.model_dump(mode="json")
    conversation.status = state.status
    conversation.stage = state.stage
    conversation.language = state.language
    conversation.country = location.country if location else (state.country_hint or "")
    conversation.city = location.city if location else ""
    conversation.last_inbound_at = state.last_inbound_at
    conversation.summary = state.summary or ""
    if state.status == Status.IN_PROGRESS:
        # A late reply can reopen an abandoned conversation.
        conversation.completed_at = None
        conversation.final_record = None
    else:
        conversation.completed_at = conversation.completed_at or now
        conversation.final_record = final_record(state)
    conversation.next_tick_at = engine.next_due_at(state, config=engine_context().config)
    conversation.save()

    name = state.profile.full_name
    if name.status == FieldStatus.ACCEPTED and name.value != conversation.candidate.name:
        conversation.candidate.name = name.value
        conversation.candidate.save(update_fields=["name"])

    if inbound is not None:
        inbound.processed_at = now
        inbound.save(update_fields=["processed_at"])

    Event.objects.bulk_create(
        Event(
            conversation=conversation,
            type=event.type,
            data=event.model_dump(mode="json")["data"],
            created_at=event.at,
        )
        for event in result.events
    )
    outbound = Message.objects.bulk_create(
        Message(
            conversation=conversation,
            direction=Message.Direction.OUT,
            kind=item.kind,
            text=item.text,
            suppressed=suppress and item.kind != "close",
        )
        for item in result.outbound
    )
    return [message for message in outbound if not message.suppressed]


def _send(messages: list[Message]) -> None:
    """Deliver committed messages. A failure is stored on the message, never raised."""
    for message in messages:
        conversation = message.conversation
        try:
            sid = channels.channel_for(conversation).send(
                conversation, OutboundMessage(text=message.text, kind=message.kind)
            )
        except Exception as exc:
            # Only the type in the log: provider errors can echo the phone number.
            log.warning("send failed for message %s: %s", message.pk, type(exc).__name__)
            message.send_error = f"{type(exc).__name__}: {exc}"[:500]
            message.save(update_fields=["send_error"])
        else:
            if sid:
                message.provider_sid = sid
                message.save(update_fields=["provider_sid"])


def _record_worker_error(
    conversation: Conversation, exc: Exception, now: datetime, *, message_id: int | None = None
) -> None:
    Event.objects.create(
        conversation=conversation,
        type="worker_error",
        data={"message_id": message_id, "error": f"{type(exc).__name__}: {exc}"[:500]},
        created_at=now,
    )
