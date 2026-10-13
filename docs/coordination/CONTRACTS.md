# Contracts between lanes

Owned by the lead. Lanes code against this file. To change it, add a request under "Contract change requests" in your status file; the lead updates this file and logs the change in `DECISIONS.md`.

Version: 3

## 1. Engine schemas (`screening/schemas.py`, engine lane, task E1)

```python
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class Channel(StrEnum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    SIM = "sim"                 # evals and CLI

class Status(StrEnum):
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    NEEDS_REVIEW = "needs_review"
    DISQUALIFIED = "disqualified"
    ABANDONED = "abandoned"
    OPTED_OUT = "opted_out"

class Stage(StrEnum):           # order = the conversation order in the spec
    CONSENT = "consent"
    NAME = "name"
    LICENSE = "license"
    LOCATION = "location"
    AVAILABILITY = "availability"
    SCHEDULE = "schedule"
    EXPERIENCE = "experience"
    START_DATE = "start_date"
    CONFIRM = "confirm"
    DONE = "done"

class FieldStatus(StrEnum):
    MISSING = "missing"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"         # unresolved or unclear; goes to human review

class FieldValue(BaseModel, Generic[T]):
    value: T | None = None
    status: FieldStatus = FieldStatus.MISSING
    source_message_id: str | None = None   # provenance: which inbound message gave it
    attempts: int = 0                      # re-asks used for this field (max from config)
    note: str | None = None                # short reason when flagged, e.g. "license expired"

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
    city: str                   # canonical key from service_areas.yaml, e.g. "barcelona"

class ExperienceItem(BaseModel):
    platform: str               # normalized key: glovo, uber_eats, just_eat, rappi, didi_food, other
    years: float                # months converted, 0-40

class CandidateProfile(BaseModel):
    full_name: FieldValue[str] = FieldValue[str]()
    has_driver_license: FieldValue[bool] = FieldValue[bool]()
    location: FieldValue[Location] = FieldValue[Location]()
    availability: FieldValue[list[Availability]] = FieldValue[list[Availability]]()
    schedule: FieldValue[list[Schedule]] = FieldValue[list[Schedule]]()
    experience: FieldValue[list[ExperienceItem]] = FieldValue[list[ExperienceItem]]()  # [] accepted = no experience
    start_date: FieldValue[date] = FieldValue[date]()

class TranscriptLine(BaseModel):
    role: Literal["candidate", "agent"]
    text: str
    at: datetime
    message_id: str | None = None

class ConversationState(BaseModel):
    conversation_id: str
    channel: Channel
    status: Status = Status.IN_PROGRESS
    stage: Stage = Stage.CONSENT
    language: Literal["es", "en"] = "es"
    country_hint: Literal["ES", "MX"] | None = None   # from phone prefix until location is known
    consent_at: datetime | None = None
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    disqualify_reason: Literal["no_license", "out_of_area"] | None = None
    review_reasons: list[str] = []      # e.g. "license_unclear", "unresolved:location", "human_requested", "abuse"
    pending_confirmation: dict[str, Any] | None = None  # e.g. out-of-area city awaiting the candidate's confirm
    reminders_sent: int = 0
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    offtopic_strikes: int = 0
    transcript_tail: list[TranscriptLine] = []        # last N lines (config), engine-maintained, for LLM context
    summary: str | None = None                        # set when status leaves in_progress
    schema_version: int = 1

class InboundMessage(BaseModel):
    id: str                     # app's Message primary key as a string; evals use their own IDs
    text: str
    received_at: datetime       # aware; the engine uses this as "now" for the turn
    media: Literal["none", "audio", "image", "sticker", "other"] = "none"

class OutboundMessage(BaseModel):
    text: str
    kind: Literal["reply", "reminder", "close"]   # "close" is never dropped by the reply-to-latest rule

class Event(BaseModel):
    type: str                   # see the event catalogue below
    at: datetime
    data: dict[str, Any] = {}

class TurnResult(BaseModel):
    state: ConversationState
    outbound: list[OutboundMessage] = []
    events: list[Event] = []
    changed: bool = True        # False when handle_tick had nothing to do
```

