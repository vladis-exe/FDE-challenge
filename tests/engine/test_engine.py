"""State machine tests, one or more per row of the transition table in screening/policy.py.

The LLM is a FakeLLM: each test scripts what "extract" read in a message, and
"compose" echoes back the plan it was given, so tests can assert on the plan.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from screening.config import load_config
from screening.engine import EngineContext, handle_message, new_conversation, start
from screening.llm import FakeLLM, LLMError
from screening.schemas import (
    Availability,
    Channel,
    ConversationState,
    FieldStatus,
    InboundMessage,
    Location,
    Schedule,
    Stage,
    Status,
    TurnResult,
)

CONFIG = load_config()
T0 = datetime(2026, 10, 14, 10, 0, tzinfo=UTC)  # Wednesday, midday in Madrid
TOP_LEVEL = {"consent", "confirmation", "question", "faq_id"}


def ext(intent: str = "answer", language: str = "es", **values) -> dict:
    """An Extraction as the fake LLM returns it; field keywords go under "fields"."""
    top = {key: value for key, value in values.items() if key in TOP_LEVEL}
    fields = {key: value for key, value in values.items() if key not in TOP_LEVEL}
    return {"intent": intent, "language": language, "fields": fields, **top}


def echo_plan(system: str, messages: list[dict[str, str]]) -> str:
    plan = messages[-1]["content"].split("<write>\n")[1].split("\n</write>")[0]
    return f"PLAN[{plan}]?"


def fake_summary(system: str, messages: list[dict[str, str]]) -> str:
    return "Resumen para el reclutador."


class Convo:
    def __init__(self, phone: str = "+34600000001", language: str = "es") -> None:
        self.llm = FakeLLM({"extract": [], "compose": echo_plan, "summary": fake_summary})
        self.ctx = EngineContext(config=CONFIG, llm=self.llm)
        state = new_conversation("c1", Channel.SIM, phone=phone, language=language, now=T0)
        self.opening = start(state, now=T0, ctx=self.ctx)
        self.state = self.opening.state
        self.count = 0

    def send(self, extraction: dict | Exception | None, text: str = "...", media="none",
             at: datetime | None = None) -> TurnResult:  # fmt: skip
        if extraction is not None:
            self.llm.scripts["extract"].append(extraction)
        self.count += 1
        message = InboundMessage(
            id=f"m{self.count}",
            text=text,
            received_at=at or T0 + timedelta(minutes=self.count),
            media=media,
        )
        result = handle_message(self.state, message, ctx=self.ctx)
        self.state = result.state
        return result

    def through_license(self) -> None:
        self.send(ext(consent="yes"))
        self.send(ext(full_name="Laura Pérez"))
        self.send(ext(license="yes"))

    def to_confirm(self) -> TurnResult:
        self.through_license()
        self.send(ext(city_text="Gràcia"))
        self.send(ext(availability=["part_time", "weekends"]))
        self.send(ext(schedule=["evening"]))
        self.send(ext(has_experience=True, experience=[{"platform": "Glovo", "months": 18}]))
        return self.send(ext(start_date={"kind": "date", "resolved": "2026-10-19"}))


def text_of(result: TurnResult) -> str:
    return " | ".join(message.text for message in result.outbound)


def event_types(result: TurnResult) -> list[str]:
    return [event.type for event in result.events]


# Starting


def test_new_conversation_reads_country_from_phone_prefix():
    def hint(phone):
        state = new_conversation("c", Channel.WHATSAPP, phone=phone, language=None, now=T0)
        return state.country_hint

    assert hint("+525512345678") == "MX"
    assert hint("+34600000000") == "ES"
    assert hint("+447700900000") is None
    assert hint(None) is None
    assert new_conversation("c", Channel.WEB, phone=None, language=None, now=T0).language == "es"


def test_start_sends_the_opening_with_ai_disclosure():
    convo = Convo()
    opening = convo.opening
    assert len(opening.outbound) == 1
    assert opening.outbound[0].kind == "reply"
    assert "(IA)" in opening.outbound[0].text
    assert event_types(opening) == ["conversation_started"]
    assert opening.state.stage is Stage.CONSENT
    assert opening.state.last_outbound_at == T0
    assert opening.state.transcript_tail[-1].role == "agent"
    assert convo.llm.calls == []  # the opening is fixed text, no LLM call


# Rows 9-11: consent


def test_consent_yes_moves_to_name():
    convo = Convo()
    result = convo.send(ext(consent="yes"))
    assert convo.state.consent_at is not None
    assert convo.state.stage is Stage.NAME
    assert "consent_given" in event_types(result)
    assert "Ask for: full_name." in text_of(result)


def test_consent_declined_closes_and_stores_nothing():
    convo = Convo()
    result = convo.send(ext(consent="no"))
    assert convo.state.status is Status.OPTED_OUT
    assert convo.state.stage is Stage.DONE
    assert convo.state.consent_at is None
    assert result.outbound[0].kind == "close"
    assert "no guardaremos tus datos" in text_of(result)


def test_unclear_consent_asks_again():
    convo = Convo()
    result = convo.send(ext(intent="smalltalk"), text="hola")
    assert convo.state.stage is Stage.CONSENT
    assert "Ask for: consent." in text_of(result)


def test_answers_right_away_count_as_consent_and_skip_ahead():
    convo = Convo()
    result = convo.send(ext(full_name="Laura Pérez", license="yes", city_text="Gràcia, Barcelona"))
    profile = convo.state.profile
    assert convo.state.consent_at is not None
    assert profile.full_name.value == "Laura Pérez"
    assert profile.has_driver_license.value is True
    assert profile.location.value == Location(country="ES", city="barcelona")
    assert convo.state.stage is Stage.AVAILABILITY
    assert "Ask for: availability." in text_of(result)
    assert event_types(result).count("field_accepted") == 3


# Row 16, 18, 19, 21: the happy path


def test_happy_path_ends_qualified():
    convo = Convo()
    readback = convo.to_confirm()
    assert convo.state.stage is Stage.CONFIRM
    assert readback.outbound[0].text.startswith("¡Gracias, Laura! Repasemos:")
    assert "Barcelona, media jornada y fines de semana" in readback.outbound[0].text

    result = convo.send(ext(confirmation="confirm"), text="sí, todo bien")

    state = convo.state
    assert state.status is Status.QUALIFIED
    assert state.stage is Stage.DONE
    assert result.outbound[0].kind == "close"
    assert "reclutador" in result.outbound[0].text
    assert "status_changed" in event_types(result)
    profile = state.profile
    assert profile.availability.value == [Availability.PART_TIME, Availability.WEEKENDS]
    assert profile.schedule.value == [Schedule.EVENING]
    assert profile.experience.value[0].years == 1.5
    assert profile.start_date.value == date(2026, 10, 19)
    assert profile.start_date.source_message_id == "m8"
    assert state.review_reasons == []


def test_acknowledges_what_was_just_recorded():
    convo = Convo()
    convo.send(ext(consent="yes"))
    result = convo.send(ext(full_name="Laura Pérez"))
    assert "acknowledge what they just told you: name: Laura Pérez" in text_of(result)


def test_no_experience_is_accepted():
    convo = Convo()
    convo.through_license()
    convo.send(ext(city_text="Madrid"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["morning"]))
    convo.send(ext(has_experience=False))
    assert convo.state.profile.experience.value == []
    assert convo.state.profile.experience.status is FieldStatus.ACCEPTED
    assert convo.state.stage is Stage.START_DATE


# Name


def test_first_name_only_gets_one_surname_reask_then_combines():
    convo = Convo()
    convo.send(ext(consent="yes"))
    result = convo.send(ext(full_name="Laura"))
    assert "Ask for: surname." in text_of(result)
    assert convo.state.stage is Stage.NAME

    convo.send(ext(full_name="Pérez"))
    assert convo.state.profile.full_name.value == "Laura Pérez"
    assert convo.state.profile.full_name.status is FieldStatus.ACCEPTED
    assert convo.state.stage is Stage.LICENSE


# License knockout and review


def test_no_license_disqualifies_at_once():
    convo = Convo(phone="+525500000001")
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Pedro Gómez"))
    result = convo.send(ext(license="no"))
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "no_license"
    assert convo.state.stage is Stage.DONE
    assert result.outbound[0].kind == "close"
    assert "licencia de manejo" in result.outbound[0].text
    assert "knockout_failed" in event_types(result)


def test_no_license_volunteered_with_consent_disqualifies():
    convo = Convo()
    convo.send(ext(consent="yes", full_name="Pedro Gómez", license="no"))
    assert convo.state.disqualify_reason == "no_license"


def test_expired_license_is_flagged_and_screening_continues():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    result = convo.send(ext(license="expired"))
    license = convo.state.profile.has_driver_license
    assert license.status is FieldStatus.FLAGGED
    assert license.value is None
    assert license.note == "license expired"
    assert convo.state.review_reasons == ["license_unclear"]
    assert convo.state.stage is Stage.LOCATION
    assert "field_flagged" in event_types(result)


def test_flagged_field_makes_the_outcome_needs_review():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    convo.send(ext(license="expired"))
    convo.send(ext(city_text="Deusto"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["flexible"]))
    convo.send(ext(has_experience=True, experience=[{"platform": "glovo", "years": 3}]))
    convo.send(ext(start_date={"kind": "date", "resolved": "2026-12-01"}))
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.NEEDS_REVIEW


def test_vague_license_is_reasked_twice_then_flagged():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Ana Ruiz"))
    first = convo.send(ext(license="vague"))
    assert "didn't work (not a clear yes or no)" in text_of(first)
    convo.send(ext(license="vague"))
    assert convo.state.profile.has_driver_license.attempts == 2
    assert convo.state.stage is Stage.LICENSE

    convo.send(ext(license="vague"))
    license = convo.state.profile.has_driver_license
    assert license.status is FieldStatus.FLAGGED
    assert "unresolved:has_driver_license" in convo.state.review_reasons
    assert convo.state.stage is Stage.LOCATION  # moves on, never loops


# Location: rows 12-15 and 17


def test_unserved_city_asks_for_confirmation_then_disqualifies():
    convo = Convo()
    convo.through_license()
    asked = convo.send(ext(city_text="Zaragoza"))
    assert convo.state.pending_confirmation == {"type": "out_of_area", "city_text": "Zaragoza"}
    assert "Ask for: out_of_area." in text_of(asked)
    assert "where we are not hiring: Zaragoza" in text_of(asked)
    assert convo.state.status is Status.IN_PROGRESS

    result = convo.send(ext(confirmation="confirm"), text="sí, en Zaragoza")
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "out_of_area"
    assert result.outbound[0].kind == "close"
    assert "Zaragoza" in result.outbound[0].text


def test_repeating_the_unserved_city_counts_as_confirming():
    convo = Convo()
    convo.through_license()
    convo.send(ext(city_text="Zaragoza"))
    convo.send(ext(city_text="zaragoza"))
    assert convo.state.disqualify_reason == "out_of_area"


def test_served_city_after_an_unserved_one_is_accepted():
    convo = Convo()
    convo.through_license()
    convo.send(ext(city_text="Zaragoza"))
    convo.send(ext(confirmation="deny", city_text="Madrid"), text="no, trabajaría en Madrid")
    assert convo.state.pending_confirmation is None
    assert convo.state.profile.location.value == Location(country="ES", city="madrid")
    assert convo.state.stage is Stage.AVAILABILITY


def test_denying_the_unserved_city_asks_for_the_city_again():
    convo = Convo()
    convo.through_license()
    convo.send(ext(city_text="Zaragoza"))
    result = convo.send(ext(confirmation="deny"))
    assert convo.state.pending_confirmation is None
    assert convo.state.profile.location.attempts == 1
    assert "Ask for: location." in text_of(result)


def test_ambiguous_city_offers_options():
    convo = Convo(phone="+528100000012")
    convo.through_license()
    result = convo.send(ext(city_text="san pedro"))
    assert "Ask for: city_choice. Options: Guadalajara, Monterrey." in text_of(result) or (
        "Ask for: city_choice. Options: Monterrey, Guadalajara." in text_of(result)
    )
    assert convo.state.profile.location.attempts == 1

    convo.send(ext(city_text="Monterrey"))
    assert convo.state.profile.location.value == Location(country="MX", city="monterrey")


def test_city_never_given_is_flagged_after_two_reasks():
    convo = Convo()
    convo.through_license()
    for _ in range(2):
        result = convo.send(ext(), text="por la zona sur")
        assert "Ask for: location." in text_of(result)
    convo.send(ext(), text="eso se lo digo al reclutador")
    location = convo.state.profile.location
    assert location.status is FieldStatus.FLAGGED
    assert convo.state.review_reasons == ["unresolved:location"]
    assert convo.state.stage is Stage.AVAILABILITY


# FAQ and questions


def test_question_uses_no_attempt_and_gets_the_approved_answer():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="question", question="¿Cuánto pagan?", faq_id="pay"))
    assert convo.state.profile.location.attempts == 0
    assert "El pago depende de la ciudad" in text_of(result)
    assert "Ask for: location." in text_of(result)
    faq_events = [event for event in result.events if event.type == "faq_answered"]
    assert faq_events[0].data == {"faq_id": "pay"}


def test_uncovered_question_defers_to_a_recruiter():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="question", question="¿Dan uniforme?"))
    assert "a recruiter will confirm" in text_of(result)


def test_answer_with_question_does_both():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(city_text="Madrid", question="¿Cuánto pagan?", faq_id="pay"))
    assert convo.state.profile.location.status is FieldStatus.ACCEPTED
    assert "El pago depende" in text_of(result)
    assert "Ask for: availability." in text_of(result)


def test_unknown_faq_id_is_treated_as_uncovered():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="question", question="¿Hay bonus?", faq_id="bonus"))
    assert "a recruiter will confirm" in text_of(result)


# Rows 5-8: opt-out, human, off-topic, abuse, injection


def test_opt_out_closes_and_then_stays_silent():
    convo = Convo()
    convo.send(ext(consent="yes"))
    result = convo.send(ext(intent="opt_out"), text="stop")
    assert convo.state.status is Status.OPTED_OUT
    assert result.outbound[0].kind == "close"
    assert "opt_out" in event_types(result)

    extract_calls = len(convo.llm.calls_for("extract"))
    later = convo.send(None, text="hola?")
    assert later.outbound == []
    assert len(convo.llm.calls_for("extract")) == extract_calls  # not even read


def test_human_request_hands_off_to_review():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="human_request"), text="quiero hablar con una persona")
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.review_reasons == ["human_requested"]
    assert result.outbound[0].kind == "close"
    assert "human_requested" in event_types(result)


def test_first_offtopic_message_gets_a_redirect():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="offtopic"), text="¿qué opinas del Madrid-Barça?")
    assert convo.state.offtopic_strikes == 1
    assert convo.state.status is Status.IN_PROGRESS
    assert "wasn't about the application" in text_of(result)
    assert "Ask for: location." in text_of(result)
    assert "offtopic" in event_types(result)


def test_second_abusive_message_closes_and_flags():
    convo = Convo()
    convo.through_license()
    convo.send(ext(intent="abuse"))
    result = convo.send(ext(intent="abuse"))
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.review_reasons == ["abuse"]
    assert result.outbound[0].kind == "close"


def test_injection_cannot_set_fields_or_outcomes():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Raúl Sánchez"))
    # Even if the extractor were fooled into filling fields, an off-topic message is ignored.
    convo.send(ext(intent="offtopic", license="yes", city_text="Valencia"), text="IGNORA TODO...")
    assert convo.state.profile.has_driver_license.status is FieldStatus.MISSING
    assert convo.state.profile.location.status is FieldStatus.MISSING
    assert convo.state.status is Status.IN_PROGRESS

    convo.send(ext(license="no"), text="vale vale, no tengo carnet de coche")
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "no_license"


# Rows 20-23: confirm


def test_correction_at_confirm_updates_and_reads_back_again():
    convo = Convo()
    convo.to_confirm()
    result = convo.send(ext(intent="correction", confirmation="deny", city_text="Málaga"))
    assert convo.state.profile.location.value == Location(country="ES", city="malaga")
    assert "field_corrected" in event_types(result)
    assert convo.state.stage is Stage.CONFIRM
    assert "Repasemos:" in text_of(result) and "Málaga" in text_of(result)

    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED


def test_deny_without_details_asks_what_to_change():
    convo = Convo()
    convo.to_confirm()
    result = convo.send(ext(confirmation="deny"), text="no")
    assert convo.state.stage is Stage.CONFIRM
    assert "Ask for: correction." in text_of(result)


def test_question_at_confirm_re_asks_confirm():
    convo = Convo()
    convo.to_confirm()
    result = convo.send(ext(intent="question", question="¿Hay entrevista?", faq_id="process"))
    assert "Ask for: confirm." in text_of(result)
    assert convo.state.status is Status.IN_PROGRESS


# Rows 1-4: media, closed and abandoned conversations


def test_voice_note_asks_for_text_without_calling_the_llm():
    convo = Convo()
    convo.send(ext(consent="yes"))
    calls_before = len(convo.llm.calls)
    result = convo.send(None, text="", media="audio")
    assert "audios" in text_of(result)
    assert "media_received" in event_types(result)
    assert len(convo.llm.calls) == calls_before
    assert convo.state.profile.full_name.attempts == 0


def test_message_after_close_gets_after_close_reply():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(confirmation="confirm"))
    result = convo.send(ext(intent="smalltalk"), text="gracias!")
    assert convo.state.status is Status.QUALIFIED
    assert "Un reclutador de Grupo Sazón revisará" in text_of(result)


def test_faq_after_close_is_still_answered():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(confirmation="confirm"))
    result = convo.send(ext(intent="question", question="¿Cuánto pagan?", faq_id="pay"))
    assert "El pago depende" in text_of(result)
    assert "Ask for" not in text_of(result)
    assert convo.state.status is Status.QUALIFIED


def test_late_reply_reopens_an_abandoned_conversation():
    convo = Convo()
    convo.through_license()
    convo.state = convo.state.model_copy(update={"status": Status.ABANDONED})
    result = convo.send(ext(city_text="Madrid"))
    assert convo.state.status is Status.IN_PROGRESS
    assert convo.state.profile.location.status is FieldStatus.ACCEPTED
    assert "status_changed" in event_types(result)


# Language, dates and bookkeeping


def test_replies_follow_the_language_of_the_latest_message():
    convo = Convo()
    convo.send(ext(consent="yes"))
    result = convo.send(ext(language="en", full_name="Tom Baker", license="no"))
    assert convo.state.language == "en"
    assert "driver's license" in text_of(result)


def test_asap_start_date_uses_the_candidates_local_date():
    convo = Convo(phone="+525500000002")
    convo.through_license()
    convo.send(ext(city_text="CDMX"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["morning"]))
    convo.send(ext(has_experience=False))
    # 02:00 UTC on Thursday is still Wednesday evening in Mexico City.
    convo.send(ext(start_date={"kind": "asap"}), at=datetime(2026, 10, 15, 2, 0, tzinfo=UTC))
    assert convo.state.profile.start_date.value == date(2026, 10, 14)


def test_inbound_resets_reminders_and_records_times():
    convo = Convo()
    convo.state = convo.state.model_copy(update={"reminders_sent": 2})
    at = T0 + timedelta(hours=1)
    convo.send(ext(consent="yes"), at=at)
    assert convo.state.reminders_sent == 0
    assert convo.state.last_inbound_at == at
    assert convo.state.last_outbound_at == at


def test_transcript_tail_is_capped():
    convo = Convo()
    for _ in range(10):
        convo.send(ext(intent="smalltalk"))
    assert len(convo.state.transcript_tail) == CONFIG.transcript_tail_size


def test_llm_calls_are_recorded_as_events():
    convo = Convo()
    result = convo.send(ext(consent="yes"))
    calls = [event for event in result.events if event.type == "llm_call"]
    assert [event.data["purpose"] for event in calls] == ["extract", "compose"]
    assert set(calls[0].data) >= {"model", "input_tokens", "output_tokens", "latency_ms"}


# LLM failures


@pytest.mark.parametrize("failing", ["extract", "compose"])
def test_llm_failure_sends_holding_reply_and_keeps_state(failing):
    convo = Convo()
    convo.send(ext(consent="yes"))
    before = convo.state
    if failing == "extract":
        result = convo.send(LLMError("down"))
    else:
        convo.llm.scripts["compose"] = [LLMError("down")]
        result = convo.send(ext(full_name="Laura Pérez"))

    assert "problema técnico" in text_of(result)
    assert "llm_error" in event_types(result)
    after: ConversationState = convo.state
    assert after.profile == before.profile
    assert after.stage is before.stage
    assert after.status is before.status
    assert after.transcript_tail[-2].role == "candidate"
    assert after.transcript_tail[-1].role == "agent"


# Summary (E8)


def test_summary_is_written_when_the_screening_ends():
    convo = Convo()
    convo.to_confirm()
    assert convo.state.summary is None
    result = convo.send(ext(confirmation="confirm"))
    assert convo.state.summary == "Resumen para el reclutador."
    summary_call = convo.llm.calls_for("summary")[0]
    assert summary_call.tier == "smart"
    assert '"status": "qualified"' in summary_call.messages[0]["content"]
    assert [e.data["purpose"] for e in result.events if e.type == "llm_call"][-1] == "summary"


def test_failed_summary_still_sends_the_close():
    convo = Convo()
    convo.llm.scripts["summary"] = [LLMError("down")]
    convo.through_license()
    result = convo.send(ext(intent="human_request"))
    assert result.outbound[0].kind == "close"
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.summary is None
    assert "llm_error" in event_types(result)


def test_opt_out_summary_never_goes_to_the_llm():
    convo = Convo()
    convo.send(ext(consent="no"))
    assert convo.state.summary == "Opted out at stage done."
    assert convo.llm.calls_for("summary") == []


def test_no_summary_while_in_progress_or_after_close():
    convo = Convo()
    convo.through_license()
    assert convo.llm.calls_for("summary") == []
    convo.send(ext(license="no"))  # closes: one summary
    convo.send(ext(intent="smalltalk"))  # after close: no new summary
    assert len(convo.llm.calls_for("summary")) == 1
