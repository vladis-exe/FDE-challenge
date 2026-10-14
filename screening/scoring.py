"""The preference score (CONTRACTS.md §7): a tie-breaker, never a qualification gate.

It only orders candidates who are already in the same outcome. Only accepted
`preferred` fields count, by one fixed formula per field type, and the breakdown
is kept so a recruiter sees exactly which fields contributed and how much.
"""

from screening.config import VacancyConfig
from screening.fields import typed
from screening.schemas import FieldStatus, FieldValue

EXPERIENCE_YEARS_CAP = 5  # so one candidate's 20 years doesn't swamp everything else


def score_breakdown(vacancy: VacancyConfig, fields: dict[str, FieldValue]) -> dict[str, float]:
    """Points per preferred field (0 when it didn't score)."""
    points: dict[str, float] = {}
    for spec in vacancy.fields:
        if spec.requirement != "preferred":
            continue
        field = fields.get(spec.name)
        value = typed(spec, field.value) if field and field.status is FieldStatus.ACCEPTED else None
        if spec.type == "boolean":
            points[spec.name] = spec.weight if value is True else 0.0
        elif spec.type == "enum_multi":
            points[spec.name] = spec.weight if value else 0.0
        elif spec.type == "experience":
            years = sum(item.years for item in value or [])
            points[spec.name] = spec.weight * min(years, EXPERIENCE_YEARS_CAP)
        else:
            points[spec.name] = 0.0  # date: no formula yet
    return points


def preference_score(vacancy: VacancyConfig, fields: dict[str, FieldValue]) -> float:
    return round(sum(score_breakdown(vacancy, fields).values()), 2)
