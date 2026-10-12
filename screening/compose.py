"""Compose: turn a ReplyPlan (decided by code) into Alex's next message (written by the LLM).

The policy fills the plan: what was just recorded, an approved FAQ answer if the
candidate asked something, and what to ask next. The persona prompt is static so
it caches; the plan and recent conversation go in the user message.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from screening.config import MessageLimits
from screening.guard import check_reply, trim_reply
from screening.llm import LLMClient, LLMResult
from screening.prompts import load_prompt
from screening.schemas import TranscriptLine
from screening.understand import render_transcript

AskField = Literal[
    "consent",
    "full_name",
    "surname",
    "license",
    "location",
    "city_choice",
    "out_of_area",
    "availability",
    "schedule",
    "experience",
    "start_date",
    "confirm",
    "correction",
]

VOCABULARY = {
    "ES": "Spain: carnet de conducir, coche, móvil",
    "MX": "Mexico: licencia de manejo, carro, celular",
}
REPLY_MAX_TOKENS = 300


class Ask(BaseModel):
    field: AskField
    retry_reason: str | None = None  # set when re-asking: why the last answer didn't work
    options: list[str] = []  # city_choice: the cities to offer
    city_not_served: str | None = None  # out_of_area: the city the candidate named


class ReplyPlan(BaseModel):
    language: Literal["es", "en"]
    country: Literal["ES", "MX"]
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
            "that you can only help with the delivery-driver application."
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
        f"Language: {language}\n"
        f"Country vocabulary: {VOCABULARY[plan.country]}\n"
        f"Candidate's first name: {plan.first_name or 'unknown'}\n"
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
) -> Composed:
    """Draft, check the message rules, regenerate once if broken, then trim if still broken.

    Raises LLMError when the model can't be reached; the engine sends the holding reply.
    """
    asks = plan.ask is not None
    messages = [{"role": "user", "content": user_prompt(plan, transcript)}]
    draft = _draft(messages, llm)
    composed = Composed(text=draft.value, calls=[draft])
    composed.problems = check_reply(draft.value, asks=asks, limits=limits)
    if not composed.problems:
        return composed

    feedback = (
        f'Your draft was: "{draft.value}"\n'
        f"It broke these rules: {'; '.join(composed.problems)}. "
        "Write the message again, following every rule."
    )
    retry = _draft(messages + [{"role": "assistant", "content": draft.value},
                               {"role": "user", "content": feedback}], llm)  # fmt: skip
    composed.calls.append(retry)
    composed.text = retry.value
    if check_reply(retry.value, asks=asks, limits=limits):
        composed.text = trim_reply(retry.value, asks=asks, limits=limits)
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
