"""Policy: the screening state machine. Pure code, no LLM calls.

`decide(state, extraction, message)` takes the conversation state and what the
LLM read in the candidate's message (an Extraction), and returns the new state,
the events, and what to reply: a fixed message, or a ReplyPlan for the LLM to
phrase. Every eligibility decision, stage change and outcome is made here, from
validated values only, so nothing a candidate writes to the model can change an
outcome (DECISIONS D3).

Stages follow the spec order:
    CONSENT → NAME → LICENSE → LOCATION → AVAILABILITY → SCHEDULE → EXPERIENCE
    → START_DATE → CONFIRM → DONE
The stage is always "the first field still missing"; any message may fill any
field, so a candidate who answers several questions at once skips ahead.

Transition table. Rules are checked top to bottom; the first match wins.

#    When                              Then                                 Reply
---  --------------------------------  -----------------------------------  ---------------------
     BEFORE READING THE MESSAGE
1    status = opted_out                nothing changes                      none
2    media without text                event media_received, no attempt     fixed: media
3    status = abandoned                status -> in_progress, then go on    (rules below)
4    status = qualified, needs_review  nothing changes                      FAQ answer if asked,
     or disqualified                                                        else fixed: after_close
     ANY STAGE, IN PROGRESS
5    intent = opt_out                  status -> opted_out                  close: opt_out
6    intent = human_request            status -> needs_review               close: human_requested
                                       (reason human_requested)
7    intent = offtopic or abuse,       strikes += 1; any values in the      redirect + re-ask
     strikes < max                     message are ignored
8    intent = offtopic or abuse,       status -> needs_review               close: flagged
     strikes = max                     (reason offtopic or abuse)
     CONSENT
9    consent = no                      status -> opted_out, nothing stored  close: consent_declined
10   consent = yes, or a field given   consent_at = now; apply fields (16)  next ask
11   anything else                     nothing changes                      FAQ if asked +
                                                                            ask consent
     OUT-OF-AREA CONFIRMATION PENDING
12   a served city                     pending cleared, city accepted       next ask
13   the same unserved city again,     status -> disqualified               close: out_of_area
     or confirm                        (out_of_area)                        (waitlist sentence)
14   another unserved city             pending = that city                  ask out_of_area
15   deny, no city                     pending cleared, location attempt    ask location
                                       used
--   anything else                     nothing changes                      FAQ if asked +
                                                                            ask out_of_area
     COLLECTING FIELDS (NAME ... START_DATE, and corrections at CONFIRM)
16   each field given, in spec order:
16a    valid                           stored with source message id;       acknowledged
                                       field_accepted / field_corrected
16b    license = no                    status -> disqualified (no_license)  close: no_license
16c    license expired, in progress    flagged with a note,                 acknowledged
       or foreign                      reason license_unclear
16d    city not served                 pending_confirmation = that city     ask out_of_area
16e    city ambiguous                  attempt used                         ask city_choice
16f    invalid, the field asked for    attempt used; once past the max:     re-ask with reason
                                       flagged, reason unresolved:<field>
16g    invalid, another field          ignored; it is asked in turn         -
17   an answer with no field in it     attempt used on the field asked for  re-ask
18   then: a field still missing       stage -> first missing field         FAQ if asked + ask it
19   then: nothing missing             stage -> CONFIRM                     fixed: read-back
     CONFIRM (read-back sent)
20   fields given (a correction)       apply as in 16, then 18 or 19        read-back again
21   confirm                           status -> needs_review if a field    close: completed
                                       is flagged or a reason exists,
                                       else qualified
22   deny, no field given              nothing changes                      ask what to change
23   anything else                     nothing changes                      FAQ if asked +
                                                                            ask confirm

Details:
- An "attempt" is one re-ask. A field gets at most `max_attempts_per_field` (2)
  re-asks; the next failure flags it and the conversation moves on. Questions and
  small talk never use an attempt, so the agent can't loop and can't punish
  someone for asking about the job.
- A first name alone is kept, and the surname is asked once; a one-word reply
  then completes it ("Laura" + "Pérez").
- FAQ answers come only from faq.yaml (by the faq_id the LLM picked); an
  uncovered question gets "a recruiter will confirm".
- Any outcome other than in_progress also sets stage = DONE. Closes are sent as
  kind "close", so the worker never drops them.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from screening.compose import Ask, AskField, ReplyPlan
from screening.config import ScreeningConfig
from screening.locale import candidate_country, candidate_timezone
from screening.messages import first_name
from screening.schemas import (
    ConversationState,
    Event,
    FieldStatus,
    FieldValue,
    InboundMessage,
    Stage,
    Status,
)
from screening.understand import Extraction
from screening.validators import (
    RawExperience,
    Verdict,
    local_date,
    match_city,
    validate_availability,
    validate_experience,
    validate_license,
    validate_name,
    validate_schedule,
    validate_start_date,
)
from screening.validators.text import normalize

# Profile fields in spec order, with the stage that asks for each.
FIELDS: list[tuple[str, Stage]] = [
    ("full_name", Stage.NAME),
    ("has_driver_license", Stage.LICENSE),
    ("location", Stage.LOCATION),
    ("availability", Stage.AVAILABILITY),
    ("schedule", Stage.SCHEDULE),
    ("experience", Stage.EXPERIENCE),
    ("start_date", Stage.START_DATE),
]
STAGE_FIELD = {stage: name for name, stage in FIELDS}
ASK_FIELD: dict[str, AskField] = {
    "full_name": "full_name",
    "has_driver_license": "license",
    "location": "location",
    "availability": "availability",
    "schedule": "schedule",
    "experience": "experience",
    "start_date": "start_date",
}
FINAL = {Status.QUALIFIED, Status.NEEDS_REVIEW, Status.DISQUALIFIED}
FLAG_REASONS = {"has_driver_license": "license_unclear"}


@dataclass(frozen=True)
class FixedReply:
    """A message from messages.yaml, sent word for word."""

    key: str
    kind: Literal["reply", "close"] = "reply"
    values: dict[str, str] = field(default_factory=dict)


Reply = FixedReply | ReplyPlan


@dataclass
class Decision:
    state: ConversationState
    events: list[Event]
    replies: list[Reply]


def decide(
    state: ConversationState,
    extraction: Extraction,
    message: InboundMessage,
    config: ScreeningConfig,
) -> Decision:
    """Apply the transition table to one message. `state` is not modified."""
    turn = _Turn(state.model_copy(deep=True), extraction, message, config)
    turn.run()
    return Decision(turn.state, turn.events, turn.replies)


class _Turn:
    """Working memory for one decision; each method is a group of table rows."""

    def __init__(
        self,
        state: ConversationState,
        extraction: Extraction,
        message: InboundMessage,
        config: ScreeningConfig,
    ) -> None:
        self.state = state
        self.x = extraction
        self.message = message
        self.config = config
        self.asked = state.stage  # the field Alex asked for in its last message
        self.events: list[Event] = []
        self.replies: list[Reply] = []
        self.acknowledge: list[str] = []
        self.retry: Ask | None = None
        self.attempt_used = False
        self.faq_given = False

    # Rows 3-11: routing

    def run(self) -> None:
        state, x = self.state, self.x
        state.language = x.language
        if state.status is Status.ABANDONED:
            self.set_status(Status.IN_PROGRESS)
        if state.status in FINAL:
            return self.after_close()
        if x.intent == "opt_out":
            self.event("opt_out")
            return self.close(Status.OPTED_OUT, "close_opt_out")
        if x.intent == "human_request":
            self.event("human_requested")
            self.add_reason("human_requested")
            return self.close(Status.NEEDS_REVIEW, "close_human_requested")
        if x.intent in ("offtopic", "abuse"):
            return self.strike(x.intent)
        if state.stage is Stage.CONSENT:
            if x.consent == "no":
                return self.close(Status.OPTED_OUT, "close_consent_declined")
            if x.consent != "yes" and not self.fields_given():
                return self.reply(Ask(field="consent"))
            state.consent_at = self.message.received_at
            self.event("consent_given")
        if state.pending_confirmation and self.resolve_pending():
            return
        if state.stage is Stage.CONFIRM and not self.fields_given():
            if x.confirmation == "confirm":
                return self.finish()
            if x.confirmation == "deny":
                return self.reply(Ask(field="correction"))
            return self.reply(Ask(field="confirm"))
        self.collect()

    def after_close(self) -> None:
        if self.x.faq_id or self.x.question:
            self.reply(None)
        else:
            self.replies.append(FixedReply("after_close"))

    def strike(self, intent: str) -> None:
        self.event("offtopic", intent=intent, strike=self.state.offtopic_strikes + 1)
        if self.state.offtopic_strikes < self.config.max_offtopic_strikes:
            self.state.offtopic_strikes += 1
            return self.reply(self.current_ask(), redirect=True)
        self.add_reason(intent)
        self.close(Status.NEEDS_REVIEW, "close_flagged")

    # Rows 12-15: out-of-area confirmation

    def resolve_pending(self) -> bool:
        """Returns True when the turn is fully handled here."""
        pending_city = self.state.pending_confirmation["city_text"]
        city_text = self.x.fields.city_text
        if city_text:
            match = match_city(city_text, self.config)
            if match.kind == "not_served" and normalize(city_text) == normalize(pending_city):
                self.disqualify("out_of_area", city=pending_city)
                return True
            self.state.pending_confirmation = None
            return False  # collect() handles the new city
        if self.x.confirmation == "confirm":
            self.disqualify("out_of_area", city=pending_city)
            return True
        if self.x.confirmation == "deny":
            self.state.pending_confirmation = None
            self.fail("location", "the city they named is not where they'd work")
            return False
        self.reply(Ask(field="out_of_area", city_not_served=pending_city))
        return True

    # Rows 16-19: collecting fields

    def collect(self) -> None:
        fields = self.x.fields
        has_experience = fields.has_experience
        if has_experience is None and fields.experience:
            has_experience = True  # listing platforms answers the question
        raw: dict[str, Any] = {
            "full_name": fields.full_name,
            "has_driver_license": fields.license,
            "location": fields.city_text,
            "availability": fields.availability,
            "schedule": fields.schedule,
            "experience": has_experience,
            "start_date": fields.start_date,
        }
        given = False
        for name, stage in FIELDS:
            if raw[name] is None:
                continue
            given = True
            asked = stage is self.asked or self.asked is Stage.CONFIRM
            self.apply(name, raw[name], asked=asked)
            if self.state.status is not Status.IN_PROGRESS:
                return
        asked_field = STAGE_FIELD.get(self.asked)
        if (
            not given
            and not self.attempt_used
            and asked_field
            and self.x.intent in ("answer", "correction")
        ):
            self.fail(asked_field, "no answer to the question")
        self.next_step()

    def apply(self, name: str, raw: Any, *, asked: bool) -> None:
        profile = self.state.profile
        if name == "full_name":
            self.apply_name(raw, asked=asked)
        elif name == "has_driver_license":
            verdict = validate_license(raw)
            if verdict.outcome == "accept" and verdict.value is False:
                profile.has_driver_license.value = False
                profile.has_driver_license.status = FieldStatus.ACCEPTED
                profile.has_driver_license.source_message_id = self.message.id
                return self.disqualify("no_license")
            self.settle(name, verdict, asked=asked)
        elif name == "location":
            self.apply_city(raw)
        elif name == "availability":
            self.settle(name, validate_availability(raw), asked=asked)
        elif name == "schedule":
            self.settle(name, validate_schedule(raw), asked=asked)
        elif name == "experience":
            items: list[RawExperience] = self.x.fields.experience or []
            verdict = validate_experience(has_experience=raw, items=items)
            self.settle(name, verdict, asked=asked)
        elif name == "start_date":
            today = local_date(
                self.message.received_at, candidate_timezone(self.state, self.config)
            )
            verdict = validate_start_date(
                raw, today=today, max_days=self.config.start_date_max_days
            )
            self.settle(name, verdict, asked=asked)

    def apply_name(self, raw: str, *, asked: bool) -> None:
        name_field = self.state.profile.full_name
        candidate = " ".join(raw.split())
        partial = name_field.value if name_field.status is FieldStatus.MISSING else None
        if partial and len(candidate.split()) == 1 and candidate.casefold() != partial.casefold():
            candidate = f"{partial} {candidate}"  # "Laura" + "Pérez"
        verdict = validate_name(candidate, surname_asked=name_field.attempts > 0)
        if verdict.outcome == "reask" and verdict.note == "surname missing":
            name_field.value = candidate  # kept; the surname is asked once
        self.settle(
            "full_name", verdict, asked=True if verdict.note == "surname missing" else asked
        )

    def apply_city(self, city_text: str) -> None:
        match = match_city(city_text, self.config)
        if match.kind == "matched":
            self.settle("location", Verdict.accept(match.location), asked=True)
        elif match.kind == "ambiguous":
            names = [self.city_name(option.country, option.city) for option in match.options]
            options = Ask(
                field="city_choice", options=names, retry_reason="more than one city matches"
            )
            self.fail("location", "more than one city matches", ask=options)
        else:
            self.state.pending_confirmation = {"type": "out_of_area", "city_text": match.city_text}

    def settle(self, name: str, verdict: Verdict, *, asked: bool) -> None:
        value: FieldValue = getattr(self.state.profile, name)
        if verdict.outcome == "accept":
            corrected = value.status is FieldStatus.ACCEPTED and value.value != verdict.value
            value.value = verdict.value
            value.status = FieldStatus.ACCEPTED
            value.source_message_id = self.message.id
            value.note = verdict.note
            stored = value.model_dump(mode="json")["value"]
            self.event(
                "field_corrected" if corrected else "field_accepted", field=name, value=stored
            )
            self.acknowledge.append(self.describe(name))
        elif verdict.outcome == "flag":
            value.value = None
            value.status = FieldStatus.FLAGGED
            value.source_message_id = self.message.id
            value.note = verdict.note
            self.event("field_flagged", field=name, note=verdict.note)
            self.add_reason(FLAG_REASONS.get(name, f"unclear:{name}"))
            self.acknowledge.append(f"{name}: noted, a recruiter will look at it")
        elif asked:
            self.fail(name, verdict.note or "invalid answer")
        # A bad value volunteered for a field not being asked is ignored; it gets asked in turn.

    def fail(self, name: str, reason: str, ask: Ask | None = None) -> None:
        """One more failed answer for `name`: re-ask, or flag once re-asks are used up."""
        self.attempt_used = True
        value: FieldValue = getattr(self.state.profile, name)
        max_attempts = self.config.max_attempts_per_field
        if value.attempts >= max_attempts:
            value.value = None
            value.status = FieldStatus.FLAGGED
            value.note = f"unresolved after {max_attempts} re-asks"
            self.event("field_flagged", field=name, note=value.note)
            self.add_reason(f"unresolved:{name}")
            return
        value.attempts += 1
        if value.status is FieldStatus.ACCEPTED:
            # A correction that didn't validate: the old value is wrong, the new one unusable.
            value.value = None
            value.status = FieldStatus.MISSING
        self.retry = ask or Ask(field=self.ask_field(name), retry_reason=reason)

    def next_step(self) -> None:
        state = self.state
        if state.pending_confirmation:
            city = state.pending_confirmation["city_text"]
            return self.reply(Ask(field="out_of_area", city_not_served=city))
        missing = next(
            (
                (name, stage)
                for name, stage in FIELDS
                if getattr(state.profile, name).status is FieldStatus.MISSING
            ),
            None,
        )
        if missing is None:
            self.enter(Stage.CONFIRM)
            if self.x.faq_id or self.x.question:
                self.reply(None)
            self.replies.append(FixedReply("readback"))
            return
        name, stage = missing
        self.enter(stage)
        ask = self.retry if self.retry and self.retry_is_for(name) else None
        self.reply(ask or Ask(field=self.ask_field(name)))

    # Rows 21 and knockouts: outcomes

    def finish(self) -> None:
        flagged = any(
            getattr(self.state.profile, name).status is FieldStatus.FLAGGED for name, _ in FIELDS
        )
        needs_review = flagged or bool(self.state.review_reasons)
        self.close(Status.NEEDS_REVIEW if needs_review else Status.QUALIFIED, "close_completed")

    def disqualify(self, reason: Literal["no_license", "out_of_area"], **values: str) -> None:
        self.state.disqualify_reason = reason
        self.state.pending_confirmation = None
        self.event("knockout_failed", reason=reason)
        key = "close_no_license" if reason == "no_license" else "close_out_of_area"
        self.close(Status.DISQUALIFIED, key, **values)

    def close(self, status: Status, key: str, **values: str) -> None:
        self.set_status(status)
        self.enter(Stage.DONE)
        self.replies.append(FixedReply(key, kind="close", values=values))

    # Helpers

    def reply(self, ask: Ask | None, *, redirect: bool = False) -> None:
        plan = ReplyPlan(
            language=self.state.language,
            country=candidate_country(self.state),
            first_name=first_name(self.state),
            acknowledge=self.acknowledge,
            redirect=redirect,
            ask=ask,
        )
        if not self.faq_given and (self.x.faq_id or self.x.question):
            self.faq_given = True
            entry = next((e for e in self.config.faq if e.id == self.x.faq_id), None)
            if entry:
                plan.faq_answer = entry.answer[self.state.language]
            else:
                plan.unanswered_question = self.x.question
            self.event("faq_answered", faq_id=entry.id if entry else None)
        self.replies.append(plan)

    def current_ask(self) -> Ask:
        state = self.state
        if state.pending_confirmation:
            return Ask(field="out_of_area", city_not_served=state.pending_confirmation["city_text"])
        if state.stage is Stage.CONSENT:
            return Ask(field="consent")
        if state.stage is Stage.CONFIRM:
            return Ask(field="confirm")
        return Ask(field=self.ask_field(STAGE_FIELD[state.stage]))

    def ask_field(self, name: str) -> AskField:
        if name == "full_name" and self.state.profile.full_name.value:
            return "surname"
        return ASK_FIELD[name]

    def retry_is_for(self, name: str) -> bool:
        if self.retry is None:
            return False
        if self.retry.field == "city_choice":
            return name == "location"
        return self.retry.field in (ASK_FIELD[name], self.ask_field(name))

    def enter(self, stage: Stage) -> None:
        if self.state.stage is not stage:
            self.state.stage = stage
            self.event("stage_entered", stage=stage.value)

    def set_status(self, status: Status) -> None:
        if self.state.status is not status:
            self.event("status_changed", **{"from": self.state.status.value, "to": status.value})
            self.state.status = status

    def add_reason(self, reason: str) -> None:
        if reason not in self.state.review_reasons:
            self.state.review_reasons.append(reason)

    def fields_given(self) -> bool:
        fields = self.x.fields
        return any(value is not None for value in fields.model_dump().values())

    def describe(self, name: str) -> str:
        value = getattr(self.state.profile, name).value
        if name == "has_driver_license":
            return "has a valid driver's license"
        if name == "location":
            return f"city: {self.city_name(value.country, value.city)}"
        if name == "experience":
            if not value:
                return "no delivery experience (that's fine)"
            return "experience: " + ", ".join(
                f"{item.platform} {item.years:g} years" for item in value
            )
        if name == "start_date":
            return f"start date: {value.isoformat()}"
        if isinstance(value, list):
            return f"{name}: {', '.join(item.value for item in value)}"
        return f"name: {value}" if name == "full_name" else f"{name}: {value}"

    def city_name(self, country: str, key: str) -> str:
        cities = self.config.service_areas[country].cities
        return next(city.name for city in cities if city.key == key)

    def event(self, type_: str, **data: Any) -> None:
        self.events.append(Event(type=type_, at=self.message.received_at, data=data))
