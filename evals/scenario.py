"""Scenario files: who the simulated candidate is, and the exact record the engine must produce.

A scenario has three parts:
- persona, facts and behaviors steer the simulated candidate (an LLM role-playing the persona);
- script, pauses and the seed keep the hard-case moments and the clock deterministic across runs;
- expected and expected_status are the ground truth the scorers compare against.

Since CONTRACTS v4 a scenario screens against one vacancy, and its fields come from that
vacancy's config. `load_scenario` checks the ground truth against the real config: field
names, value shapes, served cities, and the preference score by the contract's formula.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from screening.config import FieldSpec, ScreeningConfig, VacancyConfig, load_config

SCENARIOS_DIR = Path(__file__).parent / "scenarios"

Status = Literal["qualified", "needs_review", "disqualified", "abandoned", "opted_out"]
Media = Literal["none", "audio", "image", "sticker", "other"]
PLATFORMS = {"glovo", "uber_eats", "just_eat", "rappi", "didi_food", "other"}
EXPERIENCE_YEARS_CAP = 5  # CONTRACTS §7: experience counts at most 5 years towards the score

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
    "preferred_asked_once",  # every preferred field is asked once: never re-asked, never flagged
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Trigger(_Strict):
    """When a scripted turn fires: on the Nth candidate turn (1-based), or the first turn at
    a step or past it (a step the candidate skipped by answering early still fires).

    A step is `consent`, the name of a vacancy field being asked, or `confirm`.
    """

    turn: int | None = Field(default=None, ge=1)
    step: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "Trigger":
        if (self.turn is None) == (self.step is None):
            raise ValueError("a trigger needs exactly one of turn or step")
        return self


class ScriptedTurn(_Strict):
    """A message sent verbatim instead of asking the persona LLM, for moments a run can't skip."""

    when: Trigger
    text: str = ""
    media: Media = "none"
    burst: list[str] = []  # follow-up messages sent right after, before the agent's reply is read


class Pause(_Strict):
    """The candidate goes silent at `at_step` (or past it); the fake clock ticks meanwhile."""

    at_step: str
    duration: timedelta
    resume: bool = True  # False: never come back (abandonment)


class ExpectedRecord(_Strict):
    """Same keys as `final_record`, minus conversation_id, vacancy_id and summary.

    `fields` holds exactly the accepted fields, as in the record: a field missing or flagged
    is absent. `flags` holds only field names: the note is free text and isn't scored.
    """

    status: Status
    language: Literal["es", "en"]
    fields: dict[str, Any] = {}
    flags: list[str] = []
    disqualify_reason: str | None = None
    review_reasons: list[str] = []
    preference_score: float = 0.0


class Scenario(_Strict):
    id: str
    title: str
    covers: list[str]  # which spec behaviors this scenario exercises
    vacancy: str = "driver"
    language: Literal["es", "en"]  # the language the candidate starts in
    country: Literal["ES", "MX"]
    phone: str  # fake E.164; its prefix is the engine's country hint
    starts_at: datetime  # fake-clock time of the opening message, candidate-local with offset
    seed: int
    max_turns: int = Field(default=25, ge=1)
    persona: str
    facts: dict[str, str]  # what the candidate knows; the persona LLM may only reveal these
    behaviors: list[str]
    # Random style notes and one sidetrack per run (simulator.QUIRKS). Off where an early
    # derail would pre-empt the scripted moment the scenario exists for.
    quirks: bool = True
    script: list[ScriptedTurn] = []
    pauses: list[Pause] = []
    sensitive_terms: list[str] = []
    checks: list[Check] = []
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
        if set(exp.flags) & set(exp.fields):
            problems.append("a flagged field can't also be accepted")
        if "no_sensitive_in_record" in self.checks and not self.sensitive_terms:
            problems.append("no_sensitive_in_record needs sensitive_terms")
        if problems:
            raise ValueError(f"{self.id}: " + "; ".join(problems))
        return self

    def steps(self, vacancy: VacancyConfig) -> list[str]:
        """The conversation's steps in order: consent, each asked field, the read-back."""
        return ["consent", *(spec.name for spec in vacancy.asked), "confirm", "done"]


