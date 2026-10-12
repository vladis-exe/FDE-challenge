"""Fixed messages (prompts/messages.yaml) and the read-back of stored answers.

Everything here is deterministic: the same state always gives the same text.
"""

from datetime import date
from functools import cache
from typing import Literal

import yaml

from screening.config import ScreeningConfig
from screening.locale import candidate_country
from screening.prompts import PROMPTS_DIR
from screening.schemas import CandidateProfile, ConversationState, FieldStatus

Language = Literal["es", "en"]
Country = Literal["ES", "MX"]

AVAILABILITY_LABELS = {
    "es_ES": {
        "full_time": "jornada completa",
        "part_time": "media jornada",
        "weekends": "fines de semana",
    },
    "es_MX": {
        "full_time": "tiempo completo",
        "part_time": "medio tiempo",
        "weekends": "fines de semana",
    },
    "en": {"full_time": "full-time", "part_time": "part-time", "weekends": "weekends"},
}
SCHEDULE_LABELS = {
    "es": {
        "morning": "mañanas",
        "afternoon": "tardes",
        "evening": "noches",
        "flexible": "horario flexible",
    },
    "en": {
        "morning": "mornings",
        "afternoon": "afternoons",
        "evening": "evenings",
        "flexible": "flexible hours",
    },
}
PLATFORM_LABELS = {
    "glovo": "Glovo",
    "uber_eats": "Uber Eats",
    "just_eat": "Just Eat",
    "rappi": "Rappi",
    "didi_food": "DiDi Food",
}
LICENSE_LABELS = {
    "es_ES": "carnet de conducir",
    "es_MX": "licencia de manejo",
    "en": "driver's license",
}
WEEKDAYS = {
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
MONTHS = {
    "es": [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}
WORDS = {
    "es": {
        "yes": "sí",
        "and": "y",
        "years": "años",
        "year": "año",
        "other": "otra plataforma",
        "no_experience": "sin experiencia en reparto",
        "start": "empiezas el",
        "review": "lo revisará un reclutador",
    },
    "en": {
        "yes": "yes",
        "and": "and",
        "years": "years",
        "year": "year",
        "other": "another platform",
        "no_experience": "no delivery experience",
        "start": "starting",
        "review": "a recruiter will check this",
    },
}


@cache
def _catalogue() -> dict[str, dict[str, str]]:
    with (PROMPTS_DIR / "messages.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fixed(
    key: str, *, language: Language, country: Country, first_name: str | None = None, **values: str
) -> str:
    variants = _catalogue()[key]
    template = variants.get(f"{language}_{country}") or variants[language]
    name = f", {first_name}" if first_name else ""
    return template.format(name=name, **values)


def first_name(state: ConversationState) -> str | None:
    full_name = state.profile.full_name.value
    return full_name.split()[0] if full_name else None


def for_state(key: str, state: ConversationState, **values: str) -> str:
    """A fixed message in the conversation's current language and country."""
    return fixed(
        key,
        language=state.language,
        country=candidate_country(state),
        first_name=first_name(state),
        **values,
    )


def opening(state: ConversationState, config: ScreeningConfig) -> str:
    return for_state("opening", state, privacy_url=config.privacy_url)


def readback(state: ConversationState, config: ScreeningConfig) -> str:
    return for_state("readback", state, summary=summarize(state, config))


def summarize(state: ConversationState, config: ScreeningConfig) -> str:
    """One line with every stored answer, in the candidate's language.

    Rendered by code so the read-back can never misstate a value.
    """
    language = state.language
    country = candidate_country(state)
    locale = f"{language}_{country}" if language == "es" else "en"
    words = WORDS[language]
    profile: CandidateProfile = state.profile
    parts: list[str] = []

    if profile.full_name.value:
        parts.append(profile.full_name.value)

    license_label = LICENSE_LABELS[locale]
    if profile.has_driver_license.status is FieldStatus.FLAGGED:
        parts.append(f"{license_label}: {words['review']}")
    elif profile.has_driver_license.value:
        parts.append(f"{license_label}: {words['yes']}")

    if profile.location.value:
        location = profile.location.value
        parts.append(_city_name(config, location.country, location.city))

    if profile.availability.value:
        labels = AVAILABILITY_LABELS[locale]
        parts.append(_join([labels[option] for option in profile.availability.value], words))

    if profile.schedule.value:
        labels = SCHEDULE_LABELS[language]
        parts.append(_join([labels[option] for option in profile.schedule.value], words))

    if profile.experience.status is FieldStatus.ACCEPTED:
        items = profile.experience.value or []
        if not items:
            parts.append(words["no_experience"])
        for item in items:
            platform = PLATFORM_LABELS.get(item.platform, words["other"])
            parts.append(f"{platform} {_years(item.years, language)}")

    if profile.start_date.value:
        parts.append(f"{words['start']} {_date(profile.start_date.value, language)}")

    return ", ".join(parts)


def _city_name(config: ScreeningConfig, country: Country, key: str) -> str:
    return next(city.name for city in config.service_areas[country].cities if city.key == key)


def _join(items: list[str], words: dict[str, str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {words['and']} {items[-1]}"


def _years(years: float, language: Language) -> str:
    number = f"{years:g}"
    if language == "es":
        number = number.replace(".", ",")
    unit = WORDS[language]["year" if years == 1 else "years"]
    return f"{number} {unit}"


def _date(day: date, language: Language) -> str:
    weekday = WEEKDAYS[language][day.weekday()]
    month = MONTHS[language][day.month - 1]
    if language == "es":
        return f"{weekday} {day.day} de {month}"
    return f"{weekday} {day.day} {month}"
