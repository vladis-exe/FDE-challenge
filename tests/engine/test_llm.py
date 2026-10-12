from types import SimpleNamespace
from typing import Literal

import anthropic
import httpx2
import pytest
from pydantic import BaseModel, ValidationError

from screening.llm import AnthropicClient, FakeLLM, LLMError
from screening.llm.anthropic_client import THINKING_HEADROOM


class Answer(BaseModel):
    intent: Literal["answer", "question"]
    city: str | None = None


def usage(input_tokens=100, output_tokens=20, cache_read=0, cache_write=0):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
    )


def text_response(text, stop_reason="end_turn"):
    content = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text=text),
    ]
    return SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage())


def parsed_response(parsed, stop_reason="end_turn"):
    return SimpleNamespace(
        parsed_output=parsed, stop_reason=stop_reason, usage=usage(cache_read=900, cache_write=50)
    )


class StubMessages:
    """Stands in for `anthropic.Anthropic().messages`: replays outcomes, records requests."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def _next(self, **request):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    parse = _next
    create = _next


def client_with(*outcomes):
    messages = StubMessages(outcomes)
    client = AnthropicClient(
        fast_model="fast-model",
        smart_model="smart-model",
        client=SimpleNamespace(messages=messages),
    )
    return client, messages


def validation_error():
    try:
        Answer.model_validate({"intent": "nonsense"})
    except ValidationError as error:
        return error


def api_error():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


# AnthropicClient


def test_structured_returns_validated_value_and_usage():
    client, messages = client_with(parsed_response(Answer(intent="answer", city="bcn")))
    result = client.structured(purpose="extract", system="sys", messages=[], schema=Answer)

    assert result.value == Answer(intent="answer", city="bcn")
    assert result.usage.model == "fast-model"
    assert result.usage.input_tokens == 100 + 900 + 50  # uncached + cache read + cache write
    assert result.usage.output_tokens == 20
    assert messages.requests[0]["output_format"] is Answer


def test_request_shape_caches_system_prompt_and_sends_no_sampling_params():
    client, messages = client_with(text_response("Hola"))
    client.text(purpose="compose", system="persona", messages=[], tier="smart", max_tokens=300)

    request = messages.requests[0]
    assert request["model"] == "smart-model"
    assert request["system"] == [
        {"type": "text", "text": "persona", "cache_control": {"type": "ephemeral"}}
    ]
    assert request["max_tokens"] == 300 + THINKING_HEADROOM
    assert request["output_config"] == {"effort": "low"}
    assert "temperature" not in request
    assert "thinking" not in request


def test_text_skips_thinking_blocks():
    client, _ = client_with(text_response("  ¿En qué ciudad vives?  "))
    result = client.text(purpose="compose", system="s", messages=[])
    assert result.value == "¿En qué ciudad vives?"


def test_structured_retries_once_on_invalid_record():
    client, messages = client_with(validation_error(), parsed_response(Answer(intent="question")))
    result = client.structured(purpose="extract", system="s", messages=[], schema=Answer)
    assert result.value.intent == "question"
    assert len(messages.requests) == 2


def test_structured_gives_up_after_two_invalid_records():
    client, _ = client_with(validation_error(), validation_error())
    with pytest.raises(LLMError):
        client.structured(purpose="extract", system="s", messages=[], schema=Answer)


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_stop_reasons_raise(stop_reason):
    client, _ = client_with(text_response("partial", stop_reason=stop_reason))
    with pytest.raises(LLMError, match=stop_reason):
        client.text(purpose="compose", system="s", messages=[])


def test_api_failure_after_sdk_retries_becomes_llm_error():
    client, _ = client_with(api_error())
    with pytest.raises(LLMError, match="compose"):
        client.text(purpose="compose", system="s", messages=[])


def test_empty_text_is_an_error():
    client, _ = client_with(text_response("   "))
    with pytest.raises(LLMError):
        client.text(purpose="compose", system="s", messages=[])


def test_models_come_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_FAST", "env-fast")
    monkeypatch.delenv("LLM_MODEL_SMART", raising=False)
    client = AnthropicClient(client=SimpleNamespace(messages=None))
    assert client.models == {"fast": "env-fast", "smart": "claude-sonnet-5-5"}


# FakeLLM


def test_fake_replays_scripts_in_order_and_records_calls():
    llm = FakeLLM({"extract": [{"intent": "answer"}, Answer(intent="question")], "compose": ["Hi"]})

    first = llm.structured(purpose="extract", system="s", messages=[], schema=Answer)
    second = llm.structured(purpose="extract", system="s", messages=[], schema=Answer)
    reply = llm.text(
        purpose="compose", system="persona", messages=[{"role": "user", "content": "x"}]
    )

    assert first.value == Answer(intent="answer")
    assert second.value == Answer(intent="question")
    assert reply.value == "Hi"
    assert [call.purpose for call in llm.calls] == ["extract", "extract", "compose"]
    assert llm.calls_for("compose")[0].messages == [{"role": "user", "content": "x"}]


def test_fake_callable_script_sees_the_prompt():
    llm = FakeLLM({"compose": lambda system, messages: f"echo:{messages[-1]['content']}"})
    result = llm.text(purpose="compose", system="s", messages=[{"role": "user", "content": "hola"}])
    assert result.value == "echo:hola"


def test_fake_raises_scripted_errors():
    llm = FakeLLM({"compose": [LLMError("down")]})
    with pytest.raises(LLMError):
        llm.text(purpose="compose", system="s", messages=[])


def test_fake_fails_loudly_on_unscripted_or_exhausted_purpose():
    llm = FakeLLM({"compose": []})
    with pytest.raises(LookupError):
        llm.text(purpose="summary", system="s", messages=[])
    with pytest.raises(LookupError):
        llm.text(purpose="compose", system="s", messages=[])
