"""The final candidate record (CONTRACTS.md §2, v4): deterministic, no LLM.

Every field the vacancy asked, required or preferred, is reported under "fields"
by name, but only once accepted: a missing field is simply absent, and a flagged
one is listed under "flags" with its note for the recruiter.
"""

from typing import Any

from screening.schemas import ConversationState, FieldStatus


def final_record(state: ConversationState) -> dict[str, Any]:
    fields = state.profile.fields
    return {
        "conversation_id": state.conversation_id,
        "vacancy_id": state.vacancy_id,
        "status": state.status.value,
        "language": state.language,
        "fields": {
            name: value.model_dump(mode="json")["value"]
            for name, value in fields.items()
            if value.status is FieldStatus.ACCEPTED
        },
        "flags": [
            {"field": name, "note": value.note}
            for name, value in fields.items()
            if value.status is FieldStatus.FLAGGED
        ],
        "disqualify_reason": state.disqualify_reason,
        "review_reasons": list(state.review_reasons),
        "summary": state.summary,
        "preference_score": state.preference_score,
    }
