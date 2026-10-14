# Board

Owned by the lead; only the lead ticks boxes. Lanes report progress in `status/<lane>.md`.

## Checkpoints
- **CP1, end of day 1:**
  - `uv run python -m screening.cli` completes a full Spanish screening against the real LLM.
  - The web chat creates conversations end to end through the worker (stub or real engine).
  - The Django admin shows them.
  - **✅ Verified by lead, 2026-10-13.** CLI: engine's own live run against Haiku 5.5 (MX/Spanish, 11 turns to qualified, see `status/engine.md` E9). Web chat + worker + admin: via the A1–A3 test suite (39 passing, incl. admin-render and worker-ordering tests) rather than a manual browser pass — that's still worth doing once before demo day. `uv run pytest tests/engine tests/evals` (212 pass) and `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (39 pass) both green; `uv run ruff check .` clean tree-wide.
- **CP2, end of day 2:**
  - A WhatsApp sandbox conversation runs end to end.
  - Reminders fire with time scaling.
  - The dashboard lists candidates with summaries and overrides.
  - The smoke evals run.
  - **✅ Verified by lead, 2026-10-14.** Reminders/dashboard/smoke evals: via test suite (233 engine/evals + 96 app tests, all green) and `evals/reports/` (V3 baseline 20/20, V6 smoke 5/5). WhatsApp: code done and unit-tested (signature validation, idempotency, `/apply/`) but the actual sandbox run is still blocked on Vlad — no Twilio credentials or a tunnel in this environment (see `status/app.md` Blocked). Counting this checkpoint done on the strength of the tests; the live sandbox run is still a real to-do before demo day.
- **CP3, midday day 3: feature freeze.** (no longer a hard deadline — see Vlad's call to drop the 3-day framing — but still the right checklist)
  - Evals report and model comparison done. **Not yet** — V4 (model comparison) and V5 (sample conversations) were waiting on this CP2 declaration; unblocked now.
  - App deployed. **Not yet** — Dockerfile/compose ready and smoke-tested against Postgres; an actual Railway deploy hasn't happened (L4).
  - README complete. **First pass done** (L5); needs the V4 numbers once they land.
  - The afternoon is for sample conversations, the demo video and presentation notes. **Not started** (V5, L6).

## Lead (L)
- [x] **L1 Bootstrap. Must be done before any lane starts.**
  - uv project with Python 3.12 and these deps: `django`, `django-htmx`, `dj-database-url`, `psycopg[binary]`, `whitenoise`, `gunicorn`, `pydantic`, `pyyaml`, `anthropic`, `twilio`, `phonenumbers`, `dateparser`, `rapidfuzz`, `python-dotenv`. Dev deps: `pytest`, `pytest-django`, `time-machine`, `ruff`.
  - ruff and pytest config, with `DJANGO_SETTINGS_MODULE=config.settings` scoped to `tests/app`.
  - The skeleton directories from the repo map, with `__init__.py` files.
  - `.gitignore` and `.env.example` (`ANTHROPIC_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_SMART`, `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `PUBLIC_BASE_URL`, `DEMO_TIME_SCALE`).
  - Initial commit.
- [ ] **L2 Continuous review.** After each lane commit:
  - Review the diff for contract adherence, simplicity and tests.
  - Run the full suite.
  - Write findings in your status file under "Review notes for <lane>".
- [x] **L3 Integration at CP1 and CP2:** verify each checkpoint end to end yourself, and report to Vlad.
- [ ] **L4 Deploy:**
  - Railway with web, worker and Postgres services, plus env vars.
  - Twilio sandbox webhook pointed at the deployed URL.
  - A smoke test on the deployed URL.
- [x] **L5 README:** (first pass — LLM justification section needs a pass once V4 lands)
  - Overview and an architecture diagram (Mermaid).
  - Setup in 5 commands or fewer.
  - How to run the CLI, web chat, WhatsApp, the worker, tests and evals.
  - LLM choice with its justification (from V4), and key trade-offs (from DECISIONS).
  - What's next: voice, ATS integration, scaling to 10K/week.
