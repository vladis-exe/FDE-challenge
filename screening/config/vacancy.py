"""Vacancies: which questions a job asks, and which of them gate (CONTRACTS.md §7).

A vacancy composes fields from a small, closed catalog of field types. The
catalog (validators, knockout rules, scoring) is engineer-owned code; a vacancy
only chooses which fields apply and whether each is required, preferred or off.
"""

from typing import Literal

from pydantic import BaseModel, model_validator

FieldType = Literal["text", "boolean", "city", "enum_multi", "experience", "date"]
Requirement = Literal["required", "preferred", "off"]
Language = Literal["es", "en"]

# Types that can only be required or off: asking a name "preferentially", or
# treating the service area as a nice-to-have, is not a meaningful rule.
NEVER_PREFERRED: set[FieldType] = {"text", "city"}


class FieldSpec(BaseModel):
    name: str  # key in CandidateProfile.fields and final_record["fields"]
    type: FieldType
    requirement: Requirement
    label: dict[Language, str]  # what to ask, in Alex's words, per language
    weight: float = 0.0  # preferred only: contribution to preference_score
    options: list[str] | None = None  # enum_multi only: allowed values, display order
    # Additions approved by Vlad, 2026-10-14 (status/engine.md, contract change requests):
    reason: str | None = None  # name in outcome strings: no_<reason>, <reason>_unclear
    summary: dict[str, str] = {}  # how the read-back introduces it; "es"/"en", "es_ES"/"es_MX"
    option_labels: dict[str, dict[str, str]] = {}  # option -> locale -> display text
    exclusive_options: list[str] = []  # enum_multi: options that stand alone

    @model_validator(mode="after")
    def _check(self) -> "FieldSpec":
        if self.type in NEVER_PREFERRED and self.requirement == "preferred":
            raise ValueError(f"{self.name}: a {self.type} field can't be preferred")
        if (self.type == "enum_multi") != bool(self.options):
            raise ValueError(f"{self.name}: options are required for enum_multi, and only there")
        unknown = set(self.exclusive_options) - set(self.options or [])
        if unknown:
            raise ValueError(f"{self.name}: exclusive options not in options: {sorted(unknown)}")
        if self.weight and self.requirement != "preferred":
            raise ValueError(f"{self.name}: only a preferred field can have a weight")
        return self

    @property
    def outcome_name(self) -> str:
        return self.reason or self.name


class VacancyConfig(BaseModel):
    id: str
    title: dict[Language, str]
    fields: list[FieldSpec]  # order = the order fields are asked in, required first

    @model_validator(mode="after")
    def _check(self) -> "VacancyConfig":
        names = [spec.name for spec in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"{self.id}: duplicate field names")
        return self

    @property
    def asked(self) -> list[FieldSpec]:
        """Fields actually asked, in policy order: required ones, then preferred ones.

        Required first is a rule, not a config choice: knockouts must come before
        anything that can't disqualify, so an ineligible candidate finishes fast.
        """
        required = [spec for spec in self.fields if spec.requirement == "required"]
        preferred = [spec for spec in self.fields if spec.requirement == "preferred"]
        return required + preferred

    def field(self, name: str) -> FieldSpec:
        return next(spec for spec in self.fields if spec.name == name)
