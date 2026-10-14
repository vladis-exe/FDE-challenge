"""Fixed messages (prompts/messages.yaml) and the read-back of stored answers.

Everything here is deterministic: the same state always gives the same text.
"""

from datetime import date
from functools import cache
from typing import Literal

import yaml

from screening.config import FieldSpec, ScreeningConfig
from screening.fields import typed
from screening.locale import candidate_country
from screening.prompts import PROMPTS_DIR
from screening.schemas import ConversationState, FieldStatus

Language = Literal["es", "en"]
Country = Literal["ES", "MX"]

PLATFORM_LABELS = {
    "glovo": "Glovo",
    "uber_eats": "Uber Eats",
    "just_eat": "Just Eat",
    "rappi": "Rappi",
    "didi_food": "DiDi Food",
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
        "no": "no",
        "and": "y",
        "years": "años",
        "year": "año",
        "months": "meses",
        "month": "mes",
        "other": "otra plataforma",
        "without": "sin",
        "review": "lo revisará un reclutador",
    },
    "en": {
        "yes": "yes",
        "no": "no",
        "and": "and",
        "years": "years",
        "year": "year",
        "months": "months",
        "month": "month",
        "other": "another platform",
        "without": "no",
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


NAME_FIELD = "full_name"  # Alex uses the first name when the vacancy asks for one


def first_name(state: ConversationState) -> str | None:
    name = state.profile.fields.get(NAME_FIELD)
    return display_name(name.value).split()[0] if name and name.value else None


def display_name(name: str) -> str:
    """How a name typed in lowercase ("carlos méndez") is shown in fixed text.

    Only all-lowercase input is changed, and only for display: the stored value
    stays as typed, and a name with its own capitals ("María de la Fuente") is kept.
    """
    return name.title() if name == name.lower() else name


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
    vacancy = config.vacancy(state.vacancy_id)
    return for_state(
        "opening",
        state,
        job=vacancy.title[state.language].lower(),
        questions=str(len(vacancy.asked)),
        privacy_url=config.privacy_url,
    )


def readback(state: ConversationState, config: ScreeningConfig) -> str:
    return for_state("readback", state, summary=summarize(state, config))


def summarize(state: ConversationState, config: ScreeningConfig) -> str:
    """One line with every stored answer, in the candidate's language and field order.

    Rendered by code so the read-back can never misstate a value.
    """
    language = state.language
    locale = f"{language}_{candidate_country(state)}"
    words = WORDS[language]
    parts: list[str] = []
    for spec in config.vacancy(state.vacancy_id).asked:
        field = state.profile.fields.get(spec.name)
        if field is None or field.status is FieldStatus.MISSING:
            continue
        intro = localized(spec.summary, locale, language)
        if field.status is FieldStatus.FLAGGED:
            if (
                spec.type == "boolean"
            ):  # an unclear yes/no is worth naming; others are just left out
                parts.append(f"{intro or spec.name}: {words['review']}")
            continue
        value = typed(spec, field.value)
        if spec.type == "text":
            parts.append(display_name(value))
        elif spec.type == "boolean":
            parts.append(f"{intro or spec.name}: {words['yes' if value else 'no']}")
        elif spec.type == "city":
            parts.append(_city_name(config, value.country, value.city))
        elif spec.type == "enum_multi":
            parts.append(
                _join([_option(spec, option, locale, language) for option in value], words)
            )
        elif spec.type == "experience":
            if not value:
                parts.append(f"{words['without']} {intro}".strip())
            for item in value:
                platform = PLATFORM_LABELS.get(item.platform, words["other"])
                parts.append(f"{platform} {_years(item.years, language)}")
        elif spec.type == "date":
            parts.append(f"{intro} {_date(value, language)}".strip())
    return ", ".join(parts)


def localized(texts: dict[str, str], locale: str, language: Language) -> str:
    """The country variant ("es_MX") if there is one, else the language ("es")."""
    return texts.get(locale) or texts.get(language) or ""


def _option(spec: FieldSpec, option: str, locale: str, language: Language) -> str:
    return localized(spec.option_labels.get(option, {}), locale, language) or option


def _city_name(config: ScreeningConfig, country: Country, key: str) -> str:
    return next(city.name for city in config.service_areas[country].cities if city.key == key)


def _join(items: list[str], words: dict[str, str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {words['and']} {items[-1]}"


def _years(years: float, language: Language) -> str:
    if years < 1:  # "6 meses" reads better than "0,5 años"
        months = max(1, round(years * 12))
        unit = WORDS[language]["month" if months == 1 else "months"]
        return f"{months} {unit}"
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
