from datetime import date

from screening.record import final_record
from screening.schemas import (
    Availability,
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    Location,
    Schedule,
    Status,
)


def accepted(field, value):
    field.value = value
    field.status = FieldStatus.ACCEPTED


def test_final_record_matches_the_contract_example():
    state = ConversationState(conversation_id="c1", channel=Channel.WHATSAPP)
    state.status = Status.NEEDS_REVIEW
    profile = state.profile
    accepted(profile.full_name, "Laura Pérez")
    accepted(profile.has_driver_license, True)
    accepted(profile.location, Location(country="ES", city="barcelona"))
    accepted(profile.availability, [Availability.PART_TIME, Availability.WEEKENDS])
    accepted(profile.schedule, [Schedule.EVENING])
    accepted(profile.experience, [ExperienceItem(platform="glovo", years=1.5)])
    profile.start_date.status = FieldStatus.FLAGGED
    profile.start_date.note = "unresolved after 2 re-asks"
    state.review_reasons = ["unresolved:start_date"]
    state.summary = "Resumen."

    assert final_record(state) == {
        "conversation_id": "c1",
        "status": "needs_review",
        "language": "es",
        "full_name": "Laura Pérez",
        "has_driver_license": True,
        "country": "ES",
        "city": "barcelona",
        "availability": ["part_time", "weekends"],
        "preferred_schedule": ["evening"],
        "delivery_experience": [{"platform": "glovo", "years": 1.5}],
        "start_date": None,
        "flags": [{"field": "start_date", "note": "unresolved after 2 re-asks"}],
        "disqualify_reason": None,
        "review_reasons": ["unresolved:start_date"],
        "summary": "Resumen.",
    }


def test_unasked_fields_are_null_and_no_experience_is_an_empty_list():
    state = ConversationState(conversation_id="c2", channel=Channel.SIM)
    accepted(state.profile.experience, [])
    accepted(state.profile.start_date, date(2026, 10, 19))
    record = final_record(state)
    assert record["full_name"] is None
    assert record["country"] is None
    assert record["availability"] is None
    assert record["delivery_experience"] == []
    assert record["start_date"] == "2026-10-19"
    assert record["flags"] == []


def test_a_partial_name_waiting_for_its_surname_is_not_reported():
    state = ConversationState(conversation_id="c3", channel=Channel.SIM)
    state.profile.full_name.value = "Laura"  # status still MISSING
    assert final_record(state)["full_name"] is None
