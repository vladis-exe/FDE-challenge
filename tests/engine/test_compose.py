from datetime import date

import pytest

from screening.compose import Ask, ReplyPlan, compose_reply, instructions, user_prompt
from screening.config import load_config
from screening.llm import FakeLLM
from screening.messages import display_name, fixed, opening, readback, summarize
from screening.prompts import load_prompt
from screening.schemas import (
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    FieldValue,
    Location,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


def accepted(value) -> FieldValue:
    return FieldValue(value=value, status=FieldStatus.ACCEPTED)


def completed_state(language="es", country="ES", city="barcelona") -> ConversationState:
    state = ConversationState(
        conversation_id="c1",
        channel=Channel.SIM,
        vacancy_id="driver",
        language=language,
        country_hint=country,
    )
    state.profile.fields = {
        "full_name": accepted("Laura Pérez"),
        "has_driver_license": accepted(True),
        "location": accepted(Location(country=country, city=city)),
        "availability": accepted(["part_time", "weekends"]),
        "schedule": accepted(["evening"]),
        "experience": accepted([ExperienceItem(platform="glovo", years=1.5)]),
        "start_date": accepted(date(2026, 10, 19)),
    }
    return state


def plan(**values) -> ReplyPlan:
    return ReplyPlan(**{"language": "es", "country": "ES", "job_title": "Repartidor"} | values)


# Fixed messages


@pytest.mark.parametrize("language", ["es", "en"])
def test_opening_discloses_ai_and_links_privacy(config, language):
    state = ConversationState(
        conversation_id="c1", channel=Channel.SIM, vacancy_id="driver", language=language
    )
    text = opening(state, config)
    assert "Alex" in text
    assert ("(IA)" if language == "es" else "(AI)") in text
    assert config.privacy_url in text
    assert text.endswith("?")


def test_opening_names_the_job_and_its_question_count(config):
    state = ConversationState(conversation_id="c1", channel=Channel.SIM, vacancy_id="kitchen_prep")
    assert "Son 7 preguntas rápidas sobre el puesto de ayudante de cocina" in opening(state, config)


def test_every_fixed_message_has_both_languages():
    catalogue_keys = [
        "opening",
        "readback",
        "close_completed",
        "close_knockout",
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
                values = {"summary": "x", "city": "x", "privacy_url": "x", "job": "x"}
                values |= {"questions": "7", "requirement": "x"}
                text = fixed(key, language=language, country=country, **values)
                assert "{" not in text, (key, language, country)


def test_knockout_close_names_the_requirement():
    spain = fixed(
        "close_knockout", language="es", country="ES", first_name="Laura",
        requirement="carnet de conducir",
    )  # fmt: skip
    assert spain.startswith("Gracias, Laura. Para este puesto es imprescindible tener carnet")
    mexico = fixed("close_knockout", language="es", country="MX", requirement="x")
    assert "indispensable" in mexico and "solicitud" in mexico


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
    state.profile.fields["has_driver_license"] = FieldValue(status=FieldStatus.FLAGGED)
    state.profile.fields["experience"] = accepted([])
    text = summarize(state, config)
    assert "carnet de conducir: lo revisará un reclutador" in text
    assert "sin experiencia en reparto" in text


def test_summary_follows_the_vacancy_and_shows_a_preferred_no(config):
    state = completed_state()
    state.vacancy_id = "kitchen_prep"
    state.profile.fields["has_driver_license"] = accepted(False)
    state.profile.fields["food_handler_certificate"] = accepted(True)
    assert summarize(state, config) == (
        "Laura Pérez, Barcelona, media jornada y fines de semana, noches, "
        "empiezas el lunes 19 de octubre, carnet de conducir: no, "
        "carnet de manipulador de alimentos: sí"
    )  # no delivery experience: it isn't a kitchen_prep field


def test_readback_fits_message_limit(config):
    text = readback(completed_state(), config)
    assert text.startswith("¡Gracias, Laura! Repasemos:")
    assert text.endswith("¿Está todo bien?")
    assert len(text) <= config.message_limits.max_chars


# Composed replies


def test_instructions_follow_plan_order():
    reply = plan(
        country="MX",
        acknowledge=["city: Guadalajara"],
        faq_answer="Hay turnos de mañana, tarde y noche.",
        ask=Ask(field="availability"),
    )
    assert instructions(reply) == (
        "1. Briefly acknowledge what they just told you: city: Guadalajara.\n"
        "2. Answer their question with this approved information, in your own words but "
        'without adding or changing any fact: "Hay turnos de mañana, tarde y noche."\n'
        "3. Ask for: availability."
    )


def test_reask_with_options_and_reason():
    reply = plan(
        language="en",
        ask=Ask(field="city_choice", options=["Madrid", "Barcelona"], retry_reason="two cities"),
    )
    assert "Options: Madrid, Barcelona." in instructions(reply)
    assert "didn't work (two cities)" in instructions(reply)


def test_field_ask_carries_its_label_and_optional_marker():
    ask = Ask(field="has_driver_license", about="si tiene carnet", optional=True)
    assert instructions(plan(ask=ask)) == (
        "1. Ask for: has_driver_license. Ask about: si tiene carnet. "
        "This question is optional for this job."
    )


def test_redirect_names_the_job():
    assert "the Ayudante de cocina application" in instructions(
        plan(job_title="Ayudante de cocina", redirect=True)
    )


def test_unanswered_question_defers_to_recruiter():
    assert "a recruiter will confirm" in instructions(plan(unanswered_question="¿Dan uniforme?"))


def test_user_prompt_has_language_and_vocabulary():
    prompt = user_prompt(plan(country="MX", first_name="Ana"), [])
    assert "Job: Repartidor" in prompt
    assert "Language: Spanish" in prompt
    assert "licencia de manejo, carro, celular" in prompt
    assert "Candidate's first name: Ana" in prompt


def test_compose_reply_uses_static_persona_prompt():
    llm = FakeLLM(
        {"compose": ["¡Genial! ¿Buscas jornada completa, media jornada o fines de semana?"]}
    )
    reply = plan(ask=Ask(field="availability"))
    result = compose_reply(reply, [], llm=llm, limits=load_config().message_limits)
    assert result.text.endswith("?")
    assert result.problems == []
    call = llm.calls_for("compose")[0]
    assert call.system == load_prompt("compose")
    assert call.tier == "fast"


def test_out_of_area_names_the_city_as_not_served():
    reply = plan(ask=Ask(field="out_of_area", city_not_served="Tijuana"))
    assert "City they named, where we are not hiring: Tijuana." in instructions(reply)


def test_a_reply_breaking_the_rules_is_regenerated_once():
    llm = FakeLLM(
        {"compose": ["¡Genial! Anotado. ¿Qué horario? Puedes combinar.", "¿Qué horario?"]}
    )
    reply = plan(ask=Ask(field="schedule"))
    result = compose_reply(reply, [], llm=llm, limits=load_config().message_limits)
    assert result.text == "¿Qué horario?"
    assert len(result.calls) == 2
    assert "text after the question" in result.problems
    assert result.trimmed is False
    retry = llm.calls_for("compose")[1].messages
    assert retry[1] == {
        "role": "assistant",
        "content": "¡Genial! Anotado. ¿Qué horario? Puedes combinar.",
    }
    assert "It broke these rules" in retry[2]["content"]


def test_a_retry_that_still_breaks_the_rules_is_trimmed():
    bad = "¡Genial! Anotado. ¿Qué horario prefieres? Puedes combinar."
    llm = FakeLLM({"compose": [bad, bad]})
    reply = plan(ask=Ask(field="schedule"))
    result = compose_reply(reply, [], llm=llm, limits=load_config().message_limits)
    assert result.text == "Anotado. ¿Qué horario prefieres?"
    assert result.trimmed is True


def test_names_typed_in_lowercase_are_title_cased_for_display_only(config):
    state = completed_state()
    state.profile.fields["full_name"] = accepted("carlos méndez ruiz")
    text = readback(state, config)
    assert text.startswith("¡Gracias, Carlos! Repasemos: Carlos Méndez Ruiz,")
    assert state.profile.fields["full_name"].value == "carlos méndez ruiz"  # stored as typed


def test_a_name_with_its_own_capitals_is_kept(config):
    state = completed_state()
    state.profile.fields["full_name"] = accepted("María de la Fuente")
    assert "María de la Fuente," in summarize(state, config)


def test_under_a_year_of_experience_reads_in_months(config):
    state = completed_state()
    state.profile.fields["experience"] = accepted([ExperienceItem(platform="just_eat", years=0.5)])
    assert "Just Eat 6 meses" in summarize(state, config)


def test_the_read_back_shows_what_they_said_about_a_flagged_answer(config):
    """V8 scenario 13: "lo revisará un reclutador" alone made the candidate keep correcting it."""
    state = completed_state()
    state.profile.fields["has_driver_license"] = FieldValue(
        status=FieldStatus.FLAGGED, note="license expired: caducó en agosto, renueva en 2 semanas"
    )
    assert (
        "carnet de conducir: caducó en agosto, renueva en 2 semanas (lo revisará un reclutador)"
        in summarize(state, config)
    )


# E20 (1): the label is stripped in code, and the retry asks for the text only


def test_a_labelled_retry_never_reaches_the_candidate():
    """A13 live run: the retry answered "Corrected: …" and trim kept it."""
    draft = "Anotado, el lunes 19. Ahora una pregunta. ¿Tienes licencia de manejo? Gracias."
    retry = "Corrected: Anotado, el lunes 19. ¿Tienes licencia de manejo?"
    llm = FakeLLM({"compose": [draft, retry]})
    result = compose_reply(
        plan(ask=Ask(field="x")), [], llm=llm, limits=load_config().message_limits
    )
    assert result.text == "Anotado, el lunes 19. ¿Tienes licencia de manejo?"
    feedback = llm.calls_for("compose")[1].messages[-1]["content"]
    assert "message text only" in feedback


def test_mexico_gets_agendar_in_the_close():
    assert "agendar una entrevista" in fixed("close_completed", language="es", country="MX")
    assert "concertar una entrevista" in fixed("close_completed", language="es", country="ES")


def test_a_question_names_the_thing_in_the_candidates_vocabulary():
    ask = Ask(
        field="food_handler_certificate",
        about="si tiene el carnet",
        term="curso de manejo higiénico de alimentos",
    )
    assert "Call it: curso de manejo higiénico de alimentos." in instructions(plan(ask=ask))


# E21: display names, word by word


@pytest.mark.parametrize(
    "typed, shown",
    [
        ("kevin Ramírez Soto", "Kevin Ramírez Soto"),  # A15: mixed input stayed as typed
        ("iker etxeberria goñi", "Iker Etxeberria Goñi"),
        ("María de la Fuente", "María de la Fuente"),
        ("maría de la fuente", "María de la Fuente"),  # particles stay lowercase
        ("juan de los santos y garcía", "Juan de los Santos y García"),
        ("McDonald", "McDonald"),  # existing capitals are kept
        ("ana mcdonald", "Ana Mcdonald"),  # all lowercase: nothing to keep
        ("joão dos santos", "João dos Santos"),
        ("pieter van dijk", "Pieter van Dijk"),
        ("jean-pierre dupont", "Jean-Pierre Dupont"),
        ("de la cruz", "De la Cruz"),  # a particle first is still capitalized
    ],
)
def test_display_name_capitalizes_word_by_word(typed, shown):
    assert display_name(typed) == shown


@pytest.mark.parametrize(
    "typed, shown",
    [
        ("LAURA PÉREZ", "Laura Pérez"),  # all caps, common on WhatsApp
        ("LAURA DE LA FUENTE", "Laura de la Fuente"),
        ("laura PÉREZ", "Laura Pérez"),
        ("McDonald", "McDonald"),  # mixed case is still kept
        ("ana J. lópez", "Ana J. López"),  # a single capital letter is kept
        ("o'brien", "O'Brien"),
        ("sean o'brien-smith", "Sean O'Brien-Smith"),
    ],
)
def test_display_name_handles_all_caps_and_apostrophes(typed, shown):
    assert display_name(typed) == shown
