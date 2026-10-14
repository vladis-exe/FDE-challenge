"""Engine data types shared by every lane (CONTRACTS.md §1).

These models are the boundary between the engine, the Django shell and the evals.
Change them only through a contract change request.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    SIM = "sim"  # evals and CLI


class Status(StrEnum):
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    NEEDS_REVIEW = "needs_review"
    DISQUALIFIED = "disqualified"
    ABANDONED = "abandoned"
    OPTED_OUT = "opted_out"


class Stage(StrEnum):  # v4: generic phases, not one value per field (CONTRACTS §7)
    CONSENT = "consent"
    COLLECTING = "collecting"  # which field is current: state.current_field
    CONFIRM = "confirm"
    DONE = "done"


class FieldStatus(StrEnum):
    MISSING = "missing"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"  # unresolved or unclear; goes to human review


class FieldValue(BaseModel, Generic[T]):  # noqa: UP046 -- syntax as written in CONTRACTS.md
    value: T | None = None
    status: FieldStatus = FieldStatus.MISSING
    source_message_id: str | None = None  # provenance: which inbound message gave it
    attempts: int = 0  # re-asks used for this field (max from config)
    note: str | None = None  # short reason when flagged, e.g. "license expired"


class Availability(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    WEEKENDS = "weekends"


class Schedule(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    FLEXIBLE = "flexible"


class Location(BaseModel):
    country: Literal["ES", "MX"]
    city: str  # canonical key from service_areas.yaml, e.g. "barcelona"


class ExperienceItem(BaseModel):
    platform: str  # normalized key: glovo, uber_eats, just_eat, rappi, didi_food, other
    years: float  # months converted, 0-40


class CandidateProfile(BaseModel):  # v4: keyed by the vacancy's field names (CONTRACTS §7)
    fields: dict[str, FieldValue[Any]] = {}


class TranscriptLine(BaseModel):
    role: Literal["candidate", "agent"]
    text: str
    at: datetime
    message_id: str | None = None


class ConversationState(BaseModel):
    conversation_id: str
    channel: Channel
    vacancy_id: str  # which VacancyConfig this screening is against (CONTRACTS §7)
    status: Status = Status.IN_PROGRESS
    stage: Stage = Stage.CONSENT
    current_field: str | None = None  # the field being asked, when stage = COLLECTING
    language: Literal["es", "en"] = "es"
    country_hint: Literal["ES", "MX"] | None = None  # from phone prefix until location is known
    consent_at: datetime | None = None
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    disqualify_reason: str | None = None  # "out_of_area", or "no_<field>" for a boolean knockout
    review_reasons: list[str] = []  # e.g. "<field>_unclear", "unresolved:<field>", "abuse"
    pending_confirmation: dict[str, Any] | None = None  # e.g. out-of-area city awaiting confirm
    reminders_sent: int = 0
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    offtopic_strikes: int = 0
    transcript_tail: list[TranscriptLine] = []  # last N lines (config), for LLM context
    summary: str | None = None  # set when status leaves in_progress
    preference_score: float = 0.0  # sum of matched preferred fields' weights; ranking only
    schema_version: int = 2


class InboundMessage(BaseModel):
    id: str  # app's Message primary key as a string; evals use their own IDs
    text: str
    received_at: datetime  # aware; the engine uses this as "now" for the turn
    media: Literal["none", "audio", "image", "sticker", "other"] = "none"


class OutboundMessage(BaseModel):
    text: str
    kind: Literal["reply", "reminder", "close"]  # "close" is never dropped by reply-to-latest


class Event(BaseModel):
    type: str  # see the event catalogue in CONTRACTS.md
    at: datetime
    data: dict[str, Any] = {}


class TurnResult(BaseModel):
    state: ConversationState
    outbound: list[OutboundMessage] = []
    events: list[Event] = []
    changed: bool = True  # False when handle_tick had nothing to do
