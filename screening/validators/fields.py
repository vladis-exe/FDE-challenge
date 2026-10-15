"""Validators for every field except the city. Pure functions: value in, Verdict out.

The LLM turns messy wording into these raw shapes; the rules applied here are
the spec's ("Data fields and validation"), so they run in code, not in the prompt.
"""

import re
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from screening.schemas import ExperienceItem
from screening.validators.text import normalize
from screening.validators.verdict import Verdict

# Normalized spelling with spaces removed -> platform key.
_PLATFORMS = {
    "glovo": "glovo",
    "ubereats": "uber_eats",
    "uber": "uber_eats",
    "justeat": "just_eat",
    "rappi": "rappi",
    "didi": "didi_food",
    "didifood": "didi_food",
}
MAX_EXPERIENCE_YEARS = 40


class RawExperience(BaseModel):
    platform: str
    years: float | None = None
    months: float | None = None


class StartDateAnswer(BaseModel):
    kind: Literal["asap", "date", "vague"]
    resolved: date | None = None  # set by the LLM when kind == "date"


BooleanAnswer = Literal["yes", "no", "expired", "in_progress", "foreign", "vague"]
_UNCLEAR = {"expired": "expired", "in_progress": "in progress", "foreign": "from another country"}


def validate_boolean(answer: BooleanAnswer, *, name: str) -> Verdict[bool]:
    """Yes/no is decided. Expired, in progress or foreign goes to a recruiter, never rejected.

    `name` only words the note ("license expired"); whether a "no" disqualifies is
    the policy's call, from the field's requirement level.
    """
    if answer == "yes":
        return Verdict.accept(True)
    if answer == "no":
        return Verdict.accept(False)
    if answer == "vague":
        return Verdict.reask("not a clear yes or no")
    return Verdict.flag(f"{name} {_UNCLEAR[answer]}")


def validate_options(
    values: list[str], *, options: list[str], exclusive: list[str]
) -> Verdict[list[str]]:
    """At least one option, in display order. An exclusive option ("flexible") stands alone."""
    chosen = [option for option in options if option in values]
    alone = [option for option in chosen if option in exclusive]
    if alone:
        return Verdict.accept(alone[:1])
    if not chosen:
        return Verdict.reask("no option chosen")
    return Verdict.accept(chosen)


def validate_name(raw: str, *, surname_asked: bool) -> Verdict[str]:
    """First name plus a surname. Asks once for the surname, then accepts what was given."""
    name = " ".join(raw.split())
    words = [word for word in name.split() if any(char.isalpha() for char in word)]
    if not words:
        return Verdict.reask("no name given")
    if len(words) >= 2:
        return Verdict.accept(name)
    if not surname_asked:
        return Verdict.reask("surname missing")
    return Verdict.accept(name, note="no surname given")


def validate_experience(
    *, has_experience: bool, items: list[RawExperience]
) -> Verdict[list[ExperienceItem]]:
    """No experience is a valid answer ([]), never a knockout."""
    if not has_experience:
        return Verdict.accept([])
    if not items:
        return Verdict.reask("which platforms and for how long")

    by_platform: dict[str, float] = {}
    for item in items:
        if item.years is not None:
            years = item.years
        elif item.months is not None:
            years = item.months / 12
        else:
            return Verdict.reask(f"how long on {item.platform}")
        if not 0 <= years <= MAX_EXPERIENCE_YEARS:
            return Verdict.reask(f"implausible duration on {item.platform}")
        platform = _platform_key(item.platform)
        by_platform[platform] = max(round(years, 1), by_platform.get(platform, 0))
    return Verdict.accept(
        [ExperienceItem(platform=platform, years=years) for platform, years in by_platform.items()]
    )


def _platform_key(raw: str) -> str:
    """The known app named anywhere in the answer: "uber eats en houston" is Uber Eats.

    The platform is the app, not where they used it. Longest names first, so
    "ubereats" wins over "uber" and "didifood" over "didi".
    """
    squashed = normalize(raw).replace(" ", "")
    for alias in sorted(_PLATFORMS, key=len, reverse=True):
        if alias in squashed:
            return _PLATFORMS[alias]
    return "other"


# Relative days, by how many days after the message's local date they mean.
# "mañana" as "morning" ("por la mañana", "las mañanas") isn't matched.
_RELATIVE_DAYS = [
    (re.compile(r"\bpasado mañana\b|\bday after tomorrow\b"), 2),
    (re.compile(r"(?<!\bla )(?<!\bpasado )\bmañana\b|\btomorrow\b"), 1),
    (re.compile(r"\bhoy\b|\btoday\b"), 0),
]


def relative_day(text: str) -> int | None:
    """Days after today that a message's relative day means, if it names exactly one.

    Code does the arithmetic the model sometimes gets wrong (V9: Friday's "mañana
    mismo" stored as Friday). Two or more different days give None, so the model's
    reading stands: candidates often rule one out ("hoy no, mañana sí"), and picking
    either day in code could store the one they refused.
    """
    lowered = text.casefold()
    found = set()
    for pattern, offset in _RELATIVE_DAYS:
        if pattern.search(lowered):
            found.add(offset)
            lowered = pattern.sub(" ", lowered)  # "pasado mañana" mustn't also count as "mañana"
    return found.pop() if len(found) == 1 else None


def local_date(moment: datetime, timezone: str) -> date:
    """The candidate's calendar date at `moment` (an aware datetime)."""
    return moment.astimezone(ZoneInfo(timezone)).date()


def validate_start_date(answer: StartDateAnswer, *, today: date, max_days: int) -> Verdict[date]:
    """`today` is the candidate-local date of the message that gave the answer."""
    if answer.kind == "asap":
        return Verdict.accept(today)
    if answer.kind == "vague" or answer.resolved is None:
        return Verdict.reask("no rough date given")
    if answer.resolved < today:
        return Verdict.reask("date in the past")
    if (answer.resolved - today).days > max_days:
        return Verdict.reask(f"more than {max_days} days away")
    return Verdict.accept(answer.resolved)
