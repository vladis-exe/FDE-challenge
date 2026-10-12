# Status: app

Last updated: 2026-10-12

## Current task
**A3 next:** web chat (`/chat/` picker + mobile-style chat page, HTMX send, 1.5 s poll).

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| A2 | `apps/messaging/services.py` (pipeline; its docstring lists the 5 reliability rules), `channels.py` (Web no-op, WhatsApp placeholder until A4), `run_worker` command (`--once`, `--poll`, SIGTERM-safe), `stub_engine.py` (CONTRACTS §2 signatures, walks stages; delete at E5). SQLite: IMMEDIATE + WAL (D16). | `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (30 pass; each reliability rule has its own test in `test_worker.py`) | (this commit) |
| A1 | Django project `config/` (settings from env, dj-database-url with a SQLite fallback, UTC, whitenoise, django-htmx). Apps `candidates`, `messaging`, `dashboard`. Models exactly as CONTRACTS §5, initial migrations, admin with message/event/review inlines on Conversation. | `cp .env.example .env && uv run python manage.py migrate && uv run pytest tests/app` | 049360c |

## Blocked
None

## Requests (to other lanes or the lead)
None

## Contract change requests
- **Engine owns "when is the next tick due" (proposal, not blocking).** The worker needs `next_tick_at` to know when to call `handle_tick`. Today `services.next_tick_at()` recomputes it from config (`last_inbound_at or last_outbound_at` + `reminder_schedule[reminders_sent]`, then `abandon_after`). That duplicates timing logic the engine owns in E7, and the two can drift. Proposal: add `screening.engine.next_due_at(state, *, config) -> datetime | None` to CONTRACTS §2, and the app calls it. Quiet hours can stay in `handle_tick`: an unchanged tick is retried after 1 min (scaled by `DEMO_TIME_SCALE`).

## Notes for other lanes
- `config/settings.py` refuses to start when `DEBUG` is off and `DJANGO_SECRET_KEY` is unset; use `cp .env.example .env` locally.
- **Engine:** the app calls `new_conversation`, `start`, `handle_message`, `handle_tick` and `final_record` exactly as CONTRACTS §2 says. It relies on `TurnResult.changed=False` meaning "nothing to persist", and on `InboundMessage.id` being the `Message` pk as a string. After `start`, the app may set `state.country_hint` from the web-chat country picker. App-side event types: `worker_error`, and `recruiter_override` (A5).
- Model notes: `Message.kind` adds `inbound` beside the outbound kinds (`reply`, `reminder`, `close`). `Message` ordering is by primary key, which is the per-conversation arrival order the worker relies on. `Event.created_at` is copied from the engine event's `at`.
