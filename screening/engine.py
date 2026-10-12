"""Engine API (CONTRACTS.md §2): state + one inbound message in, new state + messages + events out.

Functional core: no database, no network except through `ctx.llm`. One turn is
    extract (LLM reads) → policy.decide (code decides) → render (fixed text, or LLM phrases a plan)
If any LLM call fails after retries, the candidate gets a holding reply and the
screening state is left exactly as it was, so repeating the message works.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from screening import messages, timers
from screening.compose import ReplyPlan, compose_reply
from screening.config import ScreeningConfig
from screening.llm import LLMClient, LLMError, LLMResult
from screening.locale import candidate_timezone
from screening.policy import FixedReply, decide
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
from screening.summary import summarize
from screening.understand import extract

OPEN = {Status.IN_PROGRESS, Status.ABANDONED}  # a screening that can still continue
PHONE_COUNTRIES: dict[str, Literal["ES", "MX"]] = {"+34": "ES", "+52": "MX"}


@dataclass(frozen=True)
class EngineContext:
    config: ScreeningConfig
    llm: LLMClient


def new_conversation(
    conversation_id: str,
    channel: Channel,
    *,
    phone: str | None,
    language: Literal["es", "en"] | None,
    now: datetime,
) -> ConversationState:
    hint = next(
        (
            country
            for prefix, country in PHONE_COUNTRIES.items()
            if phone and phone.startswith(prefix)
        ),
        None,
    )
    return ConversationState(
        conversation_id=conversation_id,
        channel=channel,
        language=language or "es",
        country_hint=hint,
    )


def start(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult:
    """The opening message: AI disclosure, privacy link and the consent question."""
    state = state.model_copy(deep=True)
    opening = OutboundMessage(text=messages.opening(state, ctx.config), kind="reply")
    _record_outbound(state, [opening], now, ctx.config)
    return TurnResult(
        state=state,
        outbound=[opening],
        events=[Event(type="conversation_started", at=now, data={"channel": state.channel})],
    )


def handle_message(
    state: ConversationState, message: InboundMessage, *, ctx: EngineContext
) -> TurnResult:
    now = message.received_at
    # Bookkeeping that holds whatever happens next, including an LLM failure.
    base = state.model_copy(deep=True)
    base.last_inbound_at = now
    base.reminders_sent = 0
    _append(base, "candidate", message.text or f"[{message.media}]", now, ctx.config, message.id)

    if state.status is Status.OPTED_OUT:
        return TurnResult(state=base)  # they asked us to stop: never reply again

    events: list[Event] = []
    if message.media != "none":
        events.append(Event(type="media_received", at=now, data={"media": message.media}))
        if not message.text.strip():
            return _reply(base, [_fixed(FixedReply("media"), base, ctx)], events, now, ctx)

    try:
        extraction = extract(state, message, llm=ctx.llm, config=ctx.config)
        events.append(_llm_call("extract", extraction, now))
        decision = decide(base, extraction.value, message, ctx.config)
        events.extend(decision.events)
        outbound: list[OutboundMessage] = []
        for reply in decision.replies:
            if isinstance(reply, ReplyPlan):
                composed = compose_reply(reply, decision.state.transcript_tail, llm=ctx.llm)
                events.append(_llm_call("compose", composed, now))
                outbound.append(OutboundMessage(text=composed.value, kind="reply"))
            else:
                outbound.append(_fixed(reply, decision.state, ctx))
    except LLMError as error:
        events.append(Event(type="llm_error", at=now, data={"error": str(error)}))
        return _reply(base, [_fixed(FixedReply("holding"), base, ctx)], events, now, ctx)

    result = _reply(decision.state, outbound, events, now, ctx)
    if state.status in OPEN and result.state.status not in OPEN:
        _write_summary(result, now, ctx)
    return result


def handle_tick(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult:
    """Send a due reminder, or abandon after long silence. changed=False when nothing is due.

    The worker should call this at `next_due_at(state, config=...)`, which already
    skips quiet hours; calling it earlier is harmless.
    """
    config = ctx.config
    due = timers.next_due_at(state, config=config)
    if due is None or now < due:
        return TurnResult(state=state, changed=False)

    state = state.model_copy(deep=True)
    started = timers.silence_started(state)
    if now >= started + config.abandon_after:
        event = Event(
            type="status_changed",
            at=now,
            data={"from": "in_progress", "to": "abandoned", "stage": state.stage.value},
        )
        state.status = Status.ABANDONED  # the stage stays, for drop-off analytics
        result = TurnResult(state=state, events=[event])
        _write_summary(result, now, ctx)
        return result

    timezone = ZoneInfo(candidate_timezone(state, config))
    originally_due = started + config.reminder_schedule[state.reminders_sent]
    events: list[Event] = []
    if timers.is_quiet(originally_due, config.quiet_hours, timezone):
        events.append(
            Event(type="reminder_deferred", at=now, data={"due_at": originally_due.isoformat()})
        )
    # After a night's wait several reminders may be due: send one, count them all.
    number = timers.reminders_due(state, now, config)
    state.reminders_sent = number
    reminder = OutboundMessage(
        text=messages.for_state(f"reminder_{number}", state), kind="reminder"
    )
    events.append(Event(type="reminder_sent", at=now, data={"number": number}))
    return _reply(state, [reminder], events, now, ctx)


def next_due_at(state: ConversationState, *, config: ScreeningConfig) -> datetime | None:
    """When the worker should next call handle_tick (None: never). Quiet hours included."""
    return timers.next_due_at(state, config=config)


def _fixed(reply: FixedReply, state: ConversationState, ctx: EngineContext) -> OutboundMessage:
    if reply.key == "readback":
        text = messages.readback(state, ctx.config)
    else:
        text = messages.for_state(reply.key, state, **reply.values)
    return OutboundMessage(text=text, kind=reply.kind)


def _write_summary(result: TurnResult, now: datetime, ctx: EngineContext) -> None:
    """Set the recruiter note once the screening has ended. Never blocks the close."""
    state = result.state
    if state.status is Status.OPTED_OUT:
        # Consent was refused or withdrawn: the conversation goes to no other model.
        state.summary = f"Opted out at stage {state.stage.value}."
        return
    try:
        summary = summarize(state, llm=ctx.llm)
    except LLMError as error:
        state.summary = None
        result.events.append(Event(type="llm_error", at=now, data={"error": str(error)}))
        return
    state.summary = summary.value
    result.events.append(_llm_call("summary", summary, now))


def _reply(
    state: ConversationState,
    outbound: list[OutboundMessage],
    events: list[Event],
    now: datetime,
    ctx: EngineContext,
) -> TurnResult:
    _record_outbound(state, outbound, now, ctx.config)
    return TurnResult(state=state, outbound=outbound, events=events)


def _record_outbound(
    state: ConversationState,
    outbound: list[OutboundMessage],
    now: datetime,
    config: ScreeningConfig,
) -> None:
    for message in outbound:
        _append(state, "agent", message.text, now, config)
    if outbound:
        state.last_outbound_at = now


def _append(
    state: ConversationState,
    role: Literal["candidate", "agent"],
    text: str,
    at: datetime,
    config: ScreeningConfig,
    message_id: str | None = None,
) -> None:
    state.transcript_tail.append(TranscriptLine(role=role, text=text, at=at, message_id=message_id))
    del state.transcript_tail[: -config.transcript_tail_size]


def _llm_call(purpose: str, result: LLMResult, now: datetime) -> Event:
    return Event(type="llm_call", at=now, data={"purpose": purpose, **result.usage.model_dump()})