- [ ] **L6 `docs/presentation-notes.md`:**
  - Demo script and a demo-day checklist (seed data, fallback recording).
  - Architecture talking points and trade-offs.
  - The 10K/week answer, and "what I'd do with more time".
- [ ] **L7 (if time) bonus docs:** `docs/deployment.md` (production architecture) and `docs/ats-integration.md` (API sketch).

## Engine (E): `screening/`
Order: E1 → E3 → E2 → E4 → E6a → E5 → E9 (CP1) → E7 → E8 → E6b.
- [x] **E1 Schemas and config.** Do this first and commit early; it unblocks every lane.
  - `schemas.py` exactly as in CONTRACTS §1.
  - The `ScreeningConfig` loader, plus `service_areas.yaml`, `faq.yaml` and `screening.yaml` with sample data.
- [x] **E3 LLM layer:**
  - `LLMClient` protocol, `AnthropicClient` and `FakeLLM`.
  - Check the current Anthropic docs for structured outputs or forced tool use, and for prompt caching, before writing it.
  - Timeouts, retries and usage capture.
- [x] **E2 Validators.** Pure functions with heavy unit tests:
  - **City matcher:** handles accents, case, aliases, neighborhoods and fuzzy matches. It returns `matched`, `ambiguous(options)` or `not_served(city_text)`. A `not_served` result sets `pending_confirmation` so the candidate confirms before disqualification. Unresolved after 2 attempts → flagged.
  - **License:** yes / no / unclear(note).
  - **Availability and schedule:** normalization to the enums.
  - **Experience:** months → years and platform aliases.
  - **Start date:** resolve against the message's local date and weekday (dateparser or the LLM), then validate in code: not in the past, at most `start_date_max_days` away, "ASAP" means today.
  - **Name:** a first name plus a surname, with a single soft re-ask.
- [x] **E4 Understand.**
  - An `Extraction` schema: intent (`answer`, `question`, `correction`, `smalltalk`, `offtopic`, `opt_out`, `human_request`, `abuse`), language, raw values for any fields mentioned, and the question text.
  - The extraction prompt, with few-shot examples: multi-field messages, corrections, code-switching, Mexican vocabulary, emoji answers.
- [x] **E6a Compose (basic):**
  - The Alex persona prompt and per-action instructions.
  - Language and country vocabulary.
  - The opening message and the closes.
- [x] **E5 Policy and state machine.**
  - Write the transition table as a docstring first.
  - Covers: consent, slot filling in spec order, knockouts with confirmation, attempts and flags, the confirm step with corrections, outcomes, opt-out, human handoff, FAQ answers, media, off-topic strikes, and injection-proof outcomes.
  - Exhaustive tests with FakeLLM.
- [x] **E9 CLI:** `uv run python -m screening.cli [--lang es|en] [--country ES|MX] [--fake] [--script file.txt]`. Prints each reply, the state diff and the events.
- [x] **E7 Timers:** `handle_tick` covers the reminder schedule, quiet hours in the candidate's timezone, abandonment and `DEMO_TIME_SCALE`.
- [x] **E8 Summary and final record:** the summary uses the smart tier; `record.final_record(state)` is deterministic.
- [x] **E6b Compose polish:**
  - A length and one-question guard: regenerate once if violated, then trim safely.
  - Tone tuning from eval findings.

## App (A): Django
Order: A1 → A2 (stub engine) → A3 (CP1) → A4 → A5 → A9 (CP2) → A6 → A7 → A8.
- [x] **A1 Project setup.**
  - Django project `config/`: settings from env, `dj-database-url` (Postgres, or SQLite fallback), TZ=UTC, whitenoise.
  - Apps `apps/candidates`, `apps/messaging`, `apps/dashboard`.
  - Models from CONTRACTS §5, migrations and admin.
- [x] **A2 Worker and pipeline.**
  - The `run_worker` command: claim with `skip_locked`, oldest-first per conversation, reply-to-latest suppression, a transactional persist, send after commit, and ticks via `next_tick_at`.
  - Use a stub engine with the contract's signatures until E5 lands, then switch.
