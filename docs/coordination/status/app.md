# Status: app

Last updated: 2026-10-14

## Current task
**A4 in progress:** WhatsApp webhook (signature, idempotency, media, phone routing), `WhatsAppChannel.send`, `/apply/`.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| A2b | Switched the worker to the real engine: `screening.engine` + `EngineContext(config, AnthropicClient())` (built lazily), `screening.record.final_record`, `engine.next_due_at` for `next_tick_at` (CONTRACTS v3). Deleted `stub_engine.py` and my local `next_tick_at`. Tests: an autouse `fake_llm` fixture replaces `engine_context`, so no test can build the real client. New `test_real_engine.py` runs the real engine with `FakeLLM` through the worker (knockout → close + final record; silence → first reminder via real timers). httpx request logs lowered to WARNING. | `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (37 pass). Live check (real LLM, worker): 3 turns at 2.2–4.0 s, 8 `llm_call`s, 0 errors. A "name" + "license" burst stored the stale license question as suppressed and sent only the reply to the latest message. | (this commit) |
| A3 | Web chat: `/chat/` job-ad picker (country + language), `/chat/<uuid>/` phone-style chat (light/dark, local-time bubbles, typing indicator). HTMX send (204 + `HX-Trigger` → immediate poll) and a 1.5 s self-replacing poller that appends only newer, non-suppressed messages. A chat is visible only to the browser session that started it. No build step: htmx is served from django-htmx's vendored copy. | `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (39 pass). Manual: `uv run python manage.py runserver 8000` + `uv run python manage.py run_worker`, open http://localhost:8000/chat/ | e61e327 |
| A2 | `apps/messaging/services.py` (pipeline; its docstring lists the 5 reliability rules), `channels.py` (Web no-op, WhatsApp placeholder until A4), `run_worker` command (`--once`, `--poll`, SIGTERM-safe), `stub_engine.py` (CONTRACTS §2 signatures, walks stages; delete at E5). SQLite: IMMEDIATE + WAL (D16). | `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (30 pass; each reliability rule has its own test in `test_worker.py`) | 8d45077 |
| A1 | Django project `config/` (settings from env, dj-database-url with a SQLite fallback, UTC, whitenoise, django-htmx). Apps `candidates`, `messaging`, `dashboard`. Models exactly as CONTRACTS §5, initial migrations, admin with message/event/review inlines on Conversation. | `cp .env.example .env && uv run python manage.py migrate && uv run pytest tests/app` | 049360c |

## Blocked
None

## Requests (to other lanes or the lead)
None

## Contract change requests
None (the `next_due_at` proposal landed as CONTRACTS v3, thanks).

## Notes for other lanes
- **lead, re the tests/app stall:** that was a real bug, not contention, and it's fixed in 8d45077. `tests/app` uses an in-memory SQLite DB per run, so two runs can't block each other. Your run and mine both hit my uncommitted WIP: `run_worker --once` kept retrying a repeated error instead of exiting. `--once` now re-raises; the long-running worker still logs and keeps going.
- `config/settings.py` refuses to start when `DEBUG` is off and `DJANGO_SECRET_KEY` is unset; use `cp .env.example .env` locally.
- **Engine:** the app calls `new_conversation`, `start`, `handle_message`, `handle_tick` and `final_record` exactly as CONTRACTS §2 says. It relies on `TurnResult.changed=False` meaning "nothing to persist", and on `InboundMessage.id` being the `Message` pk as a string. Between `new_conversation` and `start`, the app sets `state.country_hint` from the web-chat country picker. App-side event types: `worker_error`, and `recruiter_override` (A5).
- Model notes: `Message.kind` adds `inbound` beside the outbound kinds (`reply`, `reminder`, `close`). `Message` ordering is by primary key, which is the per-conversation arrival order the worker relies on. `Event.created_at` is copied from the engine event's `at`.
