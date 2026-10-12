"""LLMClient backed by the Anthropic Messages API.

Choices (checked against the current API reference, October 2026):
- Structured output uses `messages.parse(output_format=Model)`, which constrains
  decoding to the JSON schema and validates into the Pydantic model. Forced tool
  use is not an option: Sonnet 5.5 rejects a forced `tool_choice`.
- Current models think by default and thinking tokens count against `max_tokens`.
  We keep thinking on, ask for low effort (fast, cheap replies), and add a fixed
  headroom so a short reply budget is never eaten by thinking. Turning thinking
  off is model-specific (`disabled` vs `between_tools`) and would break the
  model swaps the evals do.
- The system prompt is marked for prompt caching. It must stay byte-stable:
  per-conversation data goes in `messages`, never in `system`.
- No temperature: current models reject non-default sampling parameters.
"""

import os
import time
from typing import Any

import anthropic
from pydantic import ValidationError

from screening.llm.base import LLMError, LLMResult, LLMUsage, M, ModelTier

DEFAULT_MODELS: dict[ModelTier, str] = {"fast": "claude-haiku-5-5", "smart": "claude-sonnet-5-5"}
THINKING_HEADROOM = 2048  # tokens on top of the visible-output budget
STRUCTURED_MAX_TOKENS = 1024  # an Extraction or summary record is small
EFFORT = "low"


class AnthropicClient:
    def __init__(
        self,
        *,
        fast_model: str | None = None,
        smart_model: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        client: Any = None,  # injected in tests; anything with a `.messages` like the SDK's
    ) -> None:
        self.models: dict[ModelTier, str] = {
            "fast": fast_model or os.environ.get("LLM_MODEL_FAST") or DEFAULT_MODELS["fast"],
            "smart": smart_model or os.environ.get("LLM_MODEL_SMART") or DEFAULT_MODELS["smart"],
        }
        # The SDK retries connection errors, 408, 409, 429 and 5xx with exponential
        # backoff; we only decide how many times and how long each try may take.
        self._client = client or anthropic.Anthropic(timeout=timeout, max_retries=max_retries)

    def structured(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        schema: type[M],
        tier: ModelTier = "fast",
    ) -> LLMResult[M]:
        model = self.models[tier]
        # Constrained decoding makes an invalid record rare; one more try covers it.
        for _ in range(2):
            started = time.monotonic()
            try:
                response = self._client.messages.parse(
                    **self._request(model, system, messages, STRUCTURED_MAX_TOKENS),
                    output_format=schema,
                )
            except ValidationError:
                continue
            except anthropic.APIError as error:
                raise LLMError(f"{purpose}: {type(error).__name__}: {error}") from error
            self._check_stop(purpose, response)
            if response.parsed_output is not None:
                return LLMResult[schema](
                    value=response.parsed_output, usage=_usage(model, response, started)
                )
        raise LLMError(f"{purpose}: response did not match {schema.__name__}")

    def text(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier = "fast",
        max_tokens: int = 300,
    ) -> LLMResult[str]:
        model = self.models[tier]
        started = time.monotonic()
        try:
            response = self._client.messages.create(
                **self._request(model, system, messages, max_tokens)
            )
        except anthropic.APIError as error:
            raise LLMError(f"{purpose}: {type(error).__name__}: {error}") from error
        self._check_stop(purpose, response)
        # Read blocks by type: a response may start with (empty) thinking blocks.
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise LLMError(f"{purpose}: empty response")
        return LLMResult[str](value=text, usage=_usage(model, response, started))

    def _request(
        self, model: str, system: str, messages: list[dict[str, str]], max_tokens: int
    ) -> dict[str, Any]:
        return {
            "model": model,
            "max_tokens": max_tokens + THINKING_HEADROOM,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "output_config": {"effort": EFFORT},
        }

    @staticmethod
    def _check_stop(purpose: str, response: Any) -> None:
        # A refusal or a cut-off answer is unusable; the engine falls back to a holding reply.
        if response.stop_reason in ("refusal", "max_tokens"):
            raise LLMError(f"{purpose}: stopped with {response.stop_reason}")


def _usage(model: str, response: Any, started: float) -> LLMUsage:
    usage = response.usage
    cache_read = usage.cache_read_input_tokens or 0
    cache_write = usage.cache_creation_input_tokens or 0
    # The API's input_tokens counts only uncached input; the contract wants the total.
    return LLMUsage(
        model=model,
        input_tokens=usage.input_tokens + cache_read + cache_write,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        latency_ms=round((time.monotonic() - started) * 1000),
    )
