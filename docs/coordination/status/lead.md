# Status: lead

Last updated: 2026-10-12

## Current task
L2 continuous review loop, waiting on the next lane commit.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| L1 | uv project (Python 3.12), all deps from BOARD.md installed, ruff + pytest config in pyproject.toml, skeleton dirs (`screening/`, `tests/engine/`, `config/`, `apps/`, `templates/`, `static/`, `tests/app/`, `evals/`, `tests/evals/`, `docs/sample-conversations/`) with `__init__.py`, `.env.example`, `.gitignore` | `uv run ruff check .` passes; `uv sync` installs clean | e4c9ab9 |
| L2 (E1, A1) | Reviewed both commits; fixed the pytest/ruff config both of you hit independently (see Announcements). Ticked E1, A1 in BOARD.md. Approved all 8 of engine's open spec questions (see Review notes) and logged it as D13. | `uv run pytest tests/engine -q` (29 pass incl. your E3 WIP); `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app -q` (10 pass) | (pending, see below) |

## Blocked
None

## Requests (to other lanes or the lead)
None

## Contract change requests
None

## Notes for other lanes
None

## Review notes for lanes

**Engine (E1):** Clean. `schemas.py` matches CONTRACTS §1 verbatim, the `noqa: UP046` call on `FieldValue` is the right move (contract syntax over the lint rule), config loader and sample YAML look right, tests are thorough (29 passing incl. your E3 WIP). Nothing to change.

Your 8 open spec questions: approved as proposed, all of them. Most are near-verbatim from `process-design.md` already (the no-surname rule especially), so I didn't see a reason to take these to Vlad — logged as D13 in DECISIONS.md. Go ahead and build E5 against them. If one turns out wrong against a real transcript, it's a small patch, not a contract change.

**App (A1):** Clean. Models match CONTRACTS §5, migrations are sane, admin inlines look useful for the dashboard work later. `tests/app/conftest.py`'s static-storage override is a reasonable call, no issue.

## Announcements (contract changes, scope cuts, dependency additions)
- **Pytest config fixed** (both engine and app hit this independently): dropped the global `DJANGO_SETTINGS_MODULE` from `pyproject.toml`. `tests/engine` and `tests/evals` now run with zero Django involvement, as the architecture requires. App tests need the env var explicitly: `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (documented in CLAUDE.md Commands). Also added `pythonpath = ["."]` so plain `uv run pytest` can import `screening` without `-m`.
- **Ruff:** added `extend-exclude = ["**/migrations"]` globally, per app's request.
- **`.gitignore`:** added `media/`, per app's request.
