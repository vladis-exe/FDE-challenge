"""A scripted LLMClient for tests. It never touches the network.

Responses are keyed by purpose ("extract", "compose", "summary"). Each script is
either a list consumed in order, or a callable invoked on every call:

    llm = FakeLLM({
        "extract": [Extraction(intent="answer", ...)],
        "compose": lambda system, messages: "¡Genial! ¿En qué ciudad vives?",
    })

A scripted item that is an exception instance is raised instead of returned,
which is how tests simulate an LLM outage.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from screening.llm.base import LLMResult, LLMUsage, M, ModelTier

Script = list[Any] | Callable[[str, list[dict[str, str]]], Any]
FAKE_USAGE = LLMUsage(model="fake", input_tokens=0, output_tokens=0, latency_ms=0)


@dataclass
class FakeCall:
    purpose: str
    system: str
    messages: list[dict[str, str]]
    tier: ModelTier


@dataclass
class FakeLLM:
    scripts: dict[str, Script] = field(default_factory=dict)
    calls: list[FakeCall] = field(default_factory=list)

    def structured(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        schema: type[M],
        tier: ModelTier = "fast",
    ) -> LLMResult[M]:
        raw = self._next(purpose, system, messages, tier)
        value = raw if isinstance(raw, schema) else schema.model_validate(raw)
        return LLMResult[schema](value=value, usage=FAKE_USAGE)

    def text(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier = "fast",
        max_tokens: int = 300,
    ) -> LLMResult[str]:
        raw = self._next(purpose, system, messages, tier)
        if isinstance(raw, BaseModel) or not isinstance(raw, str):
            raise TypeError(f"FakeLLM script for {purpose!r} returned {type(raw).__name__}")
        return LLMResult[str](value=raw, usage=FAKE_USAGE)

    def calls_for(self, purpose: str) -> list[FakeCall]:
        return [call for call in self.calls if call.purpose == purpose]

    def _next(
        self, purpose: str, system: str, messages: list[dict[str, str]], tier: ModelTier
    ) -> Any:
        self.calls.append(FakeCall(purpose, system, messages, tier))
        if purpose not in self.scripts:
            raise LookupError(f"FakeLLM has no script for purpose {purpose!r}")
        script = self.scripts[purpose]
        if callable(script):
            raw = script(system, messages)
        elif script:
            raw = script.pop(0)
        else:
            raise LookupError(f"FakeLLM script for {purpose!r} is used up")
        if isinstance(raw, Exception):
            raise raw
        return raw
