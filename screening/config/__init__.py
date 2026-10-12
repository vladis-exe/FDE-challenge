"""Screening configuration: service areas, FAQ and process timings (CONTRACTS.md §4).

Loaded once at startup by whoever builds the EngineContext (Django, CLI, evals).
Everything the client might change lives in the YAML files next to this module.
"""

import os
import re
from datetime import time, timedelta
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, BeforeValidator, Field, model_validator

CONFIG_DIR = Path(__file__).parent

Country = Literal["ES", "MX"]
Language = Literal["es", "en"]

_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd])\s*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(raw: object) -> object:
    """Read "15m", "2h", "24h" or "30s" as a timedelta; leave anything else to Pydantic."""
    if isinstance(raw, str) and (match := _DURATION.match(raw)):
        amount, unit = match.groups()
        return timedelta(seconds=float(amount) * _UNIT_SECONDS[unit])
    return raw


Duration = Annotated[timedelta, BeforeValidator(parse_duration)]


class City(BaseModel):
    key: str  # canonical key stored in Location.city
    name: str  # display name
    aliases: list[str] = []
    neighborhoods: list[str] = []


class CountryArea(BaseModel):
    timezone: str
    cities: list[City]


class FaqEntry(BaseModel):
    id: str
    questions: dict[Language, list[str]]  # example phrasings, used as few-shot hints
    answer: dict[Language, str]
    placeholder: bool = True  # true until Grupo Sazón supplies the real answer


class QuietHours(BaseModel):
    start: time  # no outbound from start...
    end: time  # ...until end, candidate-local time; wraps midnight


class MessageLimits(BaseModel):
    max_chars: int = 300
    max_sentences: int = 2
    max_questions: int = 1
    max_emojis: int = 1


class ScreeningConfig(BaseModel):
    service_areas: dict[Country, CountryArea]
    faq: list[FaqEntry]
    reminder_schedule: list[Duration]  # measured from the candidate's last message
    abandon_after: Duration
    quiet_hours: QuietHours
    max_attempts_per_field: int = 2
    max_offtopic_strikes: int = 1
    start_date_max_days: int = 183
    transcript_tail_size: int = 12
    message_limits: MessageLimits = Field(default_factory=MessageLimits)
    time_scale: float = 1.0  # DEMO_TIME_SCALE already applied to the durations above

    @model_validator(mode="after")
    def _check_timings(self) -> "ScreeningConfig":
        if self.reminder_schedule != sorted(self.reminder_schedule):
            raise ValueError("reminder_schedule must be in increasing order")
        if self.reminder_schedule and self.reminder_schedule[-1] >= self.abandon_after:
            raise ValueError("abandon_after must come after the last reminder")
        return self

    def timezone_for(self, country: Country) -> str:
        return self.service_areas[country].timezone


def load_config(path: Path | None = None) -> ScreeningConfig:
    """Load the three YAML files from `path` (a directory; defaults to this package).

    DEMO_TIME_SCALE compresses the reminder and abandonment timings: 60 turns 15 min
    into 15 s. Quiet hours are wall-clock rules and are not scaled.
    """
    directory = path or CONFIG_DIR
    settings = _read_yaml(directory / "screening.yaml")
    areas = _read_yaml(directory / "service_areas.yaml")
    faq = _read_yaml(directory / "faq.yaml")

    config = ScreeningConfig.model_validate(
        {**settings, "service_areas": areas, "faq": faq["entries"]}
    )
    scale = float(os.environ.get("DEMO_TIME_SCALE") or 1)
    if scale <= 0:
        raise ValueError(f"DEMO_TIME_SCALE must be positive, got {scale}")
    return config.model_copy(
        update={
            "reminder_schedule": [delay / scale for delay in config.reminder_schedule],
            "abandon_after": config.abandon_after / scale,
            "time_scale": scale,
        }
    )


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)
