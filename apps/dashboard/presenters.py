"""Turn engine state into what the recruiter sees. Read-only; no decisions are made here.

Every view reads candidate data through `screening.record.final_record`, so the queue, the
detail page and the CSV export always agree with the stored record.
"""

from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Any

from apps.candidates.models import Conversation
from apps.messaging.services import engine_context
from screening.record import final_record
from screening.schemas import ConversationState

FIELD_LABELS = {
    "full_name": "Name",
    "has_driver_license": "Driver's license",
    "location": "City",
    "availability": "Availability",
    "schedule": "Schedule",
    "experience": "Experience",
    "start_date": "Start date",
}
OPTION_LABELS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "weekends": "Weekends",
    "morning": "Morning",
    "afternoon": "Afternoon",
    "evening": "Evening",
    "flexible": "Flexible",
}
PLATFORM_LABELS = {
    "glovo": "Glovo",
    "uber_eats": "Uber Eats",
    "just_eat": "Just Eat",
    "rappi": "Rappi",
    "didi_food": "DiDi Food",
    "other": "Other",
}


@cache
def city_names() -> dict[str, str]:
    return {
        city.key: city.name
        for area in engine_context().config.service_areas.values()
        for city in area.cities
    }


def city_choices() -> list[tuple[str, str]]:
    config = engine_context().config
    return [
        (city.key, f"{city.name} ({country})")
        for country, area in config.service_areas.items()
        for city in area.cities
    ]


def record_for(conversation: Conversation) -> dict[str, Any]:
    """The stored final record, or the same shape built from the current state."""
    if conversation.final_record:
        return conversation.final_record
    return final_record(ConversationState.model_validate(conversation.state))


def options(values: list[str] | None) -> str:
    return ", ".join(OPTION_LABELS.get(value, value) for value in values or [])


def experience(items: list[dict] | None) -> str:
    if items is None:
        return ""
    if not items:
        return "None"
    return ", ".join(
        f"{PLATFORM_LABELS.get(item['platform'], item['platform'])} {item['years']:g}y"
        for item in items
    )


@dataclass
class Row:
    conversation: Conversation
    name: str
    city: str
    availability: str
    schedule: str
    experience: str
    start_date: date | None
    flag_count: int


def row(conversation: Conversation) -> Row:
    record = record_for(conversation)
    return Row(
        conversation=conversation,
        name=conversation.candidate.name or record["full_name"] or "—",
        city=city_names().get(record["city"] or conversation.city, ""),
        availability=options(record["availability"]),
        schedule=options(record["preferred_schedule"]),
        experience=experience(record["delivery_experience"]),
        start_date=date.fromisoformat(record["start_date"]) if record["start_date"] else None,
        flag_count=len(record["flags"]) + len(record["review_reasons"]),
    )


@dataclass
class FieldLine:
    label: str
    value: str
    status: str  # missing / accepted / flagged
    note: str | None
    source_message_id: str | None


def field_lines(state: ConversationState) -> list[FieldLine]:
    """One line per profile field, accepted or not, with its provenance."""
    lines = []
    for name, label in FIELD_LABELS.items():
        field = getattr(state.profile, name)
        lines.append(
            FieldLine(
                label=label,
                value=_display(name, field.value) if field.value is not None else "",
                status=field.status.value,
                note=field.note,
                source_message_id=field.source_message_id,
            )
        )
    return lines


def _display(name: str, value: Any) -> str:
    if name == "has_driver_license":
        return "Yes" if value else "No"
    if name == "location":
        return f"{city_names().get(value.city, value.city)}, {value.country}"
    if name in ("availability", "schedule"):
        return options([option.value for option in value])
    if name == "experience":
        return experience([item.model_dump() for item in value])
    if name == "start_date":
        return value.strftime("%a %d %b %Y")
    return str(value)