Event catalogue: `conversation_started`, `consent_given`, `stage_entered`, `field_accepted`, `field_flagged`, `field_corrected`, `knockout_failed`, `status_changed`, `reminder_sent`, `reminder_deferred`, `faq_answered`, `offtopic`, `opt_out`, `human_requested`, `media_received`, `llm_call` (data: purpose, model, input_tokens, output_tokens, latency_ms), `llm_error`.

## 2. Engine API (`screening/engine.py`, tasks E5, E7)

```python
class EngineContext(BaseModel):          # or a frozen dataclass
    config: ScreeningConfig
    llm: LLMClient

def new_conversation(conversation_id: str, channel: Channel, *, phone: str | None,
                     language: Literal["es", "en"] | None, now: datetime) -> ConversationState
def start(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult
    # produces the opening message (AI disclosure, consent question)
def handle_message(state: ConversationState, message: InboundMessage, *, ctx: EngineContext) -> TurnResult
def handle_tick(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult
    # reminders, quiet-hours deferral, abandonment; changed=False when nothing is due
def next_due_at(state: ConversationState, *, config: ScreeningConfig) -> datetime | None
    # when the app should next call handle_tick; already moved past quiet hours. None = nothing scheduled.
```

Rules:
- All three turn functions are pure with respect to storage: they never touch a DB or network except through `ctx.llm`. `next_due_at` is pure and needs no `ctx`.
- They never raise on LLM failure. After retries they return a holding reply and an `llm_error` event. Bookkeeping updates as normal — `last_inbound_at`, `last_outbound_at` and `reminders_sent` (reset to 0: the holding reply counts as outbound contact, so reminder timing restarts from it) — because reminder timing depends on them and must not drift. Profile, stage, status, attempts and strikes are untouched; `transcript_tail` gains the inbound message and the holding reply.
- When `status` leaves `in_progress`, the engine sets `state.summary`, or `None` plus an `llm_error` event if the summary call failed.
- `screening.record.final_record(state) -> dict` builds the final JSON deterministically (no LLM):

```json
{"conversation_id": "…", "status": "qualified", "language": "es", "full_name": "Laura Pérez",
 "has_driver_license": true, "country": "ES", "city": "barcelona",
 "availability": ["part_time", "weekends"], "preferred_schedule": ["evening"],
 "delivery_experience": [{"platform": "glovo", "years": 1.5}], "start_date": "2026-10-19",
 "flags": [{"field": "start_date", "note": "vague answer, resolved to next Monday"}],
 "disqualify_reason": null, "review_reasons": [], "summary": "…"}
```

## 3. LLM client (`screening/llm/`, task E3)

```python
ModelTier = Literal["fast", "smart"]     # env LLM_MODEL_FAST (default claude-haiku-5-5), LLM_MODEL_SMART (default claude-sonnet-5-5)
M = TypeVar("M", bound=BaseModel)

class LLMUsage(BaseModel):
    model: str
    input_tokens: int          # total input, cached parts included
    output_tokens: int
    cache_read_tokens: int = 0     # billed ~0.1x; v2, defaults keep old callers valid
    cache_write_tokens: int = 0    # billed ~1.25x
    latency_ms: int

class LLMResult(BaseModel, Generic[T]):
    value: T
    usage: LLMUsage

class LLMError(Exception): ...

class LLMClient(Protocol):
    def structured(self, *, purpose: str, system: str, messages: list[dict[str, str]],
                   schema: type[M], tier: ModelTier = "fast") -> LLMResult[M]: ...
    def text(self, *, purpose: str, system: str, messages: list[dict[str, str]],
             tier: ModelTier = "fast", max_tokens: int = 300) -> LLMResult[str]: ...
```

- Implementations: `AnthropicClient` (timeout, 3 retries with backoff, raises `LLMError`) and `FakeLLM` (scripted responses keyed by `purpose`, for tests).
- Engine purposes: `extract` (fast), `compose` (fast), `summary` (smart).
- Evals may swap model names through env to compare configurations.

## 4. Config (`screening/config/`, task E1)

