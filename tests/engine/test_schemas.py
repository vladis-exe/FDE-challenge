from datetime import UTC, datetime

from screening.config import load_config
from screening.fields import typed
from screening.schemas import (
    Channel,
    ConversationState,
    FieldStatus,
    FieldValue,
    Location,
    Stage,
    Status,
)

DRIVER = load_config().vacancy("driver")


def make_state() -> ConversationState:
    return ConversationState(conversation_id="c1", channel=Channel.WHATSAPP, vacancy_id="driver")


def test_new_state_defaults():
    state = make_state()
    assert state.status is Status.IN_PROGRESS
    assert state.stage is Stage.CONSENT
    assert state.current_field is None
    assert state.profile.fields == {}
    assert state.review_reasons == []
    assert state.preference_score == 0.0
    assert state.schema_version == 2


def test_defaults_are_not_shared_between_instances():
    first, second = make_state(), make_state()
    first.profile.fields["full_name"] = FieldValue(value="Laura Pérez")
    first.review_reasons.append("abuse")
    assert second.profile.fields == {}
    assert second.review_reasons == []


def test_state_round_trips_through_json_and_values_come_back_typed():
    """The app stores state as JSON (model_dump(mode="json")) and reloads it every turn."""
    state = make_state()
    state.stage = Stage.COLLECTING
    state.current_field = "start_date"
    state.profile.fields["location"] = FieldValue(
        value=Location(country="ES", city="barcelona"), status=FieldStatus.ACCEPTED
    )
    state.profile.fields["start_date"] = FieldValue(value="2026-10-19", source_message_id="m42")
    state.consent_at = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)

    reloaded = ConversationState.model_validate(state.model_dump(mode="json"))

    assert reloaded.model_dump(mode="json") == state.model_dump(mode="json")
    assert reloaded.current_field == "start_date"
    # FieldValue[Any] reloads plain JSON; the field type restores the real value.
    location = reloaded.profile.fields["location"].value
    assert typed(DRIVER.field("location"), location) == Location(country="ES", city="barcelona")