def check_against_config(scenario: Scenario, config: ScreeningConfig) -> list[str]:
    """Problems with the ground truth given the real vacancy and service-area config."""
    if scenario.vacancy not in config.vacancies:
        return [f"unknown vacancy {scenario.vacancy!r}"]
    vacancy = config.vacancy(scenario.vacancy)
    specs = {spec.name: spec for spec in vacancy.asked}
    exp = scenario.expected
    problems = [
        f"{name}: not a field of {vacancy.id}"
        for name in [*exp.fields, *exp.flags]
        if name not in specs
    ]
    steps = scenario.steps(vacancy)
    named = [t.when.step for t in scenario.script if t.when.step] + [
        p.at_step for p in scenario.pauses
    ]
    problems += [f"step {s!r} is not one of {steps}" for s in named if s not in steps]
    for name, value in exp.fields.items():
        if name in specs:
            problems += _value_problems(specs[name], value, scenario, config)
    if exp.status == "qualified":
        missing = [s.name for s in vacancy.asked if s.requirement == "required"]
        missing = [name for name in missing if name not in exp.fields]
        if missing:
            problems.append(f"a qualified record needs every required field: {missing}")
    score = _preference_score(vacancy, exp.fields)
    if abs(score - exp.preference_score) > 0.005:
        problems.append(f"preference_score is {exp.preference_score}, the formula gives {score}")
    return problems


def _value_problems(
    spec: FieldSpec, value: Any, scenario: Scenario, config: ScreeningConfig
) -> list[str]:
    where = f"fields.{spec.name}"
    if spec.type == "text":
        return [] if isinstance(value, str) and value.strip() else [f"{where}: expected text"]
    if spec.type == "boolean":
        return [] if isinstance(value, bool) else [f"{where}: expected true or false"]
    if spec.type == "city":
        if not isinstance(value, dict) or set(value) != {"country", "city"}:
            return [f"{where}: expected {{country, city}}"]
        area = config.service_areas.get(value["country"])
        served = {city.key for city in area.cities} if area else set()
        return [] if value["city"] in served else [f"{where}: {value} is not a served city"]
    if spec.type == "enum_multi":
        options = spec.options or []
        if not isinstance(value, list) or not value or set(value) - set(options):
            return [f"{where}: expected a non-empty list from {options}"]
        if set(value) & set(spec.exclusive_options) and len(value) > 1:
            return [f"{where}: {spec.exclusive_options} stand alone"]
        return []
    if spec.type == "experience":
        ok = isinstance(value, list) and all(
            isinstance(item, dict)
            and item.get("platform") in PLATFORMS
            and 0 <= item.get("years", -1) <= 40
            for item in value
        )
        return [] if ok else [f"{where}: expected [{{platform, years}}]"]
    # date: within the window from the conversation's first day (CONTRACTS start-date rule)
    try:
        days = (date.fromisoformat(str(value)) - scenario.starts_at.date()).days
    except ValueError:
        return [f"{where}: expected an ISO date"]
    limit = config.start_date_max_days
    return [] if 0 <= days <= limit else [f"{where}: {days} days away, outside 0-{limit}"]


def _preference_score(vacancy: VacancyConfig, fields: dict[str, Any]) -> float:
    """CONTRACTS §7's formula, recomputed here so the ground truth doesn't trust the engine."""
    total = 0.0
    for spec in vacancy.asked:
        value = fields.get(spec.name)
        if spec.requirement != "preferred" or value is None:
            continue
        if spec.type == "boolean" and value is True:
            total += spec.weight
        elif spec.type == "enum_multi" and value:
            total += spec.weight
        elif spec.type == "experience":
            total += spec.weight * min(sum(i["years"] for i in value), EXPERIENCE_YEARS_CAP)
    return round(total, 2)


def load_scenario(path: Path, config: ScreeningConfig | None = None) -> Scenario:
    scenario = Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    problems = check_against_config(scenario, config or load_config())
    if problems:
        raise ValueError(f"{scenario.id}: " + "; ".join(problems))
    return scenario


def load_all(directory: Path = SCENARIOS_DIR) -> list[Scenario]:
    config = load_config()
    return [load_scenario(p, config) for p in sorted(directory.glob("*.yaml"))]