- [x] **A3 Web chat.**
  - `/chat/` entry (country and language picker) and a mobile-style chat page.
  - HTMX send, plus a poll every 1.5 s.
- [x] **A4 WhatsApp.**
  - The Twilio webhook: signature validation, idempotency, media detection, phone → conversation routing.
  - `WhatsAppChannel.send`.
  - The `/apply/` form for agent-initiated conversations.
- [x] **A5 Recruiter dashboard.** Login required.
  - **Queue:** qualified and needs_review first.
  - **Filters:** status, country/city, availability, schedule. Search by name or phone.
  - **Detail page:** fields with flags and source message links, summary, full transcript, event timeline, final JSON.
  - **Actions:** approve / reject / needs review, each with a note.
  - **Export:** CSV.
- [x] **A9 App tests:**
  - Webhook signature and idempotency.
  - Worker ordering and reply-to-latest.
  - Reminder scheduling.
  - Overrides.
- [x] **A6 Analytics page:**
  - A funnel by stage and the outcome split.
  - Disqualify reasons, median time to complete, drop-off stage for abandoned conversations, and replies after a reminder.
  - LLM tokens and cost per conversation.
- [x] **A7 `seed_demo` command:** a recruiter user and around 30 conversations in varied states (reusing eval transcripts once V2 exists).
- [x] **A8 Docker:** a Dockerfile plus `docker-compose.yml` (web, worker, db). Hand deploy settings to the lead for L4.

## Evals (V): `evals/`
V1 can start on day 1 straight from the spec. V2 onward needs E1, E3 and E9.
- [x] **V1 Scenarios.** 15–20 YAML files with ground truth, covering:
  - Happy paths: ES Spanish, MX Spanish, English.
  - Conversation behavior: code-switching, everything in one message, corrections at confirm, a vague start date, FAQ questions mid-flow, emoji-only answers, a voice note.
  - Outcomes: no license, out of area (confirmed), an ambiguous city, an unclear (expired) license, prompt injection, abuse, silence then a late reply.
- [x] **V2 Simulator.**
  - A smart-tier LLM role-plays the persona against the engine in memory, within a max-turn limit.
  - It advances a fake clock and calls `handle_tick` for silence scenarios.
  - Saves transcripts.
- [x] **V3 Scorers:**
  - Field accuracy and outcome accuracy.
  - Knockout correctness and turns to complete.
  - Message-rule compliance: length, one question, language match, AI disclosure.
  - Cost and latency per conversation.
- [ ] **V4 Model comparison.**
  - Run the suite on 2–3 configurations (e.g. fast=haiku vs fast=sonnet for extract and compose).
  - Report to `evals/reports/model-comparison.md`; this feeds the LLM justification.
- [ ] **V5 Sample conversations.** 5–6 curated transcripts in `docs/sample-conversations/`:
  - ES happy path, EN, code-switch.
  - Disqualified, needs review, re-engagement.
- [x] **V6 Smoke suite:** `uv run python -m evals.run --suite smoke` (5 scenarios) for quick regression checks after prompt changes.

## Phase 2: vacancies, dynamic fields, preference scoring (CONTRACTS v4)

