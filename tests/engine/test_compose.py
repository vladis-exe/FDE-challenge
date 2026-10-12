from datetime import date

import pytest

from screening.compose import Ask, ReplyPlan, compose_reply, instructions, user_prompt
from screening.config import load_config
from screening.llm import FakeLLM
from screening.messages import fixed, opening, readback, summarize
from screening.prompts import load_prompt
from screening.schemas import (
    Availability,
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    Location,
    Schedule,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


def completed_state(language="es", country="ES", city="barcelona") -> ConversationState:
    state = ConversationState(conversation_id="c1", channel=Channel.SIM, language=language)
    profile = state.profile
    profile.full_name.value = "Laura Pérez"
    profile.has_driver_license.value = True
    profile.has_driver_license.status = FieldStatus.ACCEPTED
    profile.location.value = Location(country=country, city=city)
    profile.availability.value = [Availability.PART_TIME, Availability.WEEKENDS]
    profile.schedule.value = [Schedule.EVENING]
    profile.experience.value = [ExperienceItem(platform="glovo", years=1.5)]
    profile.experience.status = FieldStatus.ACCEPTED
    profile.start_date.value = date(2026, 10, 19)
    return state


# Fixed messages


@pytest.mark.parametrize("language", ["es", "en"])
def test_opening_discloses_ai_and_links_privacy(config, language):
    state = ConversationState(conversation_id="c1", channel=Channel.SIM, language=language)
    text = opening(state, config)
    assert "Alex" in text
    assert ("(IA)" if language == "es" else "(AI)") in text
    assert config.privacy_url in text
    assert text.endswith("?")


def test_every_fixed_message_has_both_languages():
    catalogue_keys = [
        "opening",
        "readback",
        "close_completed",
        "close_no_license",
        "close_out_of_area",
        "close_opt_out",
        "close_consent_declined",
        "close_human_requested",
        "close_flagged",
        "after_close",
        "holding",
        "media",
    ]
    for key in catalogue_keys:
        for language in ("es", "en"):
            for country in ("ES", "MX"):
                text = fixed(
                    key, language=language, country=country, summary="x", city="x", privacy_url="x"
                )
                assert "{" not in text, (key, language, country)


def test_no_license_close_uses_country_vocabulary():
    spain = fixed("close_no_license", language="es", country="ES", first_name="Laura")
    mexico = fixed("close_no_license", language="es", country="MX", first_name="Laura")
    assert spain.startswith("Gracias, Laura.")
    assert "carnet de conducir" in spain
    assert "licencia de manejo" in mexico


def test_name_placeholder_disappears_when_name_unknown():
    assert fixed("close_completed", language="en", country="ES").startswith("All done!")


# Read-back


def test_summary_in_spanish_spain(config):
    assert summarize(completed_state(), config) == (
        "Laura Pérez, carnet de conducir: sí, Barcelona, media jornada y fines de semana, "
        "noches, Glovo 1,5 años, empiezas el lunes 19 de octubre"
    )


def test_summary_uses_mexican_vocabulary(config):
    text = summarize(completed_state(country="MX", city="cdmx"), config)
    assert "licencia de manejo: sí" in text
    assert "Ciudad de México" in text
    assert "medio tiempo" in text


def test_summary_in_english(config):
    assert summarize(completed_state(language="en"), config) == (
        "Laura Pérez, driver's license: yes, Barcelona, part-time and weekends, "
        "evenings, Glovo 1.5 years, starting Monday 19 October"
    )


def test_summary_shows_flagged_license_and_no_experience(config):
    state = completed_state()
    state.profile.has_driver_license.value = None
    state.profile.has_driver_license.status = FieldStatus.FLAGGED
    state.profile.experience.value = []
    text = summarize(state, config)
    assert "carnet de conducir: lo revisará un reclutador" in text
    assert "sin experiencia en reparto" in text


def test_readback_fits_message_limit(config):
    text = readback(completed_state(), config)
    assert text.startswith("¡Gracias, Laura! Repasemos:")
    assert text.endswith("¿Está todo bien?")
    assert len(text) <= config.message_limits.max_chars


# Composed replies


def test_instructions_follow_plan_order():
    plan = ReplyPlan(
        language="es",
        country="MX",
        acknowledge=["city: Guadalajara"],
        faq_answer="Hay turnos de mañana, tarde y noche.",
        ask=Ask(field="availability"),
    )
    assert instructions(plan) == (
        "1. Briefly acknowledge what they just told you: city: Guadalajara.\n"
        "2. Answer their question with this approved information, in your own words but "
        'without adding or changing any fact: "Hay turnos de mañana, tarde y noche."\n'
        "3. Ask for: availability."
    )


def test_reask_with_options_and_reason():
    plan = ReplyPlan(
        language="en",
        country="ES",
        ask=Ask(field="city_choice", options=["Madrid", "Barcelona"], retry_reason="two cities"),
    )
    assert "Options: Madrid, Barcelona." in instructions(plan)
    assert "didn't work (two cities)" in instructions(plan)


def test_unanswered_question_defers_to_recruiter():
    plan = ReplyPlan(language="es", country="ES", unanswered_question="¿Dan uniforme?")
    assert "a recruiter will confirm" in instructions(plan)


def test_user_prompt_has_language_and_vocabulary():
    prompt = user_prompt(ReplyPlan(language="es", country="MX", first_name="Ana"), [])
    assert "Language: Spanish" in prompt
    assert "licencia de manejo, carro, celular" in prompt
    assert "Candidate's first name: Ana" in prompt


def test_compose_reply_uses_static_persona_prompt():
    llm = FakeLLM(
        {"compose": ["¡Genial! ¿Buscas jornada completa, media jornada o fines de semana?"]}
    )
    plan = ReplyPlan(language="es", country="ES", ask=Ask(field="availability"))
    result = compose_reply(plan, [], llm=llm)
    assert result.value.endswith("?")
    call = llm.calls_for("compose")[0]
    assert call.system == load_prompt("compose")
    assert call.tier == "fast"


def test_out_of_area_names_the_city_as_not_served():
    plan = ReplyPlan(
        language="es", country="MX", ask=Ask(field="out_of_area", city_not_served="Tijuana")
    )
    assert "City they named, where we are not hiring: Tijuana." in instructions(plan)
