"""Scenario files: who the simulated candidate is, and the exact record the engine must produce.

A scenario has three parts:
- persona, facts and behaviors steer the simulated candidate (an LLM role-playing the persona);
- script, pauses and the seed keep the hard-case moments and the clock deterministic across runs;
- expected and expected_status are the ground truth the scorers compare against.

The enums mirror CONTRACTS §1 as literals, so scenarios can be validated before `screening` exists.
Once E1 lands, the scorers compare against `screening.schemas` directly.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCENARIOS_DIR = Path(__file__).parent / "scenarios"

Status = Literal["qualified", "needs_review", "disqualified", "abandoned", "opted_out"]
StageName = Literal[
    "consent", "name", "license", "location", "availability",
    "schedule", "experience", "start_date", "confirm",
]  # fmt: skip
Availability = Literal["full_time", "part_time", "weekends"]
Schedule = Literal["morning", "afternoon", "evening", "flexible"]
Platform = Literal["glovo", "uber_eats", "just_eat", "rappi", "didi_food", "other"]
Media = Literal["none", "audio", "image", "sticker", "other"]
RecordField = Literal[
    "full_name", "has_driver_license", "location", "availability",
    "schedule", "experience", "start_date",
]  # fmt: skip

# Checks beyond the record that a scenario asks the scorers to run.
# Each one must be explainable in one sentence.
Check = Literal[
    "faq_answered",  # at least one faq_answered event, and no pay figure that isn't in faq.yaml
    "faq_unknown_deferred",  # a question outside the FAQ gets "a recruiter will confirm"
    "media_asks_for_text",  # the reply to a voice note, image or sticker asks for a text answer
    "no_sensitive_in_record",  # no sensitive_terms appear in the record or summary
    "reminders_sent",  # reminders went out at the configured offsets from the last inbound message
    "quiet_hours_respected",  # no outbound between 21:00 and 09:00 candidate-local time
    "no_messages_after_close",  # nothing is sent after opt-out, disqualification or abandonment
    "waitlist_offered",  # the out-of-area close offers the waitlist
    "surname_asked_once",  # a first-name-only answer gets exactly one surname re-ask
    "injection_ignored",  # injected instructions change neither the outcome nor the persona
    "single_redirect",  # off-topic or abuse gets exactly one redirect before the close
]

COUNTRY_CITIES: dict[str, set[str]] = {
    "ES": {"madrid", "barcelona", "valencia", "sevilla", "malaga", "bilbao"},
    "MX": {"cdmx", "guadalajara", "monterrey", "puebla", "queretaro"},
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Trigger(_Strict):
    """When a scripted turn fires: on the Nth candidate turn (1-based), or the first turn at
    a stage or past it (a stage the candidate skipped by answering early still fires)."""

    turn: int | None = Field(default=None, ge=1)
    stage: StageName | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "Trigger":
        if (self.turn is None) == (self.stage is None):
            raise ValueError("a trigger needs exactly one of turn or stage")
        return self


class ScriptedTurn(_Strict):
    """A message sent verbatim instead of asking the persona LLM, for moments a run can't skip."""

    when: Trigger
    text: str = ""
    media: Media = "none"
    burst: list[str] = []  # follow-up messages sent right after, before the agent's reply is read


class Pause(_Strict):
    """The candidate goes silent at `at_stage` (or past it); the fake clock ticks meanwhile."""

    at_stage: StageName
    duration: timedelta
    resume: bool = True  # False: never come back (abandonment)


class Experience(_Strict):
    platform: Platform
    years: float = Field(ge=0, le=40)


class ExpectedRecord(_Strict):
    """Same keys as `final_record`, minus conversation_id and summary, which have no fixed truth.

    `flags` holds only field names: the note is free text and isn't scored.
    """

    status: Status
    language: Literal["es", "en"]
    full_name: str | None
    has_driver_license: bool | None
    country: Literal["ES", "MX"] | None
    city: str | None
    availability: list[Availability] | None
    preferred_schedule: list[Schedule] | None
    delivery_experience: list[Experience] | None
    start_date: date | None
    flags: list[RecordField] = []
    disqualify_reason: Literal["no_license", "out_of_area"] | None = None
    review_reasons: list[str] = []


class Scenario(_Strict):
    id: str
    title: str
    covers: list[str]  # which spec behaviors this scenario exercises
    language: Literal["es", "en"]  # the language the candidate starts in
    country: Literal["ES", "MX"]
    phone: str  # fake E.164; its prefix is the engine's country hint
    starts_at: datetime  # fake-clock time of the opening message, candidate-local with offset
    seed: int
    max_turns: int = Field(default=25, ge=1)
    persona: str
    facts: dict[str, str]  # what the candidate knows; the persona LLM may only reveal these
    behaviors: list[str]
    script: list[ScriptedTurn] = []
    pauses: list[Pause] = []
    sensitive_terms: list[str] = []
    checks: list[Check] = []
    score_ignore: list[str] = []  # record keys where the spec leaves the engine latitude
    expected_status: Status
    expected: ExpectedRecord

    @model_validator(mode="after")
    def _consistent(self) -> "Scenario":
        exp = self.expected
        problems: list[str] = []
        if self.starts_at.tzinfo is None:
            problems.append("starts_at must carry a UTC offset")
        if exp.status != self.expected_status:
            problems.append("expected.status differs from expected_status")
        if (self.expected_status == "disqualified") != (exp.disqualify_reason is not None):
            problems.append("disqualify_reason must be set exactly when disqualified")
        if (self.expected_status == "needs_review") != bool(exp.review_reasons):
            problems.append("review_reasons must be non-empty exactly when needs_review")
        if exp.flags and self.expected_status not in ("needs_review", "abandoned", "opted_out"):
            problems.append("flagged fields imply needs_review")
        if exp.city is not None and exp.city not in COUNTRY_CITIES.get(exp.country or "", set()):
            problems.append(f"city {exp.city!r} is not a served city of {exp.country}")
        if self.expected_status == "qualified" and None in (
            exp.full_name, exp.has_driver_license, exp.city, exp.availability,
            exp.preferred_schedule, exp.delivery_experience, exp.start_date,
        ):  # fmt: skip
            problems.append("a qualified record must have every field")
        schedule = exp.preferred_schedule or []
        if "flexible" in schedule and len(schedule) > 1:
            problems.append("flexible stands alone")
        if exp.start_date is not None:
            days = (exp.start_date - self.starts_at.date()).days
            if not 0 <= days <= 183:
                problems.append(f"start_date is {days} days from starts_at, outside 0-183")
        if "no_sensitive_in_record" in self.checks and not self.sensitive_terms:
            problems.append("no_sensitive_in_record needs sensitive_terms")
        if problems:
            raise ValueError(f"{self.id}: " + "; ".join(problems))
        return self


def load_scenario(path: Path) -> Scenario:
    return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_all(directory: Path = SCENARIOS_DIR) -> list[Scenario]:
    return [load_scenario(p) for p in sorted(directory.glob("*.yaml"))]
