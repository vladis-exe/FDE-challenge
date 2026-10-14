from datetime import date

from screening.record import final_record
from screening.schemas import (
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    FieldValue,
    Location,
    Status,
)


def accepted(value) -> FieldValue:
    return FieldValue(value=value, status=FieldStatus.ACCEPTED)


def test_final_record_matches_the_contract_example():
    state = ConversationState(conversation_id="c1", channel=Channel.WHATSAPP, vacancy_id="driver")
    state.status = Status.NEEDS_REVIEW
    state.profile.fields = {
        "full_name": accepted("Laura Pérez"),
        "has_driver_license": accepted(True),
        "location": accepted(Location(country="ES", city="barcelona")),
        "availability": accepted(["part_time", "weekends"]),
        "schedule": accepted(["evening"]),
        "experience": accepted([ExperienceItem(platform="glovo", years=1.5)]),
        "start_date": FieldValue(status=FieldStatus.FLAGGED, note="unresolved after 2 re-asks"),
    }
    state.review_reasons = ["unresolved:start_date"]
    state.summary = "Resumen."

    assert final_record(state) == {
        "conversation_id": "c1",
        "vacancy_id": "driver",
        "status": "needs_review",
        "language": "es",
        "fields": {
            "full_name": "Laura Pérez",
            "has_driver_license": True,
            "location": {"country": "ES", "city": "barcelona"},
            "availability": ["part_time", "weekends"],
            "schedule": ["evening"],
            "experience": [{"platform": "glovo", "years": 1.5}],
        },
        "flags": [{"field": "start_date", "note": "unresolved after 2 re-asks"}],
        "disqualify_reason": None,
        "review_reasons": ["unresolved:start_date"],
        "summary": "Resumen.",
        "preference_score": 0.0,
    }


def test_missing_fields_are_absent_and_no_experience_is_an_empty_list():
    state = ConversationState(conversation_id="c2", channel=Channel.SIM, vacancy_id="driver")
    state.profile.fields = {
        "experience": accepted([]),
        "start_date": accepted(date(2026, 10, 19)),
        "full_name": FieldValue(value="Laura"),  # a partial name waiting for its surname
    }
    record = final_record(state)
    assert record["fields"] == {"experience": [], "start_date": "2026-10-19"}
    assert record["flags"] == []


def test_preferred_fields_and_the_score_are_reported():
    state = ConversationState(conversation_id="c3", channel=Channel.SIM, vacancy_id="kitchen_prep")
    state.profile.fields = {"has_driver_license": accepted(False)}
    state.preference_score = 1.0
    record = final_record(state)
    assert record["fields"] == {"has_driver_license": False}
    assert record["preference_score"] == 1.0
