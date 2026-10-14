"""Test doubles for the engine and the channel adapters."""

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db import transaction

from apps.candidates.models import Conversation
from apps.messaging.models import Message
from screening.schemas import (
    Channel,
    ConversationState,
    Event,
    InboundMessage,
    OutboundMessage,
    Status,
    TranscriptLine,
    TurnResult,
)


class FakeEngine:
    """CONTRACTS §2 signatures. Echoes each message; "bye" qualifies (close), "boom" raises."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.remind = True

    def new_conversation(
        self,
        conversation_id: str,
        channel: Channel,
        *,
        vacancy_id: str,
        phone,
        language,
        now: datetime,
    ) -> ConversationState:
        return ConversationState(
            conversation_id=conversation_id,
            channel=channel,
            vacancy_id=vacancy_id,
            language=language or "es",
        )

    def start(self, state: ConversationState, *, now: datetime, ctx) -> TurnResult:
        state = state.model_copy(update={"last_outbound_at": now})
        return TurnResult(
            state=state,
            outbound=[OutboundMessage(text="Hola, soy Alex (IA)", kind="reply")],
            events=[Event(type="conversation_started", at=now)],
        )

    def handle_message(self, state: ConversationState, message: InboundMessage, *, ctx):
        self.seen.append(message.text)
        if message.text == "boom":
            raise RuntimeError("engine bug")
        state = state.model_copy(deep=True)
        state.last_inbound_at = message.received_at
        state.reminders_sent = 0
        state.transcript_tail.append(
            TranscriptLine(
                role="candidate", text=message.text, at=message.received_at, message_id=message.id
            )
        )
        kind = "reply"
        if message.text == "bye":
            state.status = Status.QUALIFIED
            state.summary = "Qualified."
            kind = "close"
        return TurnResult(
            state=state,
            outbound=[OutboundMessage(text=f"echo: {message.text}", kind=kind)],
            events=[
                Event(type="field_accepted", at=message.received_at, data={"n": len(self.seen)})
            ],
        )

    def next_due_at(self, state: ConversationState, *, config) -> datetime | None:
        anchor = state.last_inbound_at or state.last_outbound_at
        if state.status != Status.IN_PROGRESS or anchor is None:
            return None
        return anchor + timedelta(minutes=15 * (state.reminders_sent + 1))

    def handle_tick(self, state: ConversationState, *, now: datetime, ctx) -> TurnResult:
        if not self.remind:
            return TurnResult(state=state, changed=False)
        state = state.model_copy(update={"reminders_sent": state.reminders_sent + 1})
        return TurnResult(
            state=state,
            outbound=[OutboundMessage(text="¿Sigues ahí?", kind="reminder")],
            events=[Event(type="reminder_sent", at=now)],
        )


@dataclass
class SentRecord:
    text: str
    kind: str
    in_transaction: bool
    row_committed: bool


_sids = itertools.count(1)  # never reset: provider SIDs are unique across tests too


@dataclass
class FakeChannel:
    sent: list[SentRecord] = field(default_factory=list)
    fail: bool = False

    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None:
        if self.fail:
            raise ConnectionError("provider down")
        self.sent.append(
            SentRecord(
                text=message.text,
                kind=message.kind,
                in_transaction=transaction.get_connection().in_atomic_block,
                row_committed=Message.objects.filter(
                    conversation=conversation, direction="out", text=message.text
                ).exists(),
            )
        )
        return f"SM-out-{next(_sids)}"
