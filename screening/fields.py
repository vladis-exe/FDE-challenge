"""The field-type catalog (CONTRACTS.md §7): what each type of field accepts and stores.

Closed on purpose: adding a type is an engineering change, reviewed like any other
code that can decide an outcome. A vacancy only picks fields from these types.

For each type:
- the raw answer the LLM extracts (`raw_type`), constrained by the output schema;
- the stored value (`typed`), restored after the state's JSON round trip;
- whether a value is a knockout when the field is required (`is_knockout`).
City answers are validated in the policy (match, ask, confirm), not here.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

from screening.config import FieldSpec
from screening.schemas import ExperienceItem, Location
from screening.validators import (
    BooleanAnswer,
    RawExperience,
    StartDateAnswer,
    Verdict,
    validate_boolean,
    validate_experience,
    validate_name,
    validate_options,
    validate_start_date,
)


class ExperienceAnswer(BaseModel):
    has_experience: bool | None = None  # false = never done this work (valid, never a knockout)
    items: list[RawExperience] = []  # each platform with its duration, as given


_RAW: dict[str, Any] = {
    "text": str,
    "boolean": BooleanAnswer,
    "city": str,  # the place as written; matched in code
    "experience": ExperienceAnswer,
    "date": StartDateAnswer,
}
_VALUE: dict[str, Any] = {
    "text": str,
    "boolean": bool,
    "city": Location,
    "enum_multi": list[str],
    "experience": list[ExperienceItem],
    "date": date,
}


def raw_type(spec: FieldSpec) -> Any:
    """The shape the extractor must return for this field."""
    if spec.type == "enum_multi":
        return list[Literal[tuple(spec.options)]]  # only this field's options
    return _RAW[spec.type]


def typed(spec: FieldSpec, value: Any) -> Any:
    """A stored value as its proper type, whether fresh or reloaded from JSON."""
    if value is None:
        return None
    return TypeAdapter(_VALUE[spec.type]).validate_python(value)


def is_knockout(spec: FieldSpec, value: Any) -> bool:
    """A value that disqualifies when the field is required: a boolean "no".

    (A city outside the service area is the other knockout; the policy handles it
    because it needs the candidate's confirmation first.)
    """
    return spec.type == "boolean" and value is False


def validate(
    spec: FieldSpec, raw: Any, *, today: date, max_days: int, surname_asked: bool
) -> Verdict:
    """Check one raw answer against the rules of its field type."""
    if spec.type == "text":
        return validate_name(raw, surname_asked=surname_asked)
    if spec.type == "boolean":
        return validate_boolean(raw, name=spec.outcome_name)
    if spec.type == "enum_multi":
        return validate_options(raw, options=spec.options, exclusive=spec.exclusive_options)
    if spec.type == "experience":
        has_experience = raw.has_experience if raw.has_experience is not None else bool(raw.items)
        return validate_experience(has_experience=has_experience, items=raw.items)
    if spec.type == "date":
        return validate_start_date(raw, today=today, max_days=max_days)
    raise ValueError(f"{spec.name}: {spec.type} answers are validated by the policy")