The original scope (CP1–CP3) is substantially done. This phase generalizes the engine from one
hardcoded role to a config-driven field catalog with required-vs-preferred fields and a ranking
score — see CONTRACTS §7 and DECISIONS D25 for the full design and reasoning before starting.
The 3-day framing is dropped (Vlad's call); the quality bar isn't.

- **CP4:** both `driver` and `kitchen_prep` vacancies run end to end via the CLI; a scenario
  where two otherwise-equal candidates differ only on a `preferred` field demonstrably ranks
  them in that order on the dashboard; full suite green; CONTRACTS v4 fully implemented, no lane
  still coding against v3 shapes.

### Engine (E10+): `screening/`
Order: E10 → E11 → E12 → E13 → E14 → E15. E10 unblocks app and evals, same as E1 did.
- [ ] **E10 Vacancy config.** `FieldSpec`/`VacancyConfig` (CONTRACTS §7) + the loader
  (`ScreeningConfig.vacancies`, `config.vacancy(id)`). Two vacancy files:
  `screening/config/vacancies/driver.yaml` (today's seven fields, migrated verbatim — same
  required/knockout behavior as now) and `kitchen_prep.yaml` (no `has_driver_license`
  requirement; `preferred, weight: 1.5` instead — the concrete case D25 is about). Also: move
  `evals/pricing.py` → `screening/llm/pricing.py` (app's request, CONTRACTS §3).
- [ ] **E11 Generalize schemas.** `CandidateProfile.fields: dict[str, FieldValue[Any]]`; `Stage`
  collapses to `CONSENT`/`COLLECTING`/`CONFIRM`/`DONE`; `ConversationState` gains `vacancy_id`,
  `current_field`, `preference_score`; `schema_version: 2`. Exactly as CONTRACTS §1.
- [ ] **E12 Generalize policy.** Replace the hardcoded `FIELDS` constant and the two special-cased
  knockout branches with the general rules in CONTRACTS §7: required fields first (vacancy
  order), then preferred; a knockout-shaped verdict only disqualifies when `requirement ==
  "required"`; a `preferred` field is asked once, never re-asked, never flagged, never
  disqualifies. **While this code is open: fix the read-back loop** evals found (`status/evals.md`
  — a no-op "correction" at CONFIRM loops the read-back with no cap). Write the new transition
  table as a docstring first, same discipline as the original E5.
- [ ] **E13 Generalize extraction and compose.** `understand.py`: build `Extraction`'s per-field
  sub-model dynamically per vacancy (`pydantic.create_model`, cached), not a fixed
  `ExtractedFields` class; update the extraction prompt so it doesn't assume the old seven
  fields. `compose.py`: `AskField` and the fixed per-field phrasing come from `FieldSpec.label`
  instead of a closed literal.
- [ ] **E14 Scoring and the final record.** `preference_score` computed per CONTRACTS §7's
  per-type formula; `record.final_record` emits the new `{"fields": {...}, "preference_score":
  ...}` shape (CONTRACTS §2).
- [ ] **E15 Rework the test suite.** The ~250 existing engine tests assumed the fixed field set;
  get them passing against `driver` (behavior should be unchanged — this is a refactor, not a
  product change, for that vacancy), then add tests specifically against `kitchen_prep` that
  prove a missing/false preferred field doesn't disqualify and does affect `preference_score`.

### App (A10+): Django
Order: A10 → A11 → A12. Needs E10, E11 at minimum; A11 needs E14.
- [ ] **A10 Vacancy on the conversation.** `Conversation.vacancy_id` + `preference_score` columns
  and migration (CONTRACTS §5). `/chat/` picker and `/apply/` gain a vacancy choice (a demo
  convenience — see CONTRACTS §5's note that one link per real job ad is the production shape);
  both pass `vacancy_id` through to `engine.new_conversation`.
- [ ] **A11 Dashboard for the new shape.** Queue sorts by `preference_score` within a status
  (CONTRACTS §5). Detail page shows each field's requirement level and, for preferred fields,
  its weight and whether it scored. CSV export and the analytics page updated for the new
  `final_record["fields"]` shape.
- [ ] **A12 Re-seed.** `seed_demo`'s fixture predates `schema_version: 2`; regenerate it from a
  fresh eval baseline run covering both vacancies (not a migration — this is demo data).

### Evals (V7+): `evals/`
V7 needs E10-E12 at least; V8 needs E14.
- [ ] **V7 Vacancy-aware scenarios.** Add `vacancy: driver` to the existing 20 scenarios
  (CONTRACTS §6) and reshape their `expected` blocks to `fields: {...}`. Add 3-4 new scenarios
  against `kitchen_prep`: a candidate with no license still qualifies; two otherwise-identical
  candidates differing only on a preferred field rank in the right order; a required field under
  the new generic code path still knocks out correctly (prove the refactor didn't quietly change
  `driver`'s behavior).
- [ ] **V8 Re-run and report.** V3 scoring and the V6 smoke suite against the rebuilt engine;
  note any regressions from the refactor in `status/evals.md`, separate from genuinely new
  findings about the vacancy system itself.
