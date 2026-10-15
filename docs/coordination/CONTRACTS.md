# Contracts between lanes

Owned by the lead. Lanes code against this file. To change it, add a request under "Contract change requests" in your status file; the lead updates this file and logs the change in `DECISIONS.md`.

Version: 4.2

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
    SIM = "sim"  # evals and CLI


class Status(StrEnum):
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    NEEDS_REVIEW = "needs_review"
    DISQUALIFIED = "disqualified"
    ABANDONED = "abandoned"
    OPTED_OUT = "opted_out"


class Stage(StrEnum):  # v4: generic phases, not one value per field (see §7)
    CONSENT = "consent"
    COLLECTING = "collecting"  # which field is current: state.current_field
    CONFIRM = "confirm"
    DONE = "done"


class FieldStatus(StrEnum):
    MISSING = "missing"
    ACCEPTED = "accepted"
    FLAGGED = "flagged"  # unresolved or unclear; goes to human review


class FieldValue(BaseModel, Generic[T]):
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


class CandidateProfile(BaseModel):  # v4: keyed by the vacancy's field names, see §7
    fields: dict[str, FieldValue[Any]] = {}


class TranscriptLine(BaseModel):
    role: Literal["candidate", "agent"]
    text: str
    at: datetime
    message_id: str | None = None


class ConversationState(BaseModel):
    conversation_id: str
    channel: Channel
    vacancy_id: str  # v4: which VacancyConfig this screening is against (§7)
    status: Status = Status.IN_PROGRESS
    stage: Stage = Stage.CONSENT
    current_field: str | None = None  # v4: which field is being asked, when stage=COLLECTING
    language: Literal["es", "en"] = "es"
    country_hint: Literal["ES", "MX"] | None = None  # from phone prefix until location is known
    consent_at: datetime | None = None
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    disqualify_reason: str | None = (
        None  # v4: "out_of_area", or "no_<outcome_name>" for a boolean knockout
    )
    review_reasons: list[
        str
    ] = []  # e.g. "<outcome_name>_unclear", "unresolved:<field>", "unresolved:confirm", "human_requested", "abuse"
    pending_confirmation: dict[str, Any] | None = (
        None  # e.g. out-of-area city awaiting the candidate's confirm
    )
    reminders_sent: int = 0
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    offtopic_strikes: int = 0
    transcript_tail: list[
        TranscriptLine
    ] = []  # last N lines (config), engine-maintained, for LLM context
    summary: str | None = None  # set when status leaves in_progress
    preference_score: float = (
        0.0  # v4: sum of matched `preferred` fields' weights (§7); ranking only
    )
    schema_version: int = 2


class InboundMessage(BaseModel):
    id: str  # app's Message primary key as a string; evals use their own IDs
    text: str
    received_at: datetime  # aware; the engine uses this as "now" for the turn
    media: Literal["none", "audio", "image", "sticker", "other"] = "none"


class OutboundMessage(BaseModel):
    text: str
    kind: Literal[
        "reply", "reminder", "close"
    ]  # "close" is never dropped by the reply-to-latest rule


class Event(BaseModel):
    type: str  # see the event catalogue below
    at: datetime
    data: dict[str, Any] = {}


class TurnResult(BaseModel):
    state: ConversationState
    outbound: list[OutboundMessage] = []
    events: list[Event] = []
    changed: bool = True  # False when handle_tick had nothing to do
```

Event catalogue: `conversation_started`, `consent_given`, `stage_entered`, `field_accepted`, `field_flagged`, `field_corrected`, `knockout_failed`, `status_changed`, `reminder_sent`, `reminder_deferred`, `faq_answered`, `offtopic`, `opt_out`, `human_requested`, `media_received`, `llm_call` (data: purpose, model, input_tokens, output_tokens, latency_ms), `llm_error`.

## 2. Engine API (`screening/engine.py`, tasks E5, E7)

```python
class EngineContext(BaseModel):          # or a frozen dataclass
    config: ScreeningConfig
    llm: LLMClient

def new_conversation(conversation_id: str, channel: Channel, *, vacancy_id: str, phone: str | None,
                     language: Literal["es", "en"] | None, now: datetime) -> ConversationState
    # v4: vacancy_id must match a VacancyConfig in ctx.config.vacancies (§7); raises if not
