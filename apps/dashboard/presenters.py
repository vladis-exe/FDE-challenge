"""Turn engine state into what the recruiter sees. Read-only; no decisions are made here.

Every view reads candidate data through `screening.record.final_record`, so the queue, the
detail page and the CSV export always agree with the stored record. Which fields exist, and
how each one is shown, comes from the conversation's vacancy config (CONTRACTS §7).
"""

from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Any

from apps.candidates.models import Conversation
from apps.messaging.services import engine_context
from screening.config import FieldSpec, VacancyConfig
from screening.messages import display_name
from screening.record import final_record
from screening.schemas import ConversationState
from screening.scoring import score_breakdown

# Field names read better with a recruiter's word; any other field is titled from its name.
FIELD_TITLES = {"full_name": "Name", "location": "City", "start_date": "Start date"}
PLATFORM_LABELS = {
    "glovo": "Glovo",
    "uber_eats": "Uber Eats",
    "just_eat": "Just Eat",
    "rappi": "Rappi",
    "didi_food": "DiDi Food",
    "other": "Other",
}
STAGE_LABELS = {"consent": "Consent", "confirm": "Read-back", "done": "Done"}


def vacancies() -> dict[str, VacancyConfig]:
    return engine_context().config.vacancies


def vacancy_title(vacancy_id: str) -> str:
    vacancy = vacancies().get(vacancy_id)
    return vacancy.title["en"] if vacancy else vacancy_id


def field_title(name: str) -> str:
    """ "has_driver_license" -> "Driver license"; the dashboard is in English."""
    if name in FIELD_TITLES:
        return FIELD_TITLES[name]
    return name.removeprefix("has_").replace("_", " ").capitalize()


def where(conversation: Conversation) -> str:
    """The step an in-progress (or abandoned) screening is at, e.g. "City"."""
    field = conversation.state.get("current_field")
    if conversation.stage == "collecting" and field:
        return field_title(field)
    return STAGE_LABELS.get(conversation.stage, conversation.stage)


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


def option_choices(field: str) -> list[tuple[str, str]]:
    """Every option of the enum_multi field `field`, across vacancies, for a queue filter."""
    choices: dict[str, str] = {}
    for vacancy in vacancies().values():
        for spec in vacancy.fields:
            if spec.name == field and spec.options:
                for option in spec.options:
                    choices.setdefault(option, option_label(spec, option))
    return list(choices.items())


def record_for(conversation: Conversation) -> dict[str, Any]:
    """The stored final record, or the same shape built from the current state."""
    if conversation.final_record:
        return conversation.final_record
    return final_record(ConversationState.model_validate(conversation.state))


def candidate_name(conversation: Conversation, record: dict[str, Any]) -> str:
    """The name as the read-back shows it ("nuria vidal roca" -> "Nuria Vidal Roca").

    Display only: the record and `Candidate.name` keep what the candidate typed.
    """
    return display_name(record["fields"].get("full_name") or conversation.candidate.name or "")


def option_label(spec: FieldSpec, option: str) -> str:
    label = spec.option_labels.get(option, {}).get("en") or option.replace("_", " ")
    return label[:1].upper() + label[1:]


def display(spec: FieldSpec | None, value: Any) -> str:
    """A field value as stored in JSON (record or state), as text for a recruiter."""
    if value is None:
        return ""
    kind = spec.type if spec else None
    if spec and spec.name == "full_name":
        return display_name(value)
    if kind == "boolean":
        return "Yes" if value else "No"
    if kind == "city":
        return f"{city_names().get(value['city'], value['city'])}, {value['country']}"
    if kind == "enum_multi":
        return ", ".join(option_label(spec, option) for option in value)
    if kind == "experience":
        if not value:
            return "None"
        return ", ".join(
            f"{PLATFORM_LABELS.get(item['platform'], item['platform'])} {item['years']:g}y"
            for item in value
        )
    if kind == "date":
        return date.fromisoformat(value).strftime("%a %d %b %Y")
    return str(value)


def _spec(vacancy: VacancyConfig | None, name: str) -> FieldSpec | None:
    if vacancy is None:
        return None
    return next((spec for spec in vacancy.fields if spec.name == name), None)


@dataclass
class Row:
    conversation: Conversation
    name: str
    vacancy: str
    where: str
    city: str
    availability: str
    schedule: str
    start_date: date | None
    flag_count: int

    @property
    def score_label(self) -> str:
        return f"{self.conversation.preference_score:g}"


def row(conversation: Conversation) -> Row:
    record = record_for(conversation)
    fields = record["fields"]
    vacancy = vacancies().get(conversation.vacancy_id)
    start = fields.get("start_date")
    return Row(
        conversation=conversation,
        name=candidate_name(conversation, record) or "—",
        vacancy=vacancy_title(conversation.vacancy_id),
        where=where(conversation) if conversation.status in ("in_progress", "abandoned") else "",
        city=city_names().get(conversation.city, ""),
        availability=display(_spec(vacancy, "availability"), fields.get("availability")),
        schedule=display(_spec(vacancy, "schedule"), fields.get("schedule")),
        start_date=date.fromisoformat(start) if start else None,
        flag_count=len(record["flags"]) + len(record["review_reasons"]),
    )


@dataclass
class FieldLine:
    label: str
    requirement: str  # required / preferred
    value: str
    status: str  # missing / accepted / flagged
    note: str | None
    source_message_id: str | None
    weight: float = 0.0  # preferred fields: what an accepted, matching answer is worth
    points: float | None = None  # preferred fields: what this answer scored

    @property
    def weight_label(self) -> str:
        return f"{self.weight:g}"

    @property
    def points_label(self) -> str:
        return f"+{self.points or 0:g}"


def field_lines(state: ConversationState, vacancy: VacancyConfig) -> list[FieldLine]:
    """One line per field the vacancy asks, in asking order, with provenance and scoring."""
    data = state.model_dump(mode="json")["profile"]["fields"]
    points = score_breakdown(vacancy, state.profile.fields)
    lines = []
    for spec in vacancy.asked:
        field = data.get(spec.name, {})
        lines.append(
            FieldLine(
                label=field_title(spec.name),
                requirement=spec.requirement,
                value=display(spec, field.get("value")),
                status=field.get("status", "missing"),
                note=field.get("note"),
                source_message_id=field.get("source_message_id"),
                weight=spec.weight,
                points=points.get(spec.name),
            )
        )
    return lines
