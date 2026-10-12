# Status: lead

Last updated: 2026-10-12

## Current task
L2 continuous review loop, waiting on the next lane commit.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| L1 | uv project (Python 3.12), all deps from BOARD.md installed, ruff + pytest config in pyproject.toml, skeleton dirs (`screening/`, `tests/engine/`, `config/`, `apps/`, `templates/`, `static/`, `tests/app/`, `evals/`, `tests/evals/`, `docs/sample-conversations/`) with `__init__.py`, `.env.example`, `.gitignore` | `uv run ruff check .` passes; `uv sync` installs clean | e4c9ab9 |
| L2 (E1, A1) | Reviewed both commits; fixed the pytest/ruff config both of you hit independently (see Announcements). Ticked E1, A1 in BOARD.md. Approved all 8 of engine's open spec questions (see Review notes) and logged it as D13. | `uv run pytest tests/engine -q` (29 pass incl. your E3 WIP); `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app -q` (10 pass) | 5944914 |
| L2 (E3) | Reviewed `AnthropicClient`/`FakeLLM`. Approved the cache-token contract request: CONTRACTS §3 `LLMUsage` bumped to v2 with `cache_read_tokens`/`cache_write_tokens` (default 0). Ticked E3 in BOARD.md. Logged D14. | `uv run pytest tests/engine -q` (29 pass) | b9a8d62 |
| L2 (E2, E4, V1) | Reviewed validators, the Extraction schema/prompt, and the 20 eval scenarios. Ticked E2, E4, V1 in BOARD.md. | `uv run pytest tests/engine tests/evals -q` | (pending) |

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

**Engine (E3):** Clean, and the Anthropic-API reasoning in your prep notes checks out against what's in CONTRACTS now. `messages.parse` + `output_format`, low effort with the thinking headroom, the one retry on a `ValidationError`, mapping `refusal`/`max_tokens`/`APIError` to `LLMError` — all sound, and the system-block caching matches your own byte-stability note. `FakeLLM` scripting by purpose is exactly what E2/E4/E5 will need.

Your cache-token request: approved, CONTRACTS is now v2 (see Announcements). Please switch `_usage()` to fill `cache_read_tokens`/`cache_write_tokens` instead of folding them into `input_tokens`, and record both in the `llm_call` event payload per CONTRACTS' event catalogue.

**Engine (E2):** Clean. `match_city`'s exact-n-gram-then-fuzzy approach with a 3-option cap is a good call — matches CONTRACTS' `matched`/`ambiguous`/`not_served` kinds exactly and correctly leaves the "2 attempts → flagged" / `pending_confirmation` policy to E5. `Verdict[T]` using PEP 695 syntax is fine since it isn't a pydantic `BaseModel` (no UP046 conflict). Nothing to change; go ahead with E4.

**Engine (E4):** Clean. `Extraction`/`ExtractedFields` cover the intents and raw per-field shapes BOARD asked for, and splitting the static system prompt (rules, FAQ catalogue, few-shots) from the per-turn user message (context, local date, transcript tail) is the right shape for caching and keeps `understand.py` honest about what's deterministic vs. model-read. Nothing to change.

**Evals (V1):** Clean, and thorough — 20 scenarios covering every BOARD case plus a few extra (unresolved field, human request, opt-out, abandonment, sensitive details), with a validated schema that catches inconsistent ground truth. Your `tests/evals/__init__.py` fix (it was shadowing the top-level `evals` package under pytest's prepend import mode) was the right call and squarely inside your own paths — no lead action needed. Your notes to engine on the Zaragoza/San Pedro fuzzy-match edge cases and the FAQ assumption are exactly the kind of cross-lane flag that should go in Notes for other lanes; engine will pick those up.

## Announcements (contract changes, scope cuts, dependency additions)
- **Pytest config fixed** (both engine and app hit this independently): dropped the global `DJANGO_SETTINGS_MODULE` from `pyproject.toml`. `tests/engine` and `tests/evals` now run with zero Django involvement, as the architecture requires. App tests need the env var explicitly: `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (documented in CLAUDE.md Commands). Also added `pythonpath = ["."]` so plain `uv run pytest` can import `screening` without `-m`.
- **Ruff:** added `extend-exclude = ["**/migrations"]` globally, per app's request.
- **`.gitignore`:** added `media/`, per app's request.
- **CONTRACTS.md bumped to v2:** `LLMUsage` gained `cache_read_tokens`/`cache_write_tokens` (default 0, backward-compatible). D14.
- **Heads up, app lane:** I ran a verification `pytest tests/app` in the background while you were also running your own, and both stalled at the same point until I killed mine — looked like contention, not a hang in your code specifically. Worth a glance if `tests/app` ever stalls for you with nothing obviously wrong: check whether something else (another session, a leftover process) is running the same command at the same time.
