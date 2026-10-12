"""The final candidate record (CONTRACTS.md §2): deterministic, no LLM.

Only accepted values are reported; a flagged or missing field is null and the
flag (with its note) is listed under "flags" for the recruiter.
"""

from typing import Any

from screening.schemas import ConversationState, FieldStatus, FieldValue


def final_record(state: ConversationState) -> dict[str, Any]:
    profile = state.profile
    location = _accepted(profile.location)
    experience = _accepted(profile.experience)
    start_date = _accepted(profile.start_date)
    fields = {
        "full_name": profile.full_name,
        "has_driver_license": profile.has_driver_license,
        "location": profile.location,
        "availability": profile.availability,
        "schedule": profile.schedule,
        "experience": profile.experience,
        "start_date": profile.start_date,
    }
    return {
        "conversation_id": state.conversation_id,
        "status": state.status.value,
        "language": state.language,
        "full_name": _accepted(profile.full_name),
        "has_driver_license": _accepted(profile.has_driver_license),
        "country": location.country if location else None,
        "city": location.city if location else None,
        "availability": _values(_accepted(profile.availability)),
        "preferred_schedule": _values(_accepted(profile.schedule)),
        "delivery_experience": (
            [item.model_dump() for item in experience] if experience is not None else None
        ),
        "start_date": start_date.isoformat() if start_date else None,
        "flags": [
            {"field": name, "note": value.note}
            for name, value in fields.items()
            if value.status is FieldStatus.FLAGGED
        ],
        "disqualify_reason": state.disqualify_reason,
        "review_reasons": list(state.review_reasons),
        "summary": state.summary,
    }


def _accepted(field: FieldValue) -> Any:
    return field.value if field.status is FieldStatus.ACCEPTED else None


def _values(options: list | None) -> list[str] | None:
    return [option.value for option in options] if options is not None else None
