"""Temporary stand-in for `screening.engine` (CONTRACTS §2) until E5 lands. Delete it then.

It has the contract's signatures and walks the stages one message at a time, echoing what it
received, so the worker, web chat and admin can be built and demoed end to end without an LLM.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from screening.config import ScreeningConfig
from screening.schemas import (
    Channel,
    ConversationState,
    Event,
    InboundMessage,
    OutboundMessage,
    Stage,
    Status,
    TranscriptLine,
    TurnResult,
)

STAGES = list(Stage)


@dataclass(frozen=True)
class EngineContext:
    config: ScreeningConfig
    llm: Any = None


def new_conversation(
    conversation_id: str,
    channel: Channel,
    *,
    phone: str | None,
    language: Literal["es", "en"] | None,
    now: datetime,
) -> ConversationState:
    hint = "MX" if phone and phone.startswith("+52") else "ES" if phone else None
    return ConversationState(
        conversation_id=conversation_id,
        channel=channel,
        language=language or "es",
        country_hint=hint,
    )


def start(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult:
    text = "Hola, soy Alex (stub engine, sin IA todavía). ¿Empezamos?"
    state = _with_agent_line(state, text, now)
    return TurnResult(
        state=state,
        outbound=[OutboundMessage(text=text, kind="reply")],
        events=[Event(type="conversation_started", at=now)],
    )


def handle_message(
    state: ConversationState, message: InboundMessage, *, ctx: EngineContext
) -> TurnResult:
    now = message.received_at
    state = state.model_copy(deep=True)
    state.last_inbound_at = now
    state.reminders_sent = 0
    state.transcript_tail.append(
        TranscriptLine(role="candidate", text=message.text, at=now, message_id=message.id)
    )
    if state.status != Status.IN_PROGRESS:
        return TurnResult(state=state, outbound=[], events=[])

    next_stage = STAGES[STAGES.index(state.stage) + 1]
    events = [Event(type="stage_entered", at=now, data={"stage": next_stage})]
    state.stage = next_stage
    if next_stage == Stage.DONE:
        state.status = Status.QUALIFIED
        state.summary = "Stub summary: the stub engine qualifies everyone."
        events.append(Event(type="status_changed", at=now, data={"status": state.status}))
        outbound = OutboundMessage(
            text="¡Gracias! Un reclutador te escribirá pronto.", kind="close"
        )
    else:
        outbound = OutboundMessage(
            text=f"Recibido: «{message.text[:80]}». Siguiente paso: {next_stage}.", kind="reply"
        )
    state = _with_agent_line(state, outbound.text, now)
    return TurnResult(state=state, outbound=[outbound], events=events)


def handle_tick(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult:
    anchor = state.last_inbound_at or state.last_outbound_at
    if state.status != Status.IN_PROGRESS or anchor is None:
        return TurnResult(state=state, changed=False)
    schedule = ctx.config.reminder_schedule
    state = state.model_copy(deep=True)
    if now >= anchor + ctx.config.abandon_after:
        state.status = Status.ABANDONED
        return TurnResult(
            state=state, events=[Event(type="status_changed", at=now, data={"status": "abandoned"})]
        )
    if state.reminders_sent < len(schedule) and now >= anchor + schedule[state.reminders_sent]:
        state.reminders_sent += 1
        text = f"¿Sigues ahí? (recordatorio {state.reminders_sent})"
        state = _with_agent_line(state, text, now)
        return TurnResult(
            state=state,
            outbound=[OutboundMessage(text=text, kind="reminder")],
            events=[Event(type="reminder_sent", at=now, data={"n": state.reminders_sent})],
        )
    return TurnResult(state=state, changed=False)


def final_record(state: ConversationState) -> dict[str, Any]:
    """Stand-in for `screening.record.final_record`."""
    return {
        "conversation_id": state.conversation_id,
        "status": state.status,
        "language": state.language,
        "summary": state.summary,
    }


def _with_agent_line(state: ConversationState, text: str, now: datetime) -> ConversationState:
    state = state.model_copy(deep=True)
    state.transcript_tail.append(TranscriptLine(role="agent", text=text, at=now))
    state.last_outbound_at = now
    return state
