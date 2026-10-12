# Board

Owned by the lead; only the lead ticks boxes. Lanes report progress in `status/<lane>.md`.

## Checkpoints
- **CP1, end of day 1:**
  - `uv run python -m screening.cli` completes a full Spanish screening against the real LLM.
  - The web chat creates conversations end to end through the worker (stub or real engine).
  - The Django admin shows them.
- **CP2, end of day 2:**
  - A WhatsApp sandbox conversation runs end to end.
  - Reminders fire with time scaling.
  - The dashboard lists candidates with summaries and overrides.
  - The smoke evals run.
- **CP3, midday day 3: feature freeze.**
  - Evals report and model comparison done.
  - App deployed.
  - README complete.
  - The afternoon is for sample conversations, the demo video and presentation notes.

## Lead (L)
- [ ] **L1 Bootstrap. Must be done before any lane starts.**
  - uv project with Python 3.12 and these deps: `django`, `django-htmx`, `dj-database-url`, `psycopg[binary]`, `whitenoise`, `gunicorn`, `pydantic`, `pyyaml`, `anthropic`, `twilio`, `phonenumbers`, `dateparser`, `rapidfuzz`, `python-dotenv`. Dev deps: `pytest`, `pytest-django`, `time-machine`, `ruff`.
  - ruff and pytest config, with `DJANGO_SETTINGS_MODULE=config.settings` scoped to `tests/app`.
  - The skeleton directories from the repo map, with `__init__.py` files.
  - `.gitignore` and `.env.example` (`ANTHROPIC_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_SMART`, `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `PUBLIC_BASE_URL`, `DEMO_TIME_SCALE`).
  - Initial commit.
- [ ] **L2 Continuous review.** After each lane commit:
  - Review the diff for contract adherence, simplicity and tests.
  - Run the full suite.
  - Write findings in your status file under "Review notes for <lane>".
- [ ] **L3 Integration at CP1 and CP2:** verify each checkpoint end to end yourself, and report to Vlad.
- [ ] **L4 Deploy:**
  - Railway with web, worker and Postgres services, plus env vars.
  - Twilio sandbox webhook pointed at the deployed URL.
  - A smoke test on the deployed URL.
- [ ] **L5 README:**
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
- [ ] **E3 LLM layer:**
  - `LLMClient` protocol, `AnthropicClient` and `FakeLLM`.
  - Check the current Anthropic docs for structured outputs or forced tool use, and for prompt caching, before writing it.
  - Timeouts, retries and usage capture.
- [ ] **E2 Validators.** Pure functions with heavy unit tests:
  - **City matcher:** handles accents, case, aliases, neighborhoods and fuzzy matches. It returns `matched`, `ambiguous(options)` or `not_served(city_text)`. A `not_served` result sets `pending_confirmation` so the candidate confirms before disqualification. Unresolved after 2 attempts → flagged.
  - **License:** yes / no / unclear(note).
  - **Availability and schedule:** normalization to the enums.
  - **Experience:** months → years and platform aliases.
  - **Start date:** resolve against the message's local date and weekday (dateparser or the LLM), then validate in code: not in the past, at most `start_date_max_days` away, "ASAP" means today.
  - **Name:** a first name plus a surname, with a single soft re-ask.
- [ ] **E4 Understand.**
  - An `Extraction` schema: intent (`answer`, `question`, `correction`, `smalltalk`, `offtopic`, `opt_out`, `human_request`, `abuse`), language, raw values for any fields mentioned, and the question text.
  - The extraction prompt, with few-shot examples: multi-field messages, corrections, code-switching, Mexican vocabulary, emoji answers.
- [ ] **E6a Compose (basic):**
  - The Alex persona prompt and per-action instructions.
  - Language and country vocabulary.
  - The opening message and the closes.
- [ ] **E5 Policy and state machine.**
  - Write the transition table as a docstring first.
  - Covers: consent, slot filling in spec order, knockouts with confirmation, attempts and flags, the confirm step with corrections, outcomes, opt-out, human handoff, FAQ answers, media, off-topic strikes, and injection-proof outcomes.
  - Exhaustive tests with FakeLLM.
- [ ] **E9 CLI:** `uv run python -m screening.cli [--lang es|en] [--country ES|MX] [--fake] [--script file.txt]`. Prints each reply, the state diff and the events.
- [ ] **E7 Timers:** `handle_tick` covers the reminder schedule, quiet hours in the candidate's timezone, abandonment and `DEMO_TIME_SCALE`.
- [ ] **E8 Summary and final record:** the summary uses the smart tier; `record.final_record(state)` is deterministic.
- [ ] **E6b Compose polish:**
  - A length and one-question guard: regenerate once if violated, then trim safely.
  - Tone tuning from eval findings.

## App (A): Django
Order: A1 → A2 (stub engine) → A3 (CP1) → A4 → A5 → A9 (CP2) → A6 → A7 → A8.
- [x] **A1 Project setup.**
  - Django project `config/`: settings from env, `dj-database-url` (Postgres, or SQLite fallback), TZ=UTC, whitenoise.
  - Apps `apps/candidates`, `apps/messaging`, `apps/dashboard`.
  - Models from CONTRACTS §5, migrations and admin.
- [ ] **A2 Worker and pipeline.**
  - The `run_worker` command: claim with `skip_locked`, oldest-first per conversation, reply-to-latest suppression, a transactional persist, send after commit, and ticks via `next_tick_at`.
  - Use a stub engine with the contract's signatures until E5 lands, then switch.
- [ ] **A3 Web chat.**
  - `/chat/` entry (country and language picker) and a mobile-style chat page.
  - HTMX send, plus a poll every 1.5 s.
- [ ] **A4 WhatsApp.**
  - The Twilio webhook: signature validation, idempotency, media detection, phone → conversation routing.
  - `WhatsAppChannel.send`.
  - The `/apply/` form for agent-initiated conversations.
- [ ] **A5 Recruiter dashboard.** Login required.
  - **Queue:** qualified and needs_review first.
  - **Filters:** status, country/city, availability, schedule. Search by name or phone.
  - **Detail page:** fields with flags and source message links, summary, full transcript, event timeline, final JSON.
  - **Actions:** approve / reject / needs review, each with a note.
  - **Export:** CSV.
- [ ] **A9 App tests:**
  - Webhook signature and idempotency.
  - Worker ordering and reply-to-latest.
  - Reminder scheduling.
  - Overrides.
- [ ] **A6 Analytics page:**
  - A funnel by stage and the outcome split.
  - Disqualify reasons, median time to complete, drop-off stage for abandoned conversations, and replies after a reminder.
  - LLM tokens and cost per conversation.
- [ ] **A7 `seed_demo` command:** a recruiter user and around 30 conversations in varied states (reusing eval transcripts once V2 exists).
- [ ] **A8 Docker:** a Dockerfile plus `docker-compose.yml` (web, worker, db). Hand deploy settings to the lead for L4.

## Evals (V): `evals/`
V1 can start on day 1 straight from the spec. V2 onward needs E1, E3 and E9.
- [ ] **V1 Scenarios.** 15–20 YAML files with ground truth, covering:
  - Happy paths: ES Spanish, MX Spanish, English.
  - Conversation behavior: code-switching, everything in one message, corrections at confirm, a vague start date, FAQ questions mid-flow, emoji-only answers, a voice note.
  - Outcomes: no license, out of area (confirmed), an ambiguous city, an unclear (expired) license, prompt injection, abuse, silence then a late reply.
- [ ] **V2 Simulator.**
  - A smart-tier LLM role-plays the persona against the engine in memory, within a max-turn limit.
  - It advances a fake clock and calls `handle_tick` for silence scenarios.
  - Saves transcripts.
- [ ] **V3 Scorers:**
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
- [ ] **V6 Smoke suite:** `uv run python -m evals.run --suite smoke` (5 scenarios) for quick regression checks after prompt changes.
