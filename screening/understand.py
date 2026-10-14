"""Understand: turn one candidate message into a typed Extraction.

The LLM reads and labels; it does not decide. The policy validates every value
with the field-type catalog and chooses the next step.

The record's `fields` part is built per vacancy (CONTRACTS §7): one optional key
per asked field, typed by its field type, so constrained decoding can only return
answers for this job's fields, in shapes code knows how to validate.

Prompt layout, for caching: the system prompt is identical across a vacancy's
conversations (rules, field list, FAQ catalogue, examples), and everything
specific to this conversation goes in the user message.
"""

from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, create_model

from screening.config import FieldSpec, ScreeningConfig, VacancyConfig
from screening.fields import raw_type
from screening.llm import LLMClient, LLMResult
from screening.locale import candidate_country, candidate_timezone
from screening.prompts import load_prompt
from screening.schemas import ConversationState, InboundMessage, Stage, TranscriptLine

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

# How each field type is described in the prompt's field list.
KIND = {
    "text": "name",
    "boolean": "yes/no",
    "city": "place",
    "enum_multi": "options",
    "experience": "work history",
    "date": "date",
}


class Extraction(BaseModel):
    intent: Intent
    language: Literal["es", "en"]
    consent: Literal["yes", "no"] | None = None
    confirmation: Literal["confirm", "deny"] | None = None
    question: str | None = None
    faq_id: str | None = None
    detail: str | None = None  # the candidate's own detail on an unclear yes/no, for the recruiter
    fields: Any = None  # per vacancy: see extraction_model

    def field(self, name: str) -> Any:
        """The raw answer for one field, or None when the message didn't give it."""
        return getattr(self.fields, name, None)


_MODELS: dict[str, type[Extraction]] = {}


def extraction_model(vacancy: VacancyConfig) -> type[Extraction]:
    """The Extraction schema for one vacancy: `fields` has a key per asked field."""
    key = vacancy.model_dump_json()  # a changed config gets a new model
    if key not in _MODELS:
        fields = create_model(
            f"Fields_{vacancy.id}",
            __doc__='Raw answers as the candidate gave them; null = "not in this message".',
            **{spec.name: (raw_type(spec) | None, None) for spec in vacancy.asked},
        )
        _MODELS[key] = create_model(
            f"Extraction_{vacancy.id}", __base__=Extraction, fields=(fields, fields())
        )
    return _MODELS[key]


def system_prompt(config: ScreeningConfig, vacancy: VacancyConfig) -> str:
    catalogue = "\n".join(
        f"- {entry.id}: " + " / ".join(entry.questions["es"] + entry.questions["en"])
        for entry in config.faq
    )
    return load_prompt("extract").format(
        job_title=vacancy.title["en"],
        field_list="\n".join(_describe(spec) for spec in vacancy.asked),
        faq_catalogue=catalogue,
    )


def _describe(spec: FieldSpec) -> str:
    line = f"- {spec.name} ({KIND[spec.type]}): {spec.label['en']}"
    if spec.options:
        line += f". Allowed values: {', '.join(spec.options)}"
    return line


def asking_for(state: ConversationState, vacancy: VacancyConfig) -> str:
    """What Alex's last message asked, in the words the prompt uses."""
    pending = state.pending_confirmation or {}
    if pending.get("type") == "out_of_area":
        return f"confirmation that they'd work in {pending['city_text']}, outside the service area"
    if state.stage is Stage.CONSENT:
        return "consent"
    if state.stage is Stage.CONFIRM:
        return "confirm (Alex read back the summary)"
    if state.stage is Stage.COLLECTING and state.current_field:
        spec = vacancy.field(state.current_field)
        return f"{spec.name} ({spec.label['en']})"
    return "nothing (screening finished)"


def user_prompt(
    state: ConversationState,
    message: InboundMessage,
    config: ScreeningConfig,
    vacancy: VacancyConfig,
) -> str:
    """`state.transcript_tail` must not yet contain `message`."""
    local = message.received_at.astimezone(ZoneInfo(candidate_timezone(state, config)))
    return (
        "<context>\n"
        f"Asking for: {asking_for(state, vacancy)}\n"
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
    vacancy = config.vacancy(state.vacancy_id)
    return llm.structured(
        purpose="extract",
        system=system_prompt(config, vacancy),
        messages=[{"role": "user", "content": user_prompt(state, message, config, vacancy)}],
        schema=extraction_model(vacancy),
        tier="fast",
    )