- `service_areas.yaml`: per country, a timezone and a set of cities. Each city has a canonical key, a display name, aliases and neighborhoods, and the matcher maps any of them to the city. Sample data covers ES (madrid, barcelona, valencia, sevilla, malaga, bilbao) and MX (cdmx, guadalajara, monterrey, puebla, queretaro).
- `faq.yaml`: entries with an `id`, example questions and answers in `es` and `en`. Values are placeholders and marked as such.
- `screening.yaml`: reminder schedule (`15m, 2h, 20h`), `abandon_after: 24h`, quiet hours `21:00-09:00`, `max_attempts_per_field: 2`, `max_offtopic_strikes: 1`, `start_date_max_days: 183`, `transcript_tail_size: 12`, message limits.
- `screening.config.load_config(path: Path | None = None) -> ScreeningConfig` is a Pydantic model. It applies `DEMO_TIME_SCALE` (e.g. 60 turns 15 min into 15 s).

## 5. Django side (app lane)

Models:
- `apps/candidates/models.py`:
  - `Candidate`: phone (E.164, unique, nullable), name, created_at.
  - `Conversation`:
    - Identity and channel: UUID primary key, candidate FK, `channel`.
    - Mirrored from `state` for filtering: `status` (indexed), `stage`, `language`, `country`, `city`.
    - `state` (JSONField holding `ConversationState.model_dump(mode="json")`).
    - Results: `final_record` (JSON, nullable), `summary`.
    - Timestamps: `started_at`, `last_inbound_at`, `completed_at`, `next_tick_at` (indexed, nullable).
  - `ReviewAction`: conversation FK, user FK, action (`approve`, `reject`, `needs_review`, `note`), note, created_at.
- `apps/messaging/models.py`:
  - `Message`: conversation FK, direction (`in`/`out`), kind, text, media, `provider_sid` (unique, nullable, for idempotency), created_at, `processed_at` (nullable), `suppressed` (bool), send_error.
  - `Event`: conversation FK, type, data JSON, created_at.

Processing pipeline (`apps/messaging/services.py` plus the `run_worker` command):
1. The webhook or web chat view stores an inbound `Message` (`processed_at=None`) and returns immediately. Twilio gets an empty 200.
2. Worker loop:
   - Claim a conversation that has unprocessed inbound messages, with `select_for_update(skip_locked=True)` on Postgres. SQLite runs a single worker.
   - Take its oldest unprocessed message and call `engine.handle_message`.
   - Persist the state, the mirrored columns, outbound `Message`s and `Event`s in one transaction.
3. **Reply-to-latest:** if another unprocessed inbound exists for the same conversation after the turn, mark this turn's `reply` and `reminder` outbound as `suppressed=True` and don't send them. Always send `close` messages.
4. Send through the channel adapter after commit, and record `provider_sid` or `send_error`.
5. Reminders: the worker scans conversations with `status=in_progress` and `next_tick_at <= now`, calls `engine.handle_tick`, and recomputes `next_tick_at` from config.

Channel adapters (`apps/messaging/channels.py`), each implementing `send(conversation, OutboundMessage) -> str | None`:
- `WebChannel`: no-op; the chat page polls.
- `WhatsAppChannel`: Twilio REST, `from=TWILIO_WHATSAPP_FROM`.

Entry points:
- `/chat/`: a simulated job-ad link. The candidate picks ES or MX and the language, then the web chat starts and `engine.start` is called.
- `/apply/`: a form with name and phone. It creates a WhatsApp conversation and calls `engine.start`, so the agent sends the first message.
- `/webhooks/twilio/whatsapp/`:
  - Validates the Twilio signature, and is idempotent on `MessageSid`.
  - Detects media from `NumMedia` / `MediaContentType0`.
  - Routes the message to the active conversation for that phone, or creates one and calls `engine.start` first.

Recruiter override: the dashboard sets `Conversation.status`, writes a `ReviewAction` and an `Event` (`recruiter_override`), and never calls the engine.

## 6. Evals (evals lane)

- Evals import only `screening` (no Django) and use `Channel.SIM`.
- Scenario files: `evals/scenarios/<id>.yaml` with `persona`, `language`, `country`, `behaviors`, an `expected` record (same keys as `final_record`) and `expected_status`.
- The runner writes `evals/runs/<timestamp>/` (transcripts as JSON and Markdown, plus `scores.json`) and `evals/reports/<name>.md`.
