"""Understand: turn one candidate message into a typed Extraction.

The LLM reads and labels; it does not decide. The policy validates every value
with screening.validators and chooses the next step.

Prompt layout, for caching: the system prompt is identical on every call (rules,
FAQ catalogue, examples), and everything specific to this conversation goes in
the user message.
"""

from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from screening.config import ScreeningConfig
from screening.llm import LLMClient, LLMResult
from screening.locale import candidate_country, candidate_timezone
from screening.prompts import load_prompt
from screening.schemas import (
    Availability,
    ConversationState,
    InboundMessage,
    Schedule,
    Stage,
    TranscriptLine,
)
from screening.validators import LicenseAnswer, RawExperience, StartDateAnswer

Intent = Literal[
    "answer",
    "question",
    "correction",
    "smalltalk",
    "offtopic",
    "opt_out",
    "human_request",
    "abuse",
]


class ExtractedFields(BaseModel):
    """Raw values as the candidate gave them; null means "not in this message"."""

    full_name: str | None = None
    license: LicenseAnswer | None = None
    city_text: str | None = None
    availability: list[Availability] | None = None
    schedule: list[Schedule] | None = None
    has_experience: bool | None = None
    experience: list[RawExperience] | None = None
    start_date: StartDateAnswer | None = None


class Extraction(BaseModel):
    intent: Intent
    language: Literal["es", "en"]
    consent: Literal["yes", "no"] | None = None
    confirmation: Literal["confirm", "deny"] | None = None
    question: str | None = None
    faq_id: str | None = None
    fields: ExtractedFields = ExtractedFields()


# What Alex is waiting for at each stage, in the words the prompt uses.
ASKING_FOR = {
    Stage.CONSENT: "consent",
    Stage.NAME: "full name",
    Stage.LICENSE: "license",
    Stage.LOCATION: "city",
    Stage.AVAILABILITY: "availability",
    Stage.SCHEDULE: "schedule",
    Stage.EXPERIENCE: "experience",
    Stage.START_DATE: "start date",
    Stage.CONFIRM: "confirm (Alex read back the summary)",
    Stage.DONE: "nothing (screening finished)",
}


def system_prompt(config: ScreeningConfig) -> str:
    catalogue = "\n".join(
        f"- {entry.id}: " + " / ".join(entry.questions["es"] + entry.questions["en"])
        for entry in config.faq
    )
    return load_prompt("extract").format(faq_catalogue=catalogue)


def user_prompt(state: ConversationState, message: InboundMessage, config: ScreeningConfig) -> str:
    """`state.transcript_tail` must not yet contain `message`."""
    local = message.received_at.astimezone(ZoneInfo(candidate_timezone(state, config)))
    if state.pending_confirmation:
        asking_for = f"confirmation of {state.pending_confirmation}"
    else:
        asking_for = ASKING_FOR[state.stage]
    return (
        "<context>\n"
        f"Asking for: {asking_for}\n"
        f"Country: {candidate_country(state)}\n"
        f"Candidate's local date: {local.date().isoformat()} ({local.strftime('%A')})\n"
        f"Conversation language so far: {state.language}\n"
        "</context>\n"
        f"<recent_conversation>\n{render_transcript(state.transcript_tail)}\n</recent_conversation>\n"
        f"<candidate_message>\n{message.text}\n</candidate_message>"
    )


def render_transcript(lines: list[TranscriptLine]) -> str:
    if not lines:
        return "(none)"
    speaker = {"agent": "Alex", "candidate": "Candidate"}
    return "\n".join(f"{speaker[line.role]}: {line.text}" for line in lines)


def extract(
    state: ConversationState,
    message: InboundMessage,
    *,
    llm: LLMClient,
    config: ScreeningConfig,
) -> LLMResult[Extraction]:
    """Raises LLMError when the model can't be reached or returns nothing usable."""
    return llm.structured(
        purpose="extract",
        system=system_prompt(config),
        messages=[{"role": "user", "content": user_prompt(state, message, config)}],
        schema=Extraction,
        tier="fast",
    )
