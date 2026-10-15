"""Policy: the screening state machine. Pure code, no LLM calls.

`decide(state, extraction, message, config)` takes the conversation state and what
the LLM read in the candidate's message (an Extraction), and returns the new state,
the events, and what to reply: a fixed message, or a ReplyPlan for the LLM to
phrase. Every eligibility decision, stage change and outcome is made here, from
validated values only, so nothing a candidate writes to the model can change an
outcome (DECISIONS D3).

The fields come from the conversation's vacancy (CONTRACTS §7). Stages:
    CONSENT -> COLLECTING (state.current_field says which) -> CONFIRM -> DONE
The field asked next is always the first required field still missing, in the
vacancy's order; then each preferred field once. Any message may fill any field,
so a candidate who answers several questions at once skips ahead. Required fields
come first by rule: a knockout must never wait behind a question that can't
disqualify, so an ineligible candidate finishes in a few messages.

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
     OUT-OF-AREA CONFIRMATION PENDING (a required city field)
12   a served city                     pending cleared, city accepted       next ask
13   the same unserved city again,     status -> disqualified               close: out_of_area
     or confirm                        (out_of_area)                        (waitlist sentence)
14   another unserved city             pending = that city                  ask out_of_area
15   deny, no city                     pending cleared, city attempt used   ask the city
--   anything else                     nothing changes                      FAQ if asked +
                                                                            ask out_of_area
     COLLECTING, and corrections at CONFIRM
16   each field given, in the vacancy's order:
16a    valid                           stored with source message id;       acknowledged
                                       field_accepted / field_corrected
16b    knockout value (boolean "no")   required: status -> disqualified     close: knockout
                                       (no_<reason>); preferred: stored     (preferred:
                                       as a plain value, never disqualifies acknowledged)
16c    unclear boolean (expired,       flagged with a note,                 acknowledged
       in progress, foreign)           reason <reason>_unclear
16d    city not served                 pending_confirmation = that city     ask out_of_area
16e    city ambiguous                  attempt used                         ask city_choice
16f    invalid, the field asked for    required: attempt used; once past    re-ask with reason
                                       the max: flagged, unresolved:<field>
                                       preferred: left missing, not asked   (next ask)
                                       again, no flag
16g    invalid, another field          ignored; it is asked in turn         -
17   an answer with no field in it     as 16f for the field asked for       re-ask / next ask
18   then: a field still to ask        current_field -> that field          FAQ if asked + ask it
19   then: nothing left to ask         stage -> CONFIRM                     fixed: read-back
     CONFIRM (read-back sent; pending_confirmation counts the rounds)
20   fields given that change a value  apply as in 16, then 18 or 19        read-back again
                                                                            (one more round)
21   confirm, or fields given that     status -> needs_review if a field    close: completed
     change nothing (a restatement)    is flagged or a reason exists,
                                       else qualified
22   deny, nothing changed             nothing changes                      ask what to change
                                                                            (one more round)
23   anything else                     nothing changes                      FAQ if asked +
                                                                            ask confirm
24   a round would pass the max        status -> needs_review               close: completed
     (20 or 22)                        (reason unresolved:confirm)

Details:
- An "attempt" is one re-ask. A required field gets at most
  `max_attempts_per_field` (2) re-asks; the next failure flags it and the
  conversation moves on. A preferred field is asked exactly once (its `attempts`
  is set to 1 to record that), and never flagged. Questions and small talk never
  use an attempt, so the agent can't loop and can't punish someone for asking
  about the job. The read-back has the same cap (rows 20, 22, 24): a candidate
  restating a correct value used to get the same read-back again, forever.
- A first name alone is kept, and the surname is asked once; a one-word reply
  then completes it ("Laura" + "Pérez").
- A city field's accepted country becomes `country_hint`, so vocabulary and time
  zones follow where the candidate actually is.
- The preference score is recomputed after every turn, from accepted preferred
  fields only (screening.scoring). It never changes a status.
- FAQ answers come only from faq.yaml (by the faq_id the LLM picked); an
  uncovered question gets "a recruiter will confirm".
- Any outcome other than in_progress also sets stage = DONE. Closes are sent as
  kind "close", so the worker never drops them.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from screening.compose import Ask, ReplyPlan
from screening.config import FieldSpec, ScreeningConfig
from screening.fields import is_knockout, typed, validate
from screening.locale import candidate_country, candidate_timezone
from screening.messages import first_name, localized, option_label
from screening.schemas import (
    ConversationState,
    Event,
    FieldStatus,
    FieldValue,
    InboundMessage,
    Stage,
    Status,
)
from screening.scoring import preference_score
from screening.understand import Extraction
from screening.validators import Verdict, local_date, match_city
from screening.validators.text import normalize

FINAL = {Status.QUALIFIED, Status.NEEDS_REVIEW, Status.DISQUALIFIED}


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
    vacancy = config.vacancy(turn.state.vacancy_id)
    turn.state.preference_score = preference_score(vacancy, turn.state.profile.fields)
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
        self.vacancy = config.vacancy(state.vacancy_id)
        # What Alex asked in its last message.
        self.at_confirm = state.stage is Stage.CONFIRM
        self.asked: FieldSpec | None = (
            self.vacancy.field(state.current_field)
            if state.stage is Stage.COLLECTING and state.current_field
            else None
        )
        self.events: list[Event] = []
        self.replies: list[Reply] = []
        self.acknowledge: list[str] = []
        self.retry: tuple[str, Ask] | None = None  # (field name, how to re-ask it)
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
        if self.pending("out_of_area") and self.resolve_pending():
            return
        if self.at_confirm:
            return self.confirm()
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
        pending = self.state.pending_confirmation
        spec = self.vacancy.field(pending["field"])
        city_text = self.raw(spec)
        if city_text:
            match = match_city(city_text, self.config)
            if match.kind == "not_served" and normalize(city_text) == normalize(
                pending["city_text"]
            ):
                self.disqualify("out_of_area", "close_out_of_area", city=pending["city_text"])
                return True
            self.state.pending_confirmation = None
            return False  # collect() handles the new city
        if self.x.confirmation == "confirm":
            self.disqualify("out_of_area", "close_out_of_area", city=pending["city_text"])
            return True
        if self.x.confirmation == "deny":
            self.state.pending_confirmation = None
            self.fail(spec, "the city they named is not where they'd work")
            return False
        self.reply(self.current_ask())
        return True

    # Rows 20-24: the read-back

    def confirm(self) -> None:
        if not self.fields_given():
            if self.x.confirmation == "confirm":
                return self.finish()
            if self.x.confirmation == "deny":
                return self.another_round(lambda: self.reply(Ask(field="correction")))
            return self.reply(Ask(field="confirm"))
        before = self.state.profile.model_dump(mode="json")
        self.apply_given()
        if self.state.status is not Status.IN_PROGRESS:
            return
        if self.state.profile.model_dump(mode="json") == before and not self.retry:
            # A restatement ("todo bien, vivo en Vallecas") changes nothing: it's an answer to
            # the read-back, not a correction, so it must not trigger the same read-back again.
            if self.x.confirmation == "deny":
                return self.another_round(lambda: self.reply(Ask(field="correction")))
            return self.finish()
        self.next_step()

    def another_round(self, send) -> None:
        """One more read-back round; past the cap the read-back is flagged instead (row 24)."""
        rounds = (self.state.pending_confirmation or {}).get("rounds", 0) + 1
        if rounds > self.config.max_attempts_per_field:
            self.add_reason("unresolved:confirm")
            return self.finish()
        self.state.pending_confirmation = {"type": "readback", "rounds": rounds}
        send()

    # Rows 16-19: collecting fields

    def collect(self) -> None:
        given = self.apply_given()
        if self.state.status is not Status.IN_PROGRESS:
            return
        if (
            not given
            and not self.attempt_used
            and self.asked
            and self.x.intent in ("answer", "correction")
        ):
            self.fail(self.asked, "no answer to the question")
        self.next_step()

    def apply_given(self) -> bool:
        """Apply every field the message gave, in the vacancy's order. True if any."""
        given = False
        for spec in self.vacancy.asked:
            raw = self.raw(spec)
            if raw is None:
                continue
            given = True
            asked = self.at_confirm or (self.asked is not None and spec.name == self.asked.name)
            self.apply(spec, raw, asked=asked)
            if self.state.status is not Status.IN_PROGRESS:
                break
        return given

    def apply(self, spec: FieldSpec, raw: Any, *, asked: bool) -> None:
        if spec.type == "city":
            return self.apply_city(spec, raw)
        if spec.type == "text":
            return self.apply_name(spec, raw, asked=asked)
        timezone = candidate_timezone(self.state, self.config)
        verdict = validate(
            spec,
            raw,
            today=local_date(self.message.received_at, timezone),
            max_days=self.config.start_date_max_days,
            surname_asked=False,
            message_text=self.message.text,
        )
        knockout = verdict.outcome == "accept" and is_knockout(spec, verdict.value)
        if knockout and spec.requirement == "required":
            self.store(spec, verdict.value)
            requirement = localized(spec.summary, self.locale, self.state.language) or spec.name
            return self.disqualify(
                f"no_{spec.outcome_name}", "close_knockout", requirement=requirement
            )
        # On a preferred field a knockout-shaped answer is just a value, kept for scoring.
        self.settle(spec, verdict, asked=asked)

    def apply_name(self, spec: FieldSpec, raw: str, *, asked: bool) -> None:
        name_field = self.field(spec.name)
        candidate = " ".join(raw.split())
        partial = name_field.value if name_field.status is FieldStatus.MISSING else None
        surname_reply = (
            partial
            and name_field.attempts > 0  # Alex asked for the surname
            and self.x.intent != "correction"
            and not candidate.casefold().startswith(partial.casefold())
        )
        if surname_reply:
            # Join in code: a model may return just the surname it was asked for
            # ("ramirez soto"), which must complete "kevin", not replace it.
            candidate = f"{partial} {candidate}"
        verdict = validate(
            spec,
            candidate,
            today=self.message.received_at.date(),
            max_days=0,
            surname_asked=name_field.attempts > 0,
        )
        surname_missing = verdict.outcome == "reask" and verdict.note == "surname missing"
        if surname_missing:
            name_field.value = candidate  # kept; the surname is asked once
        self.settle(spec, verdict, asked=asked or surname_missing)

    def apply_city(self, spec: FieldSpec, city_text: str) -> None:
        match = match_city(city_text, self.config)
        if match.kind == "matched":
            self.settle(spec, Verdict.accept(match.location), asked=True)
        elif match.kind == "ambiguous":
            names = [self.city_name(option.country, option.city) for option in match.options]
            reason = "more than one city matches"
            ask = Ask(field="city_choice", options=names, retry_reason=reason)
            self.fail(spec, reason, ask=ask)
        else:
            self.state.pending_confirmation = {
                "type": "out_of_area",
                "field": spec.name,
                "city_text": match.city_text,
            }

    def settle(self, spec: FieldSpec, verdict: Verdict, *, asked: bool) -> None:
        value = self.field(spec.name)
        if verdict.outcome == "accept":
            if value.status is FieldStatus.ACCEPTED and typed(spec, value.value) == verdict.value:
                return  # a restatement: nothing to record or acknowledge
            corrected = value.status is FieldStatus.ACCEPTED
            self.store(spec, verdict.value, note=verdict.note)
            stored = value.model_dump(mode="json")["value"]
            event_type = "field_corrected" if corrected else "field_accepted"
            self.event(event_type, field=spec.name, value=stored)
            self.acknowledge.append(self.describe(spec))
        elif verdict.outcome == "flag" and spec.requirement == "required":
            # Keep the candidate's own detail ("cita para renovarlo en 2 semanas"): it is
            # what the recruiter needs to decide.
            note = f"{verdict.note}: {self.x.detail}" if self.x.detail else verdict.note
            same_answer = value.status is FieldStatus.FLAGGED and value.note.startswith(
                verdict.note
            )
            if same_answer and (not self.x.detail or value.note == note):
                return  # the same unclear answer again ("caducó en agosto"): nothing new
            value.value = None
            value.status = FieldStatus.FLAGGED
            value.source_message_id = self.message.id
            value.note = note
            self.event("field_flagged", field=spec.name, note=note)
            self.add_reason(f"{spec.outcome_name}_unclear")
            self.acknowledge.append(f"{spec.name}: noted, a recruiter will look at it")
        elif asked:
            self.fail(spec, verdict.note or "invalid answer")
        # A bad value volunteered for a field not being asked is ignored; it gets asked in turn.

    def store(self, spec: FieldSpec, value: Any, note: str | None = None) -> None:
        field_value = self.field(spec.name)
        field_value.value = value
        field_value.status = FieldStatus.ACCEPTED
        field_value.source_message_id = self.message.id
        field_value.note = note
        if spec.type == "city":
            self.state.country_hint = value.country  # vocabulary and time zone follow the city

    def fail(self, spec: FieldSpec, reason: str, ask: Ask | None = None) -> None:
        """One more failed answer: re-ask, flag once re-asks are used up, or (preferred) move on."""
        self.attempt_used = True
        value = self.field(spec.name)
        if value.status is FieldStatus.ACCEPTED:
            # A correction that didn't validate: the old value is wrong, the new one unusable.
            value.value = None
            value.status = FieldStatus.MISSING
        if spec.requirement == "preferred":
            value.attempts = 1  # asked once; never re-asked, never flagged
            return
        max_attempts = self.config.max_attempts_per_field
        if value.attempts >= max_attempts:
            value.value = None
            value.status = FieldStatus.FLAGGED
            value.note = f"unresolved after {max_attempts} re-asks"
            self.event("field_flagged", field=spec.name, note=value.note)
            self.add_reason(f"unresolved:{spec.name}")
            return
        value.attempts += 1
        self.retry = (spec.name, ask or self.field_ask(spec, retry_reason=reason))

    def next_step(self) -> None:
        if self.pending("out_of_area"):
            return self.reply(self.current_ask())
        spec = self.next_field()
        if spec is not None:
            self.enter(Stage.COLLECTING, spec.name)
            retry = self.retry[1] if self.retry and self.retry[0] == spec.name else None
            return self.reply(retry or self.field_ask(spec))
        if self.at_confirm:
            return self.another_round(self.send_readback)
        self.enter(Stage.CONFIRM)
        self.state.pending_confirmation = {"type": "readback", "rounds": 0}
        self.send_readback()

    def next_field(self) -> FieldSpec | None:
        """The first required field still missing; then each preferred field, once."""
        for spec in self.vacancy.asked:
            value = self.field(spec.name)
            asked_once = spec.requirement == "preferred" and value.attempts > 0
            if value.status is FieldStatus.MISSING and not asked_once:
                return spec
        return None

    def send_readback(self) -> None:
        self.enter(Stage.CONFIRM)
        if self.x.faq_id or self.x.question:
            self.reply(None)
        self.replies.append(FixedReply("readback"))

    # Rows 21, 24 and knockouts: outcomes

    def finish(self) -> None:
        flagged = any(
            self.field(spec.name).status is FieldStatus.FLAGGED for spec in self.vacancy.asked
        )
        needs_review = flagged or bool(self.state.review_reasons)
        self.close(Status.NEEDS_REVIEW if needs_review else Status.QUALIFIED, "close_completed")

    def disqualify(self, reason: str, key: str, **values: str) -> None:
        self.state.disqualify_reason = reason
        self.state.pending_confirmation = None
        self.event("knockout_failed", reason=reason)
        self.close(Status.DISQUALIFIED, key, **values)

    def close(self, status: Status, key: str, **values: str) -> None:
        self.set_status(status)
        self.enter(Stage.DONE)
        self.state.pending_confirmation = None
        self.replies.append(FixedReply(key, kind="close", values=values))

    # Helpers

    def reply(self, ask: Ask | None, *, redirect: bool = False) -> None:
        plan = ReplyPlan(
            language=self.state.language,
            country=candidate_country(self.state),
            job_title=self.vacancy.title[self.state.language],
            first_name=first_name(self.state),
            acknowledge=self.acknowledge,
            redirect=redirect,
            ask=ask,
        )
        if not self.faq_given and (self.x.faq_id or self.x.question):
            self.faq_given = True
            entry = next((e for e in self.config.faq if e.id == self.x.faq_id), None)
            if entry:
                plan.faq_answer = localized(entry.answer, self.locale, self.state.language)
            else:
                plan.unanswered_question = self.x.question
            self.event("faq_answered", faq_id=entry.id if entry else None)
        self.replies.append(plan)

    def current_ask(self) -> Ask:
        state = self.state
        if self.pending("out_of_area"):
            pending = state.pending_confirmation
            return Ask(field="out_of_area", city_not_served=pending["city_text"])
        if state.stage is Stage.CONSENT:
            return Ask(field="consent")
        if state.stage is Stage.CONFIRM:
            return Ask(field="confirm")
        return self.field_ask(self.vacancy.field(state.current_field))

    def field_ask(self, spec: FieldSpec, retry_reason: str | None = None) -> Ask:
        if spec.type == "text" and self.field(spec.name).value:
            return Ask(field="surname", retry_reason=retry_reason)
        # The options in the candidate's own vocabulary (es_MX: "medio tiempo"), from config,
        # so the question and the read-back use the same words.
        options = [
            option_label(spec, option, self.locale, self.state.language)
            for option in spec.options or []
        ]
        return Ask(
            field=spec.name,
            about=spec.label[self.state.language],
            optional=spec.requirement == "preferred",
            options=options,
            retry_reason=retry_reason,
        )

    def enter(self, stage: Stage, current_field: str | None = None) -> None:
        state = self.state
        if (state.stage, state.current_field) != (stage, current_field):
            if state.stage is Stage.CONFIRM and self.pending("readback"):
                state.pending_confirmation = None  # leaving the read-back resets its rounds
            state.stage = stage
            state.current_field = current_field
            self.event("stage_entered", stage=stage.value, field=current_field)

    def set_status(self, status: Status) -> None:
        if self.state.status is not status:
            self.event("status_changed", **{"from": self.state.status.value, "to": status.value})
            self.state.status = status

    def add_reason(self, reason: str) -> None:
        if reason not in self.state.review_reasons:
            self.state.review_reasons.append(reason)

    def field(self, name: str) -> FieldValue:
        return self.state.profile.fields.setdefault(name, FieldValue())

    def raw(self, spec: FieldSpec) -> Any:
        """This message's answer for a field; None when it gave none."""
        raw = self.x.field(spec.name)
        if spec.type == "experience" and raw is not None:
            if raw.has_experience is None and not raw.items:
                return None
        return raw

    def fields_given(self) -> bool:
        return any(self.raw(spec) is not None for spec in self.vacancy.asked)

    def pending(self, kind: str) -> bool:
        return (self.state.pending_confirmation or {}).get("type") == kind

    @property
    def locale(self) -> str:
        return f"{self.state.language}_{candidate_country(self.state)}"

    def describe(self, spec: FieldSpec) -> str:
        """What was just recorded, for the reply to acknowledge."""
        value = typed(spec, self.field(spec.name).value)
        if spec.type == "text":
            return f"name: {value}"
        if spec.type == "boolean":
            return f"{spec.name}: {'yes' if value else 'no'}"
        if spec.type == "city":
            return f"city: {self.city_name(value.country, value.city)}"
        if spec.type == "experience":
            if not value:
                return f"{spec.name}: none (that's fine)"
            items = ", ".join(f"{item.platform} {item.years:g} years" for item in value)
            return f"{spec.name}: {items}"
        if spec.type == "date":
            return f"{spec.name}: {value.isoformat()}"
        return f"{spec.name}: {', '.join(value)}"

    def city_name(self, country: str, key: str) -> str:
        cities = self.config.service_areas[country].cities
        return next(city.name for city in cities if city.key == key)

    def event(self, type_: str, **data: Any) -> None:
        self.events.append(Event(type=type_, at=self.message.received_at, data=data))