def start(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult
    # produces the opening message (AI disclosure, consent question)
def handle_message(state: ConversationState, message: InboundMessage, *, ctx: EngineContext) -> TurnResult
def handle_tick(state: ConversationState, *, now: datetime, ctx: EngineContext) -> TurnResult
    # reminders, quiet-hours deferral, abandonment; changed=False when nothing is due
def next_due_at(state: ConversationState, *, config: ScreeningConfig) -> datetime | None
    # when the app should next call handle_tick; already moved past quiet hours. None = nothing scheduled.
def forget_undelivered(state: ConversationState, dropped: list[OutboundMessage]) -> ConversationState
    # v4.2 (E20, D36): a copy whose transcript_tail no longer holds the replies the shell dropped
    # under reply-to-latest (§5 step 3), so the model and the recruiter summary see only what was sent.
```

Rules:
- All three turn functions are pure with respect to storage: they never touch a DB or network except through `ctx.llm`. `next_due_at` and `forget_undelivered` are pure and need no `ctx`.
- They never raise on LLM failure. After retries they return a holding reply and an `llm_error` event. Bookkeeping updates as normal — `last_inbound_at`, `last_outbound_at` and `reminders_sent` (reset to 0: the holding reply counts as outbound contact, so reminder timing restarts from it) — because reminder timing depends on them and must not drift. Profile, stage, status, attempts and strikes are untouched; `transcript_tail` gains the inbound message and the holding reply.
- When `status` leaves `in_progress`, the engine sets `state.summary`, or `None` plus an `llm_error` event if the summary call failed.
- `screening.record.final_record(state) -> dict` builds the final JSON deterministically (no LLM). **v4: the fixed top-level keys (`full_name`, `has_driver_license`, ...) are gone — every profile field, required or preferred, is reported under `"fields"`, keyed by its name from the vacancy config:**

```json
{"conversation_id": "…", "vacancy_id": "driver", "status": "qualified", "language": "es",
 "fields": {
   "full_name": "Laura Pérez",
   "has_driver_license": true,
   "location": {"country": "ES", "city": "barcelona"},
   "availability": ["part_time", "weekends"],
   "schedule": ["evening"],
   "experience": [{"platform": "glovo", "years": 1.5}],
   "start_date": "2026-10-19"
 },
 "flags": [{"field": "start_date", "note": "vague answer, resolved to next Monday"}],
 "disqualify_reason": null, "review_reasons": [], "summary": "…",
 "preference_score": 0.0}
```

A field missing or flagged is simply absent from `"fields"` (not `null` — there's no fixed key list to null out) and appears in `"flags"` instead when flagged. This is a breaking format change from v3: the app's dashboard/CSV export and evals' scenario `expected` blocks both read this shape and need updating (BOARD, Phase 2).

## 3. LLM client (`screening/llm/`, task E3)

```python
ModelTier = Literal[
    "fast", "smart"
]  # env LLM_MODEL_FAST (default claude-haiku-5-5), LLM_MODEL_SMART (default claude-sonnet-5-5)
M = TypeVar("M", bound=BaseModel)


class LLMUsage(BaseModel):
    model: str
    input_tokens: int  # total input, cached parts included
    output_tokens: int
    cache_read_tokens: int = 0  # billed ~0.1x; v2, defaults keep old callers valid
    cache_write_tokens: int = 0  # billed ~1.25x
    latency_ms: int


class LLMResult(BaseModel, Generic[T]):
    value: T
    usage: LLMUsage


class LLMError(Exception): ...


class LLMClient(Protocol):
    def structured(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        schema: type[M],
        tier: ModelTier = "fast",
    ) -> LLMResult[M]: ...
    def text(
        self,
        *,
        purpose: str,
        system: str,
        messages: list[dict[str, str]],
        tier: ModelTier = "fast",
        max_tokens: int = 300,
    ) -> LLMResult[str]: ...
```

- Implementations: `AnthropicClient` (timeout, 3 retries with backoff, raises `LLMError`) and `FakeLLM` (scripted responses keyed by `purpose`, for tests).
- Engine purposes: `extract` (fast), `compose` (fast), `summary` (smart).
- Evals may swap model names through env to compare configurations.
- **`call_cost(llm_call_data) -> float` moves from `evals/pricing.py` to `screening/llm/pricing.py`** (app's request: the dashboard's analytics page needs it for cost-per-conversation, and the app shouldn't import the evals package). Evals imports it from the new location too; one price table, not two. Engine lane's to move (Phase 2, BOARD).

## 4. Config (`screening/config/`, task E1)

- `service_areas.yaml`: per country, a timezone and a set of cities. Each city has a canonical key, a display name, aliases and neighborhoods, and the matcher maps any of them to the city. Sample data covers ES (madrid, barcelona, valencia, sevilla, malaga, bilbao) and MX (cdmx, guadalajara, monterrey, puebla, queretaro).
- `faq.yaml`: entries with an `id`, example questions and answers in `es` and `en`. Values are placeholders and marked as such.
- `screening.yaml`: reminder schedule (`15m, 2h, 20h`), `abandon_after: 24h`, quiet hours `21:00-09:00`, `max_attempts_per_field: 2`, `max_offtopic_strikes: 1`, `start_date_max_days: 183`, `transcript_tail_size: 12`, message limits.
- `screening.config.load_config(path: Path | None = None) -> ScreeningConfig` is a Pydantic model. It applies `DEMO_TIME_SCALE` (e.g. 60 turns 15 min into 15 s).
- **v4:** `vacancies/<id>.yaml`, one file per vacancy (see §7). Loaded into `ScreeningConfig.vacancies: dict[str, VacancyConfig]`; `config.vacancy(id) -> VacancyConfig` raises `KeyError` with the list of valid ids if unknown (the app and CLI surface that as a 404 / argument error, not a 500).

## 5. Django side (app lane)

Models:
- `apps/candidates/models.py`:
  - `Candidate`: phone (E.164, unique, nullable), name, created_at.
  - `Conversation`:
    - Identity and channel: UUID primary key, candidate FK, `channel`.
    - **v4:** `vacancy_id` (indexed; matches `ScreeningConfig.vacancies`), set at creation, mirrored from `state.vacancy_id`.
    - Mirrored from `state` for filtering: `status` (indexed), `stage`, `language`, `country`, `city`.
    - **v4:** `preference_score` (float, indexed — the dashboard queue sorts qualified candidates by it), mirrored from `state.preference_score`.
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
3. **Reply-to-latest:** if another unprocessed inbound exists for the same conversation after the turn, mark this turn's `reply` and `reminder` outbound as `suppressed=True` and don't send them. Always send `close` messages. **v4.2:** pass the suppressed ones to `engine.forget_undelivered` and persist the state it returns (same transaction as step 2). The evals simulator does the same in its burst handling.
4. Send through the channel adapter after commit, and record `provider_sid` or `send_error`.
5. Reminders: the worker scans conversations with `status=in_progress` and `next_tick_at <= now`, calls `engine.handle_tick`, and recomputes `next_tick_at` from config.

Channel adapters (`apps/messaging/channels.py`), each implementing `send(conversation, OutboundMessage) -> str | None`:
- `WebChannel`: no-op; the chat page polls.
- `WhatsAppChannel`: Twilio REST, `from=TWILIO_WHATSAPP_FROM`.

Entry points:
- `/chat/`: a simulated job-ad link. The candidate picks ES or MX, the language, and **(v4) the vacancy** — in production this would be one link per real job ad, so the picker is a demo convenience, not the production shape — then the web chat starts and `engine.start` is called.
- `/apply/`: a form with name and phone. It creates a WhatsApp conversation and calls `engine.start`, so the agent sends the first message. **v4:** also needs a vacancy, same as `/chat/`.
- `/webhooks/twilio/whatsapp/`:
  - Validates the Twilio signature, and is idempotent on `MessageSid`.
  - Detects media from `NumMedia` / `MediaContentType0`.
  - Routes the message to the active conversation for that phone, or creates one and calls `engine.start` first.

Recruiter override: the dashboard sets `Conversation.status`, writes a `ReviewAction` and an `Event` (`recruiter_override`), and never calls the engine.

## 6. Evals (evals lane)

- Evals import only `screening` (no Django) and use `Channel.SIM`.
- Scenario files: `evals/scenarios/<id>.yaml` with `persona`, `language`, `country`, `behaviors`, an `expected` record (same keys as `final_record`) and `expected_status`. **v4: scenarios gain `vacancy: <id>` (default `driver`, so the existing 20 scenarios need only that one line added); `expected` follows the new `final_record` shape (§2) — a flat `expected.fields` dict instead of top-level field keys.**
- The runner writes `evals/runs/<timestamp>/` (transcripts as JSON and Markdown, plus `scores.json`) and `evals/reports/<name>.md`.

## 7. Vacancies and dynamic fields (`screening/config/vacancies/`, `screening/policy.py`; CONTRACTS v4)

**Why:** §1's `CandidateProfile` and `policy.py`'s field list were hardcoded to Grupo Sazón's one driver role. A second vacancy, or a second client, needs different required fields without an engineer editing Python — and a field that's a hard requirement for one role (a driver's license) can be a pure plus for another (prefer the candidate who has one, in a tie, for a kitchen role that doesn't need it). This section generalizes the fixed 7-field model into a small, fixed **field-type catalog** (engineer-owned, auditable) that a **vacancy config** (ops-authored YAML today; the natural shape for a future recruiter UI to generate) composes from. See D24 for the full reasoning and the explicit tie-break rule.

### Field types (the catalog; closed — adding one is an engineering change, not a config change)

| Type | Validator reused from (today's code) | Value shape | Can be a knockout when `required`? |
| --- | --- | --- | --- |
| `text` | `validate_name`-style (one soft re-ask for a second word) | `str` | No |
| `boolean` | `validate_license` | `bool` | Yes — a `false` value |
| `city` | `match_city` | `Location` | Yes — `not_served` (after the existing out-of-area confirmation dance) |
| `enum_multi` | `validate_availability`/`validate_schedule` | `list[str]`, from the field's `options` | No |
| `experience` | `validate_experience` | `list[ExperienceItem]` | No — per the spec, no experience is never a knockout, required or not |
| `date` | `validate_start_date` | `date` | No |

`text` and `city` may only be `required` or `off` in a `FieldSpec` (never `preferred`) — asking a candidate's name "preferentially," or treating being in the service area as a nice-to-have, isn't a meaningful product rule, and disallowing it in the schema (a `model_validator` on `VacancyConfig`) is cheaper than someone configuring it by accident. The other four types allow all three requirement levels.

### `FieldSpec` and `VacancyConfig`

```python
FieldType = Literal["text", "boolean", "city", "enum_multi", "experience", "date"]
Requirement = Literal["required", "preferred", "off"]
NEVER_PREFERRED: set[FieldType] = {"text", "city"}


class FieldSpec(BaseModel):
    name: str  # key in CandidateProfile.fields and final_record["fields"]
    type: FieldType
    requirement: Requirement
    label: dict[Literal["es", "en"], str]  # the question, in the agent's own words, per language
    weight: float = 0.0  # preferred only: contribution to preference_score (see below)
    options: list[str] | None = None  # required for enum_multi, and only for enum_multi
    # v4.1, additive, approved by Vlad 2026-10-14 (status/engine.md):
    reason: str | None = (
        None  # outcome-string name: no_<reason>, <reason>_unclear (falls back to `name`)
    )
    summary: dict[
        str, str
    ] = {}  # read-back noun, "es"/"en" (+ optional "es_ES"/"es_MX"); falls back to `name`
    option_labels: dict[
        str, dict[str, str]
    ] = {}  # option -> locale -> display text; falls back to the option value
    exclusive_options: list[
        str
    ] = []  # enum_multi options that stand alone (e.g. schedule's "flexible")

    @model_validator(mode="after")
    def _check(self) -> "FieldSpec":
        if self.type in NEVER_PREFERRED and self.requirement == "preferred":
            raise ValueError(f"{self.name}: a {self.type} field can't be preferred")
        if (self.type == "enum_multi") != bool(self.options):
            raise ValueError(f"{self.name}: options are required for enum_multi, and only there")
        if set(self.exclusive_options) - set(self.options or []):
            raise ValueError(f"{self.name}: exclusive_options must be a subset of options")
        if self.weight and self.requirement != "preferred":
            raise ValueError(f"{self.name}: only a preferred field can have a weight")
        return self

    @property
    def outcome_name(self) -> str:
        return self.reason or self.name


class VacancyConfig(BaseModel):
    id: str
    title: dict[Literal["es", "en"], str]
    fields: list[FieldSpec]  # declared order; `.asked` below is the policy order

    @model_validator(mode="after")
    def _check(self) -> "VacancyConfig":
        names = [spec.name for spec in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"{self.id}: duplicate field names")
        return self

    @property
    def asked(self) -> list[FieldSpec]:
        """Required fields, in declared order, then preferred ones, in declared order."""
        return [f for f in self.fields if f.requirement == "required"] + [
            f for f in self.fields if f.requirement == "preferred"
        ]
```

Loaded from `screening/config/vacancies/<id>.yaml`, one file per vacancy — same pattern as `service_areas.yaml`/`faq.yaml`, just one level deeper since there are multiple vacancies. Two ship with v4: `driver` (today's Grupo Sazón fields, migrated verbatim — `has_driver_license` stays `required`, `reason: license` so outcome strings are unchanged) and `kitchen_prep` (no driving involved: `has_driver_license` is `preferred, weight: 1.5` instead of `required`, plus a preferred food-handler-certificate field — this is the concrete case D25 is about, not a hypothetical).

### Ordering and requirement semantics (replaces the old fixed `FIELDS` constant in `policy.py`)

1. **Required fields are asked first, in the vacancy's declared order; preferred fields only after every required field is `accepted` or `flagged`.** This isn't a config option — it's a policy rule, because "knockouts first, so an ineligible candidate finishes in a few messages" (`process-design.md`) only holds if preference questions can't come before a disqualifying one. `current_field` and `Stage.COLLECTING` cover both phases; the engine doesn't expose which phase it's in beyond that (the vacancy config's own field order already says what's required vs. preferred).
2. **A `required` field behaves exactly as today:** up to `max_attempts_per_field` re-asks, then flagged (`field_flagged`, `unresolved:<field>`) and the conversation moves on; a `boolean`/`city` knockout result disqualifies immediately (`disqualify_reason`, see §1).
3. **A `preferred` field is asked once.** If the answer doesn't validate, or there's no answer, the field is simply left `missing` — no re-ask, no flag, no event, no effect on `status`. This is deliberate: it's not worth a recruiter's review time, or a candidate's patience, over a field that was never going to disqualify them.
4. **A knockout-shaped result on a `preferred` field never disqualifies.** `validate_license(False)` (say) still returns the same verdict regardless of the field's requirement level in this vacancy — the type's validator doesn't know what vacancy it's running under — but `policy.py` only *acts* on a knockout verdict when `requirement == "required"`. On a `preferred` field it's downgraded to a plain accepted value: the candidate without a license, applying to a role where it's merely preferred, is **not** disqualified, and `false` is stored normally for scoring.

### `preference_score` (ranking only — never a qualification gate)

Computed in `screening.record.final_record` (or a sibling `screening.scoring.score`) from the accepted `preferred` fields only, by a fixed, auditable formula per type — no field this flows through can also disqualify, by rule 4 above:

- `boolean`: `+weight` if the value is `true`, `0` otherwise.
- `enum_multi`: `+weight` if at least one selected option is in the field's `options` (i.e. any answer at all counts, today — a per-option weight is a plausible v5 if a client wants it, not built now).
- `experience`: `+weight * min(total_years, 5)` (capped, so one candidate's 20 years doesn't swamp everything else).
- `date`: not typically given a weight; no formula needed yet.

The score is **purely a queue-ordering signal** inside a `status`: it sorts qualified (and separately, needs-review) candidates against each other. It never changes `status`, never substitutes for a flagged or missing required field, and a candidate who fails a required field never reaches scoring at all. This keeps D3 intact — code still only *decides* qualification from required fields; preference is a separate, transparent, additive number a recruiter can see broken down (which fields, which weights) on the dashboard, not a black-box rank.

### While rebuilding CONFIRM: fix the read-back loop evals found

Not a v4 feature, but `policy.py`'s CONFIRM handling is being rewritten for the generic field list anyway, and evals found a real "never loop" violation in it (see `status/evals.md`): a correction that restates an already-correct value is still treated as a correction, so the identical read-back resends with no acknowledgement and no attempt cap — 8 times in one scenario. Fix while this code is already open: a "correction" that changes no stored value counts as a confirm (or gets one "anything else to change?"), and the read-back itself gets an attempt cap like any other field — flag and move on, don't resend forever.

### Migration from v3

The `driver` vacancy's `FieldSpec` list reproduces today's seven fields and their current required/knockout behavior exactly — this is not meant to change Grupo Sazón's actual screening, only to make it one configuration of a general system instead of the only possible one. Existing `evals/scenarios/*.yaml` need `vacancy: driver` added (one line) and their `expected` blocks reshaped to `fields: {...}` (§2). The seed data (`seed_demo`'s fixture) and any local dev database predate `schema_version: 2` and should be regenerated, not migrated — this is demo/dev data, not production records.
