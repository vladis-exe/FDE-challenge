# Grupo Sazón Screening Agent

Take-home for Orbio's Forward Deployed Engineer role. An AI agent screens delivery-driver applicants for Grupo Sazón (fictional: 45 locations in Spain and Mexico, about 1,000 applications a week) over WhatsApp and web chat. Recruiters work from a dashboard of pre-screened candidates.

Time budget: 3 working days. Grading weights: technical build 40%, process design 25%, live presentation 25%, bonus 10%. Vlad must explain every line in a live session, so clarity beats cleverness.

## Read first
- `docs/process-design.md` is the product spec. Behavior questions are answered there; if not, ask Vlad through the lead.
- `docs/coordination/CONTRACTS.md` defines the interfaces between lanes. Code against these.
- `docs/coordination/BOARD.md` lists tasks, owners, order and checkpoints.

## Architecture
Functional core, imperative shell.
- `screening/` is a pure-Python engine with no Django and no I/O except the LLM client passed in. It takes the conversation state plus one inbound message and returns the new state, the outbound messages and the events.
- **Code owns the process:** the state machine, validation and outcomes. **The LLM owns the language:** understanding messy answers, writing replies and summaries.
- Django is the shell: persistence, channels (web chat, Twilio WhatsApp), the worker that processes messages and reminders, and the recruiter dashboard.
- `evals/` drives the engine with simulated candidates and scores it.

## Stack
- Python 3.12 and uv.
- Django (current stable) with templates and HTMX.
- Pydantic v2 for engine schemas, and the Anthropic SDK.
- Postgres in Docker/deploy, SQLite for tests and quick local runs.
- Twilio WhatsApp sandbox.
- pytest, pytest-django, time-machine, ruff.

No LangChain, LangGraph or CrewAI: the orchestration is a few hundred lines we own and can explain.

## Repo map and ownership
| Path | Owner |
| --- | --- |
| `screening/`, `tests/engine/` | engine lane |
| `manage.py`, `config/`, `apps/`, `templates/`, `static/`, `tests/app/`, `Dockerfile`, `docker-compose.yml` | app lane |
| `evals/`, `tests/evals/`, `docs/sample-conversations/` | evals lane |
| `CLAUDE.md`, `README.md`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore`, the rest of `docs/` | lead |
| `docs/coordination/status/<lane>.md` | that lane only |

Never edit a file you don't own. If you need a change elsewhere, write a request in your status file naming the owner; the lead routes it.

## Coordination protocol
All sessions run in parallel in the same working tree and talk only through `docs/coordination/`.
1. **Before each task:** re-read `BOARD.md`, `CONTRACTS.md` and the other lanes' status files.
2. **Start:** mark the task in progress in your own status file. Only the lead edits `BOARD.md`.
3. **Finish:** tests pass and ruff is clean on your paths. Then update your status file (what changed, how to verify, commit hash) and commit.
4. **Blocked:** write it under "Blocked" in your status file and switch to the next unblocked task. Never wait idle, and never silently work around a contract.
5. **Contract changes:** propose them under "Contract change requests". The lead edits `CONTRACTS.md` and logs the change in `DECISIONS.md`.
6. **Decisions:** for any trade-off worth defending in the presentation, append an entry to `docs/coordination/DECISIONS.md`, prefixed with your lane.
7. **Ending a session:** update your status file before you stop, so the next session or the lead can pick up from it.

## Git rules (shared working tree)
- Stay on `main`. Never run `checkout`, `switch`, `stash`, `reset`, `rebase`, `git add -A` or `git add .`.
- Commit only your own paths: `git add <your paths> && git commit -m "[E2] city matcher with aliases"`, prefixed with the task ID.
- If `.git/index.lock` exists, wait a few seconds and retry. Never delete it.
- Keep commits small, one task or sub-step each. The history is part of what gets evaluated.

## Commands
- Only the lead edits `pyproject.toml` and `uv.lock`. Need a package? Request it in your status file.
- Tests: `uv run pytest tests/engine` and `uv run pytest tests/evals` run with no Django at all. App tests need settings: `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (or `cp .env.example .env` once, which `config/settings.py` also needs for `DJANGO_SECRET_KEY`/`DEBUG`). Lint and format only your own paths: `uv run ruff check <paths>` and `uv run ruff format <paths>`.
- Dev server (app lane): `uv run python manage.py runserver 8000`.
- Worker (app lane): `uv run python manage.py run_worker`.
- Engine CLI: `uv run python -m screening.cli`.
- Tests never call the real LLM or Twilio. Use `FakeLLM` and the fake channel. Live LLM calls happen only in evals and manual runs.

## Engineering standards
- **Types:** type hints everywhere. Pydantic models at every boundary; no loose dicts crossing modules.
- **Decisions:** deterministic, in code. The LLM never decides eligibility, outcome or the next stage.
- **LLM calls:** every call has a timeout, retries with backoff and schema validation, and records an `llm_call` event (model, tokens, latency, purpose).
- **Time:** aware datetimes only, UTC in storage. Candidate-local time uses `Europe/Madrid` or `America/Mexico_City`.
- **Secrets:** from env only (see `.env.example`). Never log secrets or full phone numbers.
- **Style:** comments explain why, not what. Small modules, no speculative abstractions, no dead code.
- **Definition of done:** code, tests, ruff clean, status updated, committed.

## Product rules the code must honor (from the spec)

*Phase 2 (CONTRACTS v4, DECISIONS D25) generalized the fixed field list into per-vacancy config —
see CONTRACTS §7 and `docs/process-design.md`'s "Vacancies and preference scoring" before touching
`screening/policy.py` or `schemas.py`. The rules below describe the `driver` vacancy specifically;
they're still accurate for it, just no longer the only possible configuration.*

- **Persona:** the agent is "Alex" and discloses being an AI in the opening message.
  - Spanish uses *tú*, with vocabulary per country. Spain: carnet de conducir, coche, móvil. Mexico: licencia de manejo, carro, celular.
  - Alex replies in the language of the candidate's latest message.
- **Message limits:** about 300 characters, at most 2 sentences, one question, plain text, at most one emoji. Only the opening message may exceed these.
- **Knockouts (for the `driver` vacancy; a vacancy's own `FieldSpec.requirement` now decides this per field, CONTRACTS §7):**
  - License = no → disqualified (`no_license`).
  - City not served, confirmed by the candidate → disqualified (`out_of_area`), with a waitlist offer.
  - Unclear license, a field unresolved after 2 re-asks, a human requested, or abuse → `needs_review`.
- **Re-asks:** at most 2 per field, then flag the field and move on. Never loop. (A `preferred` field is the one exception: asked once, never re-asked — see CONTRACTS §7.)
- **Message ordering:** inbound messages are processed one at a time, in order. If a newer inbound arrived while one was being processed, keep its state update but drop its reply. Only the latest message gets answered.
- **Reminders:** at 15 min, 2 h and 20 h after the candidate's last message. Abandoned at 24 h. Nothing is sent between 21:00 and 09:00 local time; due reminders are deferred. All timings come from config, and `DEMO_TIME_SCALE` compresses them for demos.
- **FAQ:** answers come only from `screening/config/faq.yaml`. Otherwise Alex says a recruiter will confirm. Never invent pay or contract terms.
- **Sensitive details:** anything volunteered (health, immigration status, etc.) is never written into the candidate record.
- **Start date:** stored as an ISO date plus the ID of the source message, resolved against that message's timestamp in the candidate's time zone.
