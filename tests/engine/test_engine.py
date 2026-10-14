"""State machine tests, one or more per row of the transition table in screening/policy.py.

The LLM is a FakeLLM: each test scripts what "extract" read in a message, and
"compose" echoes back the plan it was given, so tests can assert on the plan.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from screening.config import load_config
from screening.engine import EngineContext, handle_message, new_conversation, start
from screening.fields import typed
from screening.llm import FakeLLM, LLMError
from screening.schemas import (
    Channel,
    ConversationState,
    ExperienceItem,
    FieldStatus,
    FieldValue,
    InboundMessage,
    Location,
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


def plan_of(messages: list[dict[str, str]]) -> str:
    return messages[0]["content"].split("<write>\n")[1].split("\n</write>")[0]


def fake_compose(system: str, messages: list[dict[str, str]]) -> str:
    """A reply that passes the message rules; tests read the plan from the request."""
    return "Vale. ¿Seguimos?" if "Ask for:" in plan_of(messages) else "Vale."


def fake_summary(system: str, messages: list[dict[str, str]]) -> str:
    return "Resumen para el reclutador."


class Convo:
    def __init__(
        self, phone: str = "+34600000001", language: str = "es", vacancy: str = "driver"
    ) -> None:
        self.llm = FakeLLM({"extract": [], "compose": fake_compose, "summary": fake_summary})
        self.ctx = EngineContext(config=CONFIG, llm=self.llm)
        self.vacancy = CONFIG.vacancy(vacancy)
        state = new_conversation(
            "c1", Channel.SIM, vacancy_id=vacancy, phone=phone, language=language, now=T0
        )
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
        calls_before = len(self.llm.calls)
        # Through JSON and back, as the app stores it between turns.
        stored = ConversationState.model_validate(self.state.model_dump(mode="json"))
        result = handle_message(stored, message, ctx=self.ctx)
        self.state = result.state
        # What Alex said this turn: fixed texts as sent, composed replies as their plans.
        plans = [
            plan_of(call.messages)
            for call in self.llm.calls[calls_before:]
            if call.purpose == "compose"
        ]
        self.said = " | ".join([message.text for message in result.outbound] + plans)
        return result

    def field(self, name: str) -> FieldValue:
        return self.state.profile.fields.get(name, FieldValue())

    def value(self, name: str):
        return typed(self.vacancy.field(name), self.field(name).value)

    @property
    def asking(self) -> str:
        """The field being asked, or the stage when no field is."""
        state = self.state
        return state.current_field if state.stage is Stage.COLLECTING else state.stage.value

    def through_license(self) -> None:
        self.send(ext(consent="yes"))
        self.send(ext(full_name="Laura Pérez"))
        self.send(ext(has_driver_license="yes"))

    def to_confirm(self) -> TurnResult:
        self.through_license()
        self.send(ext(location="Gràcia"))
        self.send(ext(availability=["part_time", "weekends"]))
        self.send(ext(schedule=["evening"]))
        self.send(
            ext(experience={"has_experience": True, "items": [{"platform": "Glovo", "months": 18}]})
        )
        return self.send(ext(start_date={"kind": "date", "resolved": "2026-10-19"}))


def event_types(result: TurnResult) -> list[str]:
    return [event.type for event in result.events]


# Starting


def test_new_conversation_reads_country_from_phone_prefix():
    def hint(phone):
        state = new_conversation(
            "c", Channel.WHATSAPP, vacancy_id="driver", phone=phone, language=None, now=T0
        )
        return state.country_hint

    assert hint("+525512345678") == "MX"
    assert hint("+34600000000") == "ES"
    assert hint("+447700900000") is None
    assert hint(None) is None
    state = new_conversation(
        "c", Channel.WEB, vacancy_id="driver", phone=None, language=None, now=T0
    )
    assert state.language == "es"
    assert state.vacancy_id == "driver"


def test_start_rejects_an_unknown_vacancy():
    state = new_conversation(
        "c", Channel.WEB, vacancy_id="astronaut", phone=None, language=None, now=T0
    )
    with pytest.raises(KeyError, match="driver, kitchen_prep"):
        start(state, now=T0, ctx=EngineContext(config=CONFIG, llm=FakeLLM()))


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
    assert convo.asking == "full_name"
    assert "consent_given" in event_types(result)
    assert "Ask for: full_name." in convo.said


def test_consent_declined_closes_and_stores_nothing():
    convo = Convo()
    result = convo.send(ext(consent="no"))
    assert convo.state.status is Status.OPTED_OUT
    assert convo.state.stage is Stage.DONE
    assert convo.state.consent_at is None
    assert result.outbound[0].kind == "close"
    assert "no guardaremos tus datos" in convo.said


def test_unclear_consent_asks_again():
    convo = Convo()
    convo.send(ext(intent="smalltalk"), text="hola")
    assert convo.asking == "consent"
    assert "Ask for: consent." in convo.said


def test_answers_right_away_count_as_consent_and_skip_ahead():
    convo = Convo()
    result = convo.send(
        ext(full_name="Laura Pérez", has_driver_license="yes", location="Gràcia, Barcelona")
    )
    assert convo.state.consent_at is not None
    assert convo.value("full_name") == "Laura Pérez"
    assert convo.value("has_driver_license") is True
    assert convo.value("location") == Location(country="ES", city="barcelona")
    assert convo.asking == "availability"
    assert "Ask for: availability." in convo.said
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
    assert convo.value("availability") == ["part_time", "weekends"]
    assert convo.value("schedule") == ["evening"]
    assert convo.value("experience") == [ExperienceItem(platform="glovo", years=1.5)]
    assert convo.value("start_date") == date(2026, 10, 19)
    assert convo.field("start_date").source_message_id == "m8"
    assert state.review_reasons == []
    assert state.preference_score == 0.0


def test_acknowledges_what_was_just_recorded():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Laura Pérez"))
    assert "acknowledge what they just told you: name: Laura Pérez" in convo.said


def test_no_experience_is_accepted():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Madrid"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["morning"]))
    convo.send(ext(experience={"has_experience": False}))
    assert convo.value("experience") == []
    assert convo.field("experience").status is FieldStatus.ACCEPTED
    assert convo.asking == "start_date"


# Name


def test_first_name_only_gets_one_surname_reask_then_combines():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Laura"))
    assert "Ask for: surname." in convo.said
    assert convo.asking == "full_name"

    convo.send(ext(full_name="Pérez"))
    assert convo.value("full_name") == "Laura Pérez"
    assert convo.field("full_name").status is FieldStatus.ACCEPTED
    assert convo.asking == "has_driver_license"


# License knockout and review


def test_no_license_disqualifies_at_once():
    convo = Convo(phone="+525500000001")
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Pedro Gómez"))
    result = convo.send(ext(has_driver_license="no"))
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "no_license"
    assert convo.state.stage is Stage.DONE
    assert result.outbound[0].kind == "close"
    assert "licencia de manejo" in result.outbound[0].text
    assert "knockout_failed" in event_types(result)


def test_no_license_volunteered_with_consent_disqualifies():
    convo = Convo()
    convo.send(ext(consent="yes", full_name="Pedro Gómez", has_driver_license="no"))
    assert convo.state.disqualify_reason == "no_license"


def test_expired_license_is_flagged_and_screening_continues():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    result = convo.send(ext(has_driver_license="expired"))
    license = convo.field("has_driver_license")
    assert license.status is FieldStatus.FLAGGED
    assert license.value is None
    assert license.note == "license expired"
    assert convo.state.review_reasons == ["license_unclear"]
    assert convo.asking == "location"
    assert "field_flagged" in event_types(result)


def test_flagged_field_makes_the_outcome_needs_review():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    convo.send(ext(has_driver_license="expired"))
    convo.send(ext(location="Deusto"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["flexible"]))
    convo.send(ext(experience={"items": [{"platform": "glovo", "years": 3}]}))
    convo.send(ext(start_date={"kind": "date", "resolved": "2026-12-01"}))
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.NEEDS_REVIEW


def test_vague_license_is_reasked_twice_then_flagged():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Ana Ruiz"))
    convo.send(ext(has_driver_license="vague"))
    assert "didn't work (not a clear yes or no)" in convo.said
    convo.send(ext(has_driver_license="vague"))
    assert convo.field("has_driver_license").attempts == 2
    assert convo.asking == "has_driver_license"

    convo.send(ext(has_driver_license="vague"))
    license = convo.field("has_driver_license")
    assert license.status is FieldStatus.FLAGGED
    assert "unresolved:has_driver_license" in convo.state.review_reasons
    assert convo.asking == "location"  # moves on, never loops


# Location: rows 12-15 and 17


def test_unserved_city_asks_for_confirmation_then_disqualifies():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Zaragoza"))
    assert convo.state.pending_confirmation == {
        "type": "out_of_area",
        "field": "location",
        "city_text": "Zaragoza",
    }
    assert "Ask for: out_of_area." in convo.said
    assert "where we are not hiring: Zaragoza" in convo.said
    assert convo.state.status is Status.IN_PROGRESS

    result = convo.send(ext(confirmation="confirm"), text="sí, en Zaragoza")
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "out_of_area"
    assert result.outbound[0].kind == "close"
    assert "Zaragoza" in result.outbound[0].text


def test_repeating_the_unserved_city_counts_as_confirming():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Zaragoza"))
    convo.send(ext(location="zaragoza"))
    assert convo.state.disqualify_reason == "out_of_area"


def test_served_city_after_an_unserved_one_is_accepted():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Zaragoza"))
    convo.send(ext(confirmation="deny", location="Madrid"), text="no, trabajaría en Madrid")
    assert convo.state.pending_confirmation is None
    assert convo.value("location") == Location(country="ES", city="madrid")
    assert convo.asking == "availability"


def test_denying_the_unserved_city_asks_for_the_city_again():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Zaragoza"))
    convo.send(ext(confirmation="deny"))
    assert convo.state.pending_confirmation is None
    assert convo.field("location").attempts == 1
    assert "Ask for: location." in convo.said


def test_ambiguous_city_offers_options():
    convo = Convo(phone="+528100000012")
    convo.through_license()
    convo.send(ext(location="san pedro"))
    assert "Ask for: city_choice. Options: Guadalajara, Monterrey." in convo.said or (
        "Ask for: city_choice. Options: Monterrey, Guadalajara." in convo.said
    )
    assert convo.field("location").attempts == 1

    convo.send(ext(location="Monterrey"))
    assert convo.value("location") == Location(country="MX", city="monterrey")


def test_city_never_given_is_flagged_after_two_reasks():
    convo = Convo()
    convo.through_license()
    for _ in range(2):
        convo.send(ext(), text="por la zona sur")
        assert "Ask for: location." in convo.said
    convo.send(ext(), text="eso se lo digo al reclutador")
    location = convo.field("location")
    assert location.status is FieldStatus.FLAGGED
    assert convo.state.review_reasons == ["unresolved:location"]
    assert convo.asking == "availability"


# FAQ and questions


def test_question_uses_no_attempt_and_gets_the_approved_answer():
    convo = Convo()
    convo.through_license()
    result = convo.send(ext(intent="question", question="¿Cuánto pagan?", faq_id="pay"))
    assert convo.field("location").attempts == 0
    assert "El pago depende de la ciudad" in convo.said
    assert "Ask for: location." in convo.said
    faq_events = [event for event in result.events if event.type == "faq_answered"]
    assert faq_events[0].data == {"faq_id": "pay"}


def test_uncovered_question_defers_to_a_recruiter():
    convo = Convo()
    convo.through_license()
    convo.send(ext(intent="question", question="¿Dan uniforme?"))
    assert "a recruiter will confirm" in convo.said


def test_answer_with_question_does_both():
    convo = Convo()
    convo.through_license()
    convo.send(ext(location="Madrid", question="¿Cuánto pagan?", faq_id="pay"))
    assert convo.field("location").status is FieldStatus.ACCEPTED
    assert "El pago depende" in convo.said
    assert "Ask for: availability." in convo.said


def test_unknown_faq_id_is_treated_as_uncovered():
    convo = Convo()
    convo.through_license()
    convo.send(ext(intent="question", question="¿Hay bonus?", faq_id="bonus"))
    assert "a recruiter will confirm" in convo.said


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
    assert "wasn't about the application" in convo.said
    assert "Ask for: location." in convo.said
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
    convo.send(
        ext(intent="offtopic", has_driver_license="yes", location="Valencia"), text="IGNORA TODO..."
    )
    assert convo.field("has_driver_license").status is FieldStatus.MISSING
    assert convo.field("location").status is FieldStatus.MISSING
    assert convo.state.status is Status.IN_PROGRESS

    convo.send(ext(has_driver_license="no"), text="vale vale, no tengo carnet de coche")
    assert convo.state.status is Status.DISQUALIFIED
    assert convo.state.disqualify_reason == "no_license"


# Rows 20-23: confirm


def test_correction_at_confirm_updates_and_reads_back_again():
    convo = Convo()
    convo.to_confirm()
    result = convo.send(ext(intent="correction", confirmation="deny", location="Málaga"))
    assert convo.value("location") == Location(country="ES", city="malaga")
    assert "field_corrected" in event_types(result)
    assert convo.state.stage is Stage.CONFIRM
    assert "Repasemos:" in convo.said and "Málaga" in convo.said

    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED


def test_deny_without_details_asks_what_to_change():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(confirmation="deny"), text="no")
    assert convo.state.stage is Stage.CONFIRM
    assert "Ask for: correction." in convo.said


def test_question_at_confirm_re_asks_confirm():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(intent="question", question="¿Hay entrevista?", faq_id="process"))
    assert "Ask for: confirm." in convo.said
    assert convo.state.status is Status.IN_PROGRESS


# Rows 1-4: media, closed and abandoned conversations


def test_voice_note_asks_for_text_without_calling_the_llm():
    convo = Convo()
    convo.send(ext(consent="yes"))
    calls_before = len(convo.llm.calls)
    result = convo.send(None, text="", media="audio")
    assert "audios" in convo.said
    assert "media_received" in event_types(result)
    assert len(convo.llm.calls) == calls_before
    assert convo.field("full_name").attempts == 0


def test_message_after_close_gets_after_close_reply():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(confirmation="confirm"))
    convo.send(ext(intent="smalltalk"), text="gracias!")
    assert convo.state.status is Status.QUALIFIED
    assert "Un reclutador de Grupo Sazón revisará" in convo.said


def test_faq_after_close_is_still_answered():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(confirmation="confirm"))
    convo.send(ext(intent="question", question="¿Cuánto pagan?", faq_id="pay"))
    assert "El pago depende" in convo.said
    assert "Ask for" not in convo.said
    assert convo.state.status is Status.QUALIFIED


def test_late_reply_reopens_an_abandoned_conversation():
    convo = Convo()
    convo.through_license()
    convo.state = convo.state.model_copy(update={"status": Status.ABANDONED})
    result = convo.send(ext(location="Madrid"))
    assert convo.state.status is Status.IN_PROGRESS
    assert convo.field("location").status is FieldStatus.ACCEPTED
    assert "status_changed" in event_types(result)


# Language, dates and bookkeeping


def test_replies_follow_the_language_of_the_latest_message():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(language="en", full_name="Tom Baker", has_driver_license="no"))
    assert convo.state.language == "en"
    assert "driver's license" in convo.said


def test_asap_start_date_uses_the_candidates_local_date():
    convo = Convo(phone="+525500000002")
    convo.through_license()
    convo.send(ext(location="CDMX"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["morning"]))
    convo.send(ext(experience={"has_experience": False}))
    # 02:00 UTC on Thursday is still Wednesday evening in Mexico City.
    convo.send(ext(start_date={"kind": "asap"}), at=datetime(2026, 10, 15, 2, 0, tzinfo=UTC))
    assert convo.value("start_date") == date(2026, 10, 14)


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

    assert "problema técnico" in convo.said
    assert "llm_error" in event_types(result)
    after: ConversationState = convo.state
    assert after.profile.model_dump(mode="json") == before.profile.model_dump(mode="json")
    assert (after.stage, after.current_field) == (before.stage, before.current_field)
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
    convo.send(ext(has_driver_license="no"))  # closes: one summary
    convo.send(ext(intent="smalltalk"))  # after close: no new summary
    assert len(convo.llm.calls_for("summary")) == 1


# Rows 20-24: the read-back loop evals found (status/evals.md)


def test_a_restatement_at_the_read_back_counts_as_confirming():
    convo = Convo()
    convo.to_confirm()
    result = convo.send(ext(location="Barcelona"), text="todo bien, vivo en Barcelona")
    assert convo.state.status is Status.QUALIFIED
    assert "Repasemos:" not in convo.said  # no second read-back
    assert "field_corrected" not in event_types(result)


def test_restating_a_flagged_answer_does_not_loop_either():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    convo.send(ext(has_driver_license="expired"))
    convo.send(ext(location="Deusto"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["flexible"]))
    convo.send(ext(experience={"has_experience": False}))
    convo.send(ext(start_date={"kind": "date", "resolved": "2026-12-01"}))
    convo.send(ext(has_driver_license="expired"), text="caducó en agosto, ya lo dije")
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.review_reasons == ["license_unclear"]


def test_saying_no_without_details_is_capped():
    convo = Convo()
    convo.to_confirm()
    for _ in range(2):
        convo.send(ext(confirmation="deny"), text="no")
        assert "Ask for: correction." in convo.said
    convo.send(ext(confirmation="deny"), text="que no")
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.review_reasons == ["unresolved:confirm"]


def test_real_corrections_are_capped_too():
    convo = Convo()
    convo.to_confirm()
    convo.send(ext(intent="correction", location="Málaga"))
    convo.send(ext(intent="correction", schedule=["morning"]))
    assert convo.state.stage is Stage.CONFIRM
    assert "Repasemos:" in convo.said
    convo.send(ext(intent="correction", availability=["full_time"]))
    assert convo.value("availability") == ["full_time"]  # the last correction still counts
    assert convo.state.status is Status.NEEDS_REVIEW
    assert convo.state.review_reasons == ["unresolved:confirm"]


def test_questions_at_the_read_back_use_no_round():
    convo = Convo()
    convo.to_confirm()
    for _ in range(3):
        convo.send(ext(intent="question", question="¿Hay entrevista?", faq_id="process"))
    assert convo.state.status is Status.IN_PROGRESS
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED


# Vacancies (CONTRACTS §7): kitchen_prep, where the license is only preferred


def kitchen_through_required() -> Convo:
    convo = Convo(vacancy="kitchen_prep")
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Ana Ruiz"))
    convo.send(ext(location="Malasaña"))
    convo.send(ext(availability=["full_time"]))
    convo.send(ext(schedule=["morning"]))
    convo.send(ext(start_date={"kind": "asap"}))
    return convo


def test_preferred_fields_come_after_every_required_one_and_say_optional():
    convo = kitchen_through_required()
    assert convo.asking == "has_driver_license"
    assert "Ask for: has_driver_license." in convo.said
    assert "This question is optional for this job." in convo.said


def test_no_license_never_disqualifies_when_it_is_only_preferred():
    convo = kitchen_through_required()
    result = convo.send(ext(has_driver_license="no"))
    assert convo.state.status is Status.IN_PROGRESS
    assert convo.value("has_driver_license") is False
    assert "knockout_failed" not in event_types(result)
    convo.send(ext(food_handler_certificate="no"))
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED
    assert convo.state.preference_score == 0.0


def test_preferred_answers_add_their_weights():
    convo = kitchen_through_required()
    convo.send(ext(has_driver_license="yes"))
    assert convo.state.preference_score == 1.5
    convo.send(ext(food_handler_certificate="yes"))
    assert convo.state.preference_score == 2.5
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED


def test_two_candidates_differing_only_in_a_preferred_field_rank_in_order():
    """The D25 tie-break: same outcome, the one with a license sorts first."""
    with_license, without = kitchen_through_required(), kitchen_through_required()
    for convo, answer in ((with_license, "yes"), (without, "no")):
        convo.send(ext(has_driver_license=answer))
        convo.send(ext(food_handler_certificate="yes"))
        convo.send(ext(confirmation="confirm"))
    assert with_license.state.status is without.state.status is Status.QUALIFIED
    assert with_license.state.preference_score > without.state.preference_score


def test_a_preferred_field_is_asked_once_and_never_flagged():
    convo = kitchen_through_required()
    convo.send(ext(), text="mmm")  # no answer to the optional license question
    assert convo.field("has_driver_license").status is FieldStatus.MISSING
    assert convo.asking == "food_handler_certificate"  # moved on, no re-ask
    convo.send(ext(food_handler_certificate="expired"))  # unclear: not flagged either
    assert convo.field("food_handler_certificate").status is FieldStatus.MISSING
    assert convo.state.stage is Stage.CONFIRM
    convo.send(ext(confirmation="confirm"))
    assert convo.state.status is Status.QUALIFIED
    assert convo.state.review_reasons == []


def test_a_preferred_answer_volunteered_early_is_kept_and_not_asked_again():
    convo = Convo(vacancy="kitchen_prep")
    convo.send(ext(consent="yes", full_name="Ana Ruiz", has_driver_license="no"))
    assert convo.state.status is Status.IN_PROGRESS
    assert convo.value("has_driver_license") is False
    assert convo.asking == "location"  # required fields still come first


def test_stage_entered_names_the_field_for_drop_off_analytics():
    convo = Convo()
    result = convo.send(ext(consent="yes"))
    entered = [e.data for e in result.events if e.type == "stage_entered"]
    assert entered == [{"stage": "collecting", "field": "full_name"}]


# E16: fixes for the live-run findings in status/evals.md


def test_a_surname_reply_is_joined_to_the_first_name_in_code():
    """Sonnet returned just "ramirez soto" after the surname re-ask (scenarios 09, 19)."""
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="kevin"))
    convo.send(ext(full_name="ramirez soto"))
    assert convo.value("full_name") == "kevin ramirez soto"


def test_a_full_name_after_the_surname_reask_is_not_doubled():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Kevin"))
    convo.send(ext(full_name="Kevin Ramírez Soto"))
    assert convo.value("full_name") == "Kevin Ramírez Soto"


def test_a_flag_note_keeps_the_candidates_detail():
    """Scenario 13: the renewal appointment was lost from the recruiter's view."""
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    convo.send(
        {**ext(has_driver_license="expired"), "detail": "caducó en agosto, renueva en 2 semanas"}
    )
    assert convo.field("has_driver_license").note == (
        "license expired: caducó en agosto, renueva en 2 semanas"
    )


def test_restating_a_flagged_answer_without_new_detail_changes_nothing():
    convo = Convo()
    convo.send(ext(consent="yes"))
    convo.send(ext(full_name="Iker Etxeberria"))
    convo.send({**ext(has_driver_license="expired"), "detail": "caducó en agosto"})
    result = convo.send(ext(has_driver_license="expired"))
    assert convo.field("has_driver_license").note == "license expired: caducó en agosto"
    assert "field_flagged" not in event_types(result)
