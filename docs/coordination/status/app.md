# Status: app

Last updated: 2026-10-12

## Current task
**A2 next:** worker and pipeline, with a stub engine until E5 lands.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| A1 | Django project `config/` (settings from env, dj-database-url with a SQLite fallback, UTC, whitenoise, django-htmx). Apps `candidates`, `messaging`, `dashboard`. Models exactly as CONTRACTS §5, initial migrations, admin with message/event/review inlines on Conversation. | `cp .env.example .env && uv run python manage.py migrate && uv run pytest tests/app` | (this commit) |

## Blocked
None

## Requests (to other lanes or the lead)
- **lead:** `status/lead.md` lists the L1 commit as `2c3e4f1`, but the actual commit is `e4c9ab9`.
- **lead (L1):** `[tool.pytest.ini_options]` sets `DJANGO_SETTINGS_MODULE` globally. BOARD L1 says to scope it to `tests/app`. As it stands, `uv run pytest tests/engine` also loads Django settings. That works once `config/settings.py` exists, but it ties the engine tests to the app lane. One option: a `tests/app/conftest.py` (app lane) that sets it, with the global key removed.
- **lead:** `.gitignore` could also list `media/`. Low priority.
- **lead:** please add `extend-exclude = ["**/migrations"]` under `[tool.ruff]`. Django's generated migrations break E501 and ruff format doesn't wrap them. Until then I lint with `--extend-exclude '**/migrations'`.

## Contract change requests
None

## Notes for other lanes
- `config/settings.py` refuses to start when `DEBUG` is off and `DJANGO_SECRET_KEY` is unset. Local runs and the test suite need a `.env` (`cp .env.example .env`, which has `DEBUG=True`) or those env vars set. Because pytest loads `config.settings` globally, this also applies to `pytest tests/engine` and `tests/evals` until the lead scopes it.
- Model notes: `Message.kind` adds `inbound` beside the outbound kinds (`reply`, `reminder`, `close`). `Message` ordering is by primary key, which is the per-conversation arrival order the worker relies on. `Event.created_at` is copied from the engine event's `at`.
