from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from screening.config import load_config
from screening.llm import FakeLLM
from screening.prompts import load_prompt
from screening.schemas import Channel, ConversationState, InboundMessage, Stage, TranscriptLine
from screening.understand import (
    Extraction,
    extract,
    extraction_model,
    system_prompt,
    user_prompt,
)

CONFIG = load_config()
DRIVER = CONFIG.vacancy("driver")
KITCHEN = CONFIG.vacancy("kitchen_prep")


def make_state(**changes) -> ConversationState:
    state = ConversationState(conversation_id="c1", channel=Channel.SIM, vacancy_id="driver")
    return state.model_copy(update=changes)


def message(text: str, at: datetime = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)) -> InboundMessage:
    return InboundMessage(id="m1", text=text, received_at=at)


def test_prompt_header_is_stripped():
    prompt = load_prompt("extract")
    assert not prompt.startswith("<!--")
    assert "Purpose:" not in prompt


def test_system_prompt_lists_the_vacancys_fields_and_faq_ids():
    prompt = system_prompt(CONFIG, DRIVER)
    assert "The job is: Delivery driver." in prompt
    assert "- has_driver_license (yes/no): whether they have a valid driver's license" in prompt
    assert "- schedule (options): " in prompt and "Allowed values: morning, afternoon" in prompt
    for entry in CONFIG.faq:
        assert f"- {entry.id}: " in prompt
    for placeholder in ("{faq_catalogue}", "{field_list}", "{job_title}"):
        assert placeholder not in prompt
    assert '{"intent": "answer"' in prompt  # escaped braces in the examples came out right


def test_each_vacancy_gets_its_own_byte_stable_system_prompt():
    """Caching depends on it: nothing conversation-specific may leak into the system prompt."""
    assert system_prompt(CONFIG, DRIVER) == system_prompt(load_config(), DRIVER)
    kitchen = system_prompt(CONFIG, KITCHEN)
    assert "food_handler_certificate (yes/no)" in kitchen
    assert "- experience" not in kitchen


def test_extraction_schema_has_only_the_vacancys_fields():
    model = extraction_model(KITCHEN)
    record = model.model_validate(
        {"intent": "answer", "language": "es", "fields": {"food_handler_certificate": "yes"}}
    )
    assert record.field("food_handler_certificate") == "yes"
    assert record.field("experience") is None  # not a kitchen_prep field
    with pytest.raises(ValidationError):  # an option from another field
        model.model_validate(
            {"intent": "answer", "language": "es", "fields": {"schedule": ["weekends"]}}
        )


def test_extraction_model_is_built_once_per_vacancy():
    assert extraction_model(DRIVER) is extraction_model(DRIVER)
    assert extraction_model(DRIVER) is not extraction_model(KITCHEN)


def test_user_prompt_names_the_current_field_local_date_and_message():
    state = make_state(stage=Stage.COLLECTING, current_field="location", country_hint="MX")
    # 03:00 UTC on Thursday is still Wednesday evening in Mexico City.
    at = datetime(2026, 10, 15, 3, 0, tzinfo=UTC)
    prompt = user_prompt(state, message("vivo en Zapopan", at), CONFIG, DRIVER)
    assert "Asking for: location (which city they live in, and the neighborhood)" in prompt
    assert "Country: MX" in prompt
    assert "Candidate's local date: 2026-10-14 (Wednesday)" in prompt
    assert "<candidate_message>\nvivo en Zapopan\n</candidate_message>" in prompt


@pytest.mark.parametrize(
    "changes, asking",
    [
        ({}, "consent"),
        ({"stage": Stage.CONFIRM}, "confirm (Alex read back the summary)"),
        (
            {
                "pending_confirmation": {
                    "type": "out_of_area",
                    "field": "location",
                    "city_text": "Tijuana",
                }
            },
            "confirmation that they'd work in Tijuana, outside the service area",
        ),
    ],
)
def test_user_prompt_names_special_asks(changes, asking):
    prompt = user_prompt(make_state(**changes), message("sí"), CONFIG, DRIVER)
    assert f"Asking for: {asking}\n" in prompt


def test_user_prompt_includes_recent_conversation():
    at = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    state = make_state(
        stage=Stage.COLLECTING,
        current_field="has_driver_license",
        transcript_tail=[
            TranscriptLine(role="agent", text="¿Tienes carnet de conducir?", at=at),
            TranscriptLine(role="candidate", text="sí", at=at, message_id="m0"),
        ],
    )
    prompt = user_prompt(state, message("👍"), CONFIG, DRIVER)
    assert "Alex: ¿Tienes carnet de conducir?\nCandidate: sí" in prompt


def test_extract_calls_fast_tier_with_the_vacancys_schema():
    llm = FakeLLM(
        {
            "extract": [
                {
                    "intent": "answer",
                    "language": "es",
                    "fields": {"full_name": "Laura Pérez", "has_driver_license": "yes"},
                }
            ]
        }
    )
    result = extract(
        make_state(), message("soy Laura Pérez y tengo carnet"), llm=llm, config=CONFIG
    )

    assert isinstance(result.value, Extraction)
    assert result.value.field("full_name") == "Laura Pérez"
    assert result.value.field("has_driver_license") == "yes"
    call = llm.calls_for("extract")[0]
    assert call.tier == "fast"
    assert call.system == system_prompt(CONFIG, DRIVER)


def test_a_bare_extraction_has_no_fields():
    extraction = Extraction(intent="smalltalk", language="en")
    assert extraction.field("full_name") is None
    assert extraction.faq_id is None
