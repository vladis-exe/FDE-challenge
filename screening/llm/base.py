"""The LLM interface the engine depends on (CONTRACTS.md §3).

The engine only sees this protocol, so tests and evals can swap in FakeLLM or a
different model without touching engine code.
"""

from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel

ModelTier = Literal["fast", "smart"]
T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


class LLMUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class LLMResult(BaseModel, Generic[T]):  # noqa: UP046 -- syntax as written in CONTRACTS.md
    value: T
    usage: LLMUsage


class LLMError(Exception):
    """Raised after retries are exhausted; the engine turns it into a holding reply."""


class LLMClient(Protocol):
    def structured(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        schema: type[M],
        tier: ModelTier = "fast",
    ) -> LLMResult[M]: ...

    def text(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier = "fast",
        max_tokens: int = 300,
    ) -> LLMResult[str]: ...
