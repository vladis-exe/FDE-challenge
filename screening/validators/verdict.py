from dataclasses import dataclass
from typing import Literal

Outcome = Literal["accept", "reask", "flag"]


@dataclass(frozen=True)
class Verdict[T]:
    """What code decided about one extracted value.

    accept: store `value` (with an optional note). reask: ask again, `note` says why.
    flag: send the field to human review with `note`; the conversation moves on.
    The policy counts attempts and turns repeated reasks into a flag.
    """

    outcome: Outcome
    value: T | None = None
    note: str | None = None

    @classmethod
    def accept(cls, value: T, note: str | None = None) -> "Verdict[T]":
        return cls("accept", value, note)

    @classmethod
    def reask(cls, note: str) -> "Verdict[T]":
        return cls("reask", None, note)

    @classmethod
    def flag(cls, note: str) -> "Verdict[T]":
        return cls("flag", None, note)
