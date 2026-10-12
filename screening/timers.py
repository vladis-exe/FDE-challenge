"""Reminders, quiet hours and abandonment. Pure functions of state, config and `now`.

Silence is measured from the candidate's last message (or from the opening, if
they never replied). Reminders go out at each `reminder_schedule` offset, but
never during quiet hours in the candidate's time zone: a reminder due at night
waits until quiet hours end, and if several came due meanwhile, only one is sent.
After `abandon_after` the conversation is abandoned, silently, at any hour.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from screening.config import QuietHours, ScreeningConfig
from screening.locale import candidate_timezone
from screening.schemas import ConversationState, Status


def silence_started(state: ConversationState) -> datetime | None:
    if state.last_inbound_at:
        return state.last_inbound_at
    # Never replied: the first line is the opening (the tail holds at most the
    # opening and the reminders, well under its size limit).
    return state.transcript_tail[0].at if state.transcript_tail else None


def next_due_at(state: ConversationState, *, config: ScreeningConfig) -> datetime | None:
    """When handle_tick next has something to do, or None if it never will."""
    started = silence_started(state)
    if state.status is not Status.IN_PROGRESS or started is None:
        return None
    abandon_at = started + config.abandon_after
    if state.reminders_sent >= len(config.reminder_schedule):
        return abandon_at
    reminder_at = started + config.reminder_schedule[state.reminders_sent]
    timezone = ZoneInfo(candidate_timezone(state, config))
    return min(outside_quiet_hours(reminder_at, config.quiet_hours, timezone), abandon_at)


def reminders_due(state: ConversationState, now: datetime, config: ScreeningConfig) -> int:
    """How many reminders of the schedule are due by `now` (sent or not)."""
    started = silence_started(state)
    return sum(1 for offset in config.reminder_schedule if started + offset <= now)


def is_quiet(moment: datetime, quiet: QuietHours, timezone: ZoneInfo) -> bool:
    local = moment.astimezone(timezone).time()
    if quiet.start <= quiet.end:
        return quiet.start <= local < quiet.end
    return local >= quiet.start or local < quiet.end  # the window wraps midnight


def outside_quiet_hours(moment: datetime, quiet: QuietHours, timezone: ZoneInfo) -> datetime:
    """`moment` itself, or the end of the quiet window it falls in."""
    if not is_quiet(moment, quiet, timezone):
        return moment
    local = moment.astimezone(timezone)
    end_day = local.date()
    if quiet.start > quiet.end and local.time() >= quiet.start:
        end_day += timedelta(days=1)  # evening part of a window that ends tomorrow morning
    return _at(end_day, quiet.end, timezone).astimezone(moment.tzinfo)


def _at(day, at: time, timezone: ZoneInfo) -> datetime:
    return datetime.combine(day, at, tzinfo=timezone)
