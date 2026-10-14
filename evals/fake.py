"""Offline mode (`evals.run --fake`): no API key, no cost.

The engine gets the CLI's keyword stub and the candidate recites its facts for the
field being asked. Scores are meaningless for language quality, but the harness, the
fake clock, reminders, quiet hours and abandonment run for real, since they are code.
"""

import re
from datetime import datetime

from evals.scenario import Scenario
from evals.simulator import Line
from screening.config import VacancyConfig

# Fact keys are short ("name", "license"); every other field's fact key is its own name.
FACT_KEYS = {"full_name": "name", "has_driver_license": "license"}
NOT_FIELDS = {"consent", "confirm", "done"}


class FactsCandidate:
    """Answers the asked field from `facts`, first sentence only; says yes otherwise."""

    def __init__(self, scenario: Scenario, vacancy: VacancyConfig) -> None:
        self.facts = scenario.facts
        self.yes_no = {spec.name for spec in vacancy.asked if spec.type == "boolean"}
        self.tokens = {"input": 0, "output": 0}

    def reply(self, lines: list[Line], directive: str | None, step: str, now: datetime) -> str:
        key = "" if step in NOT_FIELDS else FACT_KEYS.get(step, step)
        fact = self.facts.get(key) or self.facts.get(f"{key}_initial", "")
        if not fact:
            return "si"
        if step in self.yes_no:
            return "no" if fact.lower().startswith("no") else "si"
        first = re.split(r"(?<=[.;])\s", fact)[0].rstrip(".;")
        return re.sub(r"\s*\(.*?\)", "", first)  # "Kevin Ramírez Soto (gives only…)" → name
