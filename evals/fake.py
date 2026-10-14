"""Offline mode (`evals.run --fake`): no API key, no cost.

The engine gets the CLI's keyword stub and the candidate recites its facts for the
stage being asked. Scores are meaningless for language quality, but the harness, the
fake clock, reminders, quiet hours and abandonment run for real, since they are code.
"""

import re
from datetime import datetime

from evals.scenario import Scenario
from evals.simulator import Line

FIELD_STAGES = {
    "name",
    "license",
    "location",
    "availability",
    "schedule",
    "experience",
    "start_date",
}


class FactsCandidate:
    """Answers the asked stage from `facts`, first sentence only; says yes otherwise."""

    def __init__(self, scenario: Scenario) -> None:
        self.facts = scenario.facts
        self.tokens = {"input": 0, "output": 0}

    def reply(self, lines: list[Line], directive: str | None, stage: str, now: datetime) -> str:
        key = stage if stage in FIELD_STAGES else ""
        fact = self.facts.get(key) or self.facts.get(f"{key}_initial", "")
        if not fact:
            return "si"
        if key == "license":
            return "no" if fact.lower().startswith("no") else "si"
        first = re.split(r"(?<=[.;])\s", fact)[0].rstrip(".;")
        return re.sub(r"\s*\(.*?\)", "", first)  # "Kevin Ramírez Soto (gives only…)" → name
