from datetime import UTC, date, datetime

from screening.schemas import (
    Availability,
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    Location,
    Stage,
    Status,
)


def make_state() -> ConversationState:
    return ConversationState(conversation_id="c1", channel=Channel.WHATSAPP)


def test_new_state_defaults():
    state = make_state()
    assert state.status is Status.IN_PROGRESS
    assert state.stage is Stage.CONSENT
    assert state.profile.full_name.status is FieldStatus.MISSING
    assert state.review_reasons == []


def test_defaults_are_not_shared_between_instances():
    first, second = make_state(), make_state()
    first.profile.full_name.value = "Laura Pérez"
    first.review_reasons.append("abuse")
    assert second.profile.full_name.value is None
    assert second.review_reasons == []


def test_state_round_trips_through_json():
    """The app stores state as JSON (model_dump(mode="json")) and reloads it every turn."""
    state = make_state()
    profile = state.profile
    profile.location.value = Location(country="ES", city="barcelona")
    profile.availability.value = [Availability.PART_TIME, Availability.WEEKENDS]
    profile.experience.value = [ExperienceItem(platform="glovo", years=1.5)]
    profile.start_date.value = date(2026, 10, 19)
    profile.start_date.source_message_id = "m42"
    state.consent_at = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    reloaded = ConversationState.model_validate(state.model_dump(mode="json"))

    assert reloaded == state
    assert reloaded.profile.start_date.value == date(2026, 10, 19)
    assert reloaded.profile.availability.value == [Availability.PART_TIME, Availability.WEEKENDS]
