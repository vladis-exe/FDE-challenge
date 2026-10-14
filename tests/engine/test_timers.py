from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from screening.config import load_config
from screening.engine import EngineContext, handle_tick, new_conversation, next_due_at, start
from screening.llm import FakeLLM
from screening.schemas import Channel, ConversationState, FieldValue, Stage, Status

MADRID = ZoneInfo("Europe/Madrid")
MEXICO = ZoneInfo("America/Mexico_City")


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.delenv("DEMO_TIME_SCALE", raising=False)
    return EngineContext(config=load_config(), llm=FakeLLM({"summary": ["Abandonada."]}))


def silent_since(ctx, at: datetime, phone="+34600000000", replied=True) -> ConversationState:
    """A conversation whose candidate last wrote at `at` (or got the opening then)."""
    state = new_conversation(
        "c1", Channel.WHATSAPP, vacancy_id="driver", phone=phone, language="es", now=at
    )
    state = start(state, now=at, ctx=ctx).state
    if replied:
        state.stage = Stage.COLLECTING
        state.current_field = "location"
        state.profile.fields["full_name"] = FieldValue(value="Laura Pérez")
        state.last_inbound_at = at
    return state


def tick(state, ctx, at):
    result = handle_tick(state, now=at, ctx=ctx)
    return result, result.state


def local(day: int, hour: int, minute: int = 0, zone=MADRID) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=zone)


def test_nothing_is_due_before_the_first_reminder(ctx):
    state = silent_since(ctx, local(14, 12))
    result, _ = tick(state, ctx, local(14, 12, 14))
    assert result.changed is False
    assert result.outbound == []


def test_reminders_at_15_min_2_h_and_20_h_then_abandoned(ctx):
    state = silent_since(ctx, local(14, 14))  # all three reminders fall in daytime

    first, state = tick(state, ctx, local(14, 14, 15))
    assert first.outbound[0].kind == "reminder"
    assert first.outbound[0].text.startswith("¿Sigues por ahí, Laura?")
    assert state.reminders_sent == 1
    assert [event.type for event in first.events] == ["reminder_sent"]
    assert state.last_outbound_at == local(14, 14, 15)

    assert tick(state, ctx, local(14, 15))[0].changed is False
    second, state = tick(state, ctx, local(14, 16))
    assert "te queda muy poco" in second.outbound[0].text
    third, state = tick(state, ctx, local(15, 10))
    assert "Último recordatorio" in third.outbound[0].text
    assert state.reminders_sent == 3

    abandoned, state = tick(state, ctx, local(15, 14))
    assert state.status is Status.ABANDONED
    assert (state.stage, state.current_field) == (Stage.COLLECTING, "location")  # for drop-off
    assert abandoned.outbound == []
    assert abandoned.events[0].data == {
        "from": "in_progress",
        "to": "abandoned",
        "stage": "collecting",
        "field": "location",
    }
    assert tick(state, ctx, local(16, 14))[0].changed is False


def test_last_reminder_at_dawn_waits_for_nine(ctx):
    state = silent_since(ctx, local(14, 10))
    state.reminders_sent = 2
    assert next_due_at(state, config=ctx.config) == local(15, 9)  # 20 h after 10:00 is 06:00


def test_reminder_due_at_night_waits_until_morning(ctx):
    state = silent_since(ctx, local(22, 20, 30))  # scenario 16: Thursday evening
    _, state = tick(state, ctx, local(22, 20, 45))  # 15 min reminder, before 21:00
    assert state.reminders_sent == 1

    # The 2 h reminder falls at 22:30, inside quiet hours.
    assert next_due_at(state, config=ctx.config) == local(23, 9)
    assert tick(state, ctx, local(22, 22, 30))[0].changed is False
    assert tick(state, ctx, local(23, 3))[0].changed is False

    morning, state = tick(state, ctx, local(23, 9))
    assert [event.type for event in morning.events] == ["reminder_deferred", "reminder_sent"]
    assert morning.outbound[0].kind == "reminder"


def test_several_reminders_due_overnight_send_only_one(ctx):
    state = silent_since(ctx, local(22, 20, 55))  # 15 min reminder due 21:10: quiet
    assert next_due_at(state, config=ctx.config) == local(23, 9)
    result, state = tick(state, ctx, local(23, 9))
    assert len(result.outbound) == 1
    assert state.reminders_sent == 2  # 15 min and 2 h were both due by 09:00


def test_quiet_hours_use_the_candidates_time_zone(ctx):
    # 21:30 in Madrid is 13:30 in Mexico City: a Mexican candidate gets the reminder.
    at = datetime(2026, 10, 14, 19, 15, tzinfo=UTC)
    state = silent_since(ctx, at, phone="+525500000000")
    result, _ = tick(state, ctx, at + timedelta(minutes=15))
    assert result.outbound

    spain = silent_since(ctx, at)
    assert tick(spain, ctx, at + timedelta(minutes=15))[0].changed is False


def test_abandonment_happens_even_during_quiet_hours(ctx):
    state = silent_since(ctx, local(14, 23))
    state.reminders_sent = 3
    _, state = tick(state, ctx, local(15, 23))
    assert state.status is Status.ABANDONED


def test_silence_counts_from_the_opening_when_the_candidate_never_replied(ctx):
    state = silent_since(ctx, local(14, 10), replied=False)
    _, state = tick(state, ctx, local(14, 10, 15))
    assert state.reminders_sent == 1
    # The reminder itself must not restart the clock.
    assert next_due_at(state, config=ctx.config) == local(14, 12)


def test_finished_conversations_never_tick(ctx):
    state = silent_since(ctx, local(14, 10))
    state.status = Status.QUALIFIED
    assert next_due_at(state, config=ctx.config) is None
    assert tick(state, ctx, local(16, 10))[0].changed is False


def test_demo_time_scale_compresses_the_schedule(monkeypatch):
    monkeypatch.setenv("DEMO_TIME_SCALE", "60")
    ctx = EngineContext(config=load_config(), llm=FakeLLM({"summary": ["Abandonada."]}))
    state = silent_since(ctx, local(14, 12))
    assert next_due_at(state, config=ctx.config) == local(14, 12) + timedelta(seconds=15)
    _, state = tick(state, ctx, local(14, 12) + timedelta(seconds=15))
    assert state.reminders_sent == 1


def test_mexico_city_quiet_hours_end_at_local_nine(ctx):
    state = silent_since(ctx, local(14, 20, 50, zone=MEXICO), phone="+525500000000")
    assert next_due_at(state, config=ctx.config) == local(15, 9, zone=MEXICO)
