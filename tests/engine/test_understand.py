from datetime import UTC, datetime

import pytest

from screening.config import load_config
from screening.llm import FakeLLM
from screening.prompts import load_prompt
from screening.schemas import (
    Channel,
    ConversationState,
    InboundMessage,
    Location,
    Stage,
    TranscriptLine,
)
from screening.understand import Extraction, extract, system_prompt, user_prompt


@pytest.fixture(scope="module")
def config():
    return load_config()


def make_state(**changes) -> ConversationState:
    return ConversationState(conversation_id="c1", channel=Channel.SIM).model_copy(update=changes)


def message(text: str, at: datetime = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)) -> InboundMessage:
    return InboundMessage(id="m1", text=text, received_at=at)


def test_prompt_header_is_stripped():
    prompt = load_prompt("extract")
    assert not prompt.startswith("<!--")
    assert "Purpose:" not in prompt


def test_system_prompt_lists_faq_ids_and_has_no_leftover_placeholders(config):
    prompt = system_prompt(config)
    for entry in config.faq:
        assert f"- {entry.id}: " in prompt
    assert "{faq_catalogue}" not in prompt
    assert '{"intent": "answer"' in prompt  # escaped braces in the examples came out right


def test_system_prompt_is_byte_stable_across_conversations(config):
    """Caching depends on it: nothing conversation-specific may leak into the system prompt."""
    assert system_prompt(config) == system_prompt(load_config())


def test_user_prompt_carries_stage_local_date_and_message(config):
    state = make_state(stage=Stage.LOCATION, country_hint="MX")
    # 03:00 UTC on Thursday is still Wednesday evening in Mexico City.
    prompt = user_prompt(
        state, message("vivo en Zapopan", datetime(2026, 10, 15, 3, 0, tzinfo=UTC)), config
    )
    assert "Asking for: city" in prompt
    assert "Country: MX" in prompt
    assert "Candidate's local date: 2026-10-14 (Wednesday)" in prompt
    assert "<candidate_message>\nvivo en Zapopan\n</candidate_message>" in prompt


def test_confirmed_location_wins_over_the_country_hint(config):
    state = make_state(country_hint="MX")
    state.profile.location.value = Location(country="ES", city="madrid")
    assert "Country: ES" in user_prompt(state, message("hola"), config)


def test_user_prompt_includes_recent_conversation(config):
    at = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    state = make_state(
        stage=Stage.LICENSE,
        transcript_tail=[
            TranscriptLine(role="agent", text="¿Tienes carnet de conducir?", at=at),
            TranscriptLine(role="candidate", text="sí", at=at, message_id="m0"),
        ],
    )
    prompt = user_prompt(state, message("👍"), config)
    assert "Alex: ¿Tienes carnet de conducir?\nCandidate: sí" in prompt


def test_extract_calls_fast_tier_with_the_extraction_schema(config):
    llm = FakeLLM(
        {
            "extract": [
                {
                    "intent": "answer",
                    "language": "es",
                    "fields": {"full_name": "Laura Pérez", "license": "yes"},
                }
            ]
        }
    )
    result = extract(
        make_state(), message("soy Laura Pérez y tengo carnet"), llm=llm, config=config
    )

    assert isinstance(result.value, Extraction)
    assert result.value.fields.full_name == "Laura Pérez"
    assert result.value.fields.license == "yes"
    call = llm.calls_for("extract")[0]
    assert call.tier == "fast"
    assert call.system == system_prompt(config)


def test_extraction_defaults_to_empty_fields():
    extraction = Extraction(intent="smalltalk", language="en")
    assert extraction.fields.full_name is None
    assert extraction.faq_id is None
