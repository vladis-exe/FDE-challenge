"""Compose: turn a ReplyPlan (decided by code) into Alex's next message (written by the LLM).

The policy fills the plan: what was just recorded, an approved FAQ answer if the
candidate asked something, and what to ask next. The persona prompt is static so
it caches; the plan and recent conversation go in the user message.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from screening.config import MessageLimits
from screening.guard import check_reply, strip_label, trim_reply
from screening.llm import LLMClient, LLMResult
from screening.prompts import load_prompt
from screening.schemas import TranscriptLine
from screening.understand import render_transcript

# Asks with a fixed meaning (explained in the compose prompt); any other ask is a
# field name from the vacancy, with its label as the question.
SPECIAL_ASKS = {"consent", "surname", "city_choice", "out_of_area", "confirm", "correction"}

VOCABULARY = {
    "ES": "Spain: carnet de conducir, coche, móvil",
    "MX": "Mexico: licencia de manejo, carro, celular",
}
REPLY_MAX_TOKENS = 300
# Said explicitly, because a model otherwise picks a "name" out of the transcript
# ("simón, empecemos" → "Genial, Simón."). The guard enforces it too.
UNKNOWN_NAME = "unknown (they haven't given it yet: don't address them by any name)"


class Ask(BaseModel):
    field: str  # a vacancy field name, or one of SPECIAL_ASKS
    about: str | None = None  # field asks: the field's label, in the reply's language
    optional: bool = False  # a preferred field: say it's not required for this job
    term: str | None = None  # the thing asked about, in the candidate's country vocabulary
    retry_reason: str | None = None  # set when re-asking: why the last answer didn't work
    options: list[str] = []  # city_choice: the cities to offer
    city_not_served: str | None = None  # out_of_area: the city the candidate named


class ReplyPlan(BaseModel):
    language: Literal["es", "en"]
    country: Literal["ES", "MX"]
    job_title: str  # in the reply's language
    first_name: str | None = None
    acknowledge: list[str] = []  # facts just recorded, e.g. "city: Barcelona"
    faq_answer: str | None = None  # approved text from faq.yaml
    unanswered_question: str | None = None  # asked, but not covered by the FAQ
    redirect: bool = False  # the message was off-topic: steer back politely, once
    ask: Ask | None = None


def instructions(plan: ReplyPlan) -> str:
    """The numbered plan the model follows, in plain words."""
    steps: list[str] = []
    if plan.redirect:
        steps.append(
            "Their last message wasn't about the application. Say kindly, in a few words, "
            f"that you can only help with the {plan.job_title} application."
        )
    if plan.acknowledge:
        steps.append(f"Briefly acknowledge what they just told you: {'; '.join(plan.acknowledge)}.")
    if plan.faq_answer:
        steps.append(
            "Answer their question with this approved information, in your own words but "
            f'without adding or changing any fact: "{plan.faq_answer}"'
        )
    if plan.unanswered_question:
        steps.append(
            f'They asked: "{plan.unanswered_question}". You don\'t have approved information '
            "on this, so say a recruiter will confirm it."
        )
    if plan.ask:
        ask = plan.ask
        line = f"Ask for: {ask.field}."
        if ask.about:
            line += f" Ask about: {ask.about}."
        if ask.term:
            line += f" Call it: {ask.term}."
        if ask.optional:
            line += " This question is optional for this job."
        if ask.options:
            line += f" Options: {', '.join(ask.options)}."
        if ask.city_not_served:
            line += f" City they named, where we are not hiring: {ask.city_not_served}."
        if ask.retry_reason:
            line += f" Their last answer didn't work ({ask.retry_reason}); re-ask differently."
        steps.append(line)
    return "\n".join(f"{number}. {step}" for number, step in enumerate(steps, start=1))


def user_prompt(plan: ReplyPlan, transcript: list[TranscriptLine]) -> str:
    language = {"es": "Spanish", "en": "English"}[plan.language]
    return (
        "<situation>\n"
        f"Job: {plan.job_title}\n"
        f"Language: {language}\n"
        f"Country vocabulary: {VOCABULARY[plan.country]}\n"
        f"Candidate's first name: {plan.first_name or UNKNOWN_NAME}\n"
        "</situation>\n"
        f"<recent_conversation>\n{render_transcript(transcript)}\n</recent_conversation>\n"
        f"<write>\n{instructions(plan)}\n</write>"
    )


@dataclass
class Composed:
    text: str
    calls: list[LLMResult[str]] = field(default_factory=list)  # one, or two after a retry
    problems: list[str] = field(default_factory=list)  # rules the first draft broke
    trimmed: bool = False  # the retry broke rules too, so code cut it down


def compose_reply(
    plan: ReplyPlan,
    transcript: list[TranscriptLine],
    *,
    llm: LLMClient,
    limits: MessageLimits,
    not_names: frozenset[str] = frozenset(),
) -> Composed:
    """Draft, check the message rules, regenerate once if broken, then trim if still broken.

    Raises LLMError when the model can't be reached; the engine sends the holding reply.
    """
    asks = plan.ask is not None
    messages = [{"role": "user", "content": user_prompt(plan, transcript)}]
    draft = _draft(messages, llm)
    draft.value = strip_label(draft.value)  # a label is never meant for the candidate
    composed = Composed(text=draft.value, calls=[draft])
    name = plan.first_name
    rules = {"asks": asks, "limits": limits, "name": name, "not_names": not_names}
    composed.problems = check_reply(draft.value, **rules)
    if not composed.problems:
        return composed

    feedback = (
        f'Your draft was: "{draft.value}"\n'
        f"It broke these rules: {'; '.join(composed.problems)}. "
        "Write the message again, following every rule. Reply with the message text only, "
        "exactly as the candidate will read it: no label, no quotes, no explanation."
    )
    retry = _draft(messages + [{"role": "assistant", "content": draft.value},
                               {"role": "user", "content": feedback}], llm)  # fmt: skip
    retry.value = strip_label(retry.value)
    composed.calls.append(retry)
    composed.text = retry.value
    if check_reply(retry.value, **rules):
        composed.text = trim_reply(retry.value, **rules)
        composed.trimmed = True
    return composed


def _draft(messages: list[dict[str, str]], llm: LLMClient) -> LLMResult[str]:
    return llm.text(
        purpose="compose",
        system=load_prompt("compose"),
        messages=messages,
        tier="fast",
        max_tokens=REPLY_MAX_TOKENS,
    )
