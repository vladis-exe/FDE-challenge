# Status: lead

Last updated: 2026-10-14

## Current task
L2 continuous review loop. Wrote L5 (README). No lane has committed anything since 3a45a40 — all three sessions appear idle; Vlad is nudging them.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| L1 | uv project (Python 3.12), all deps from BOARD.md installed, ruff + pytest config in pyproject.toml, skeleton dirs (`screening/`, `tests/engine/`, `config/`, `apps/`, `templates/`, `static/`, `tests/app/`, `evals/`, `tests/evals/`, `docs/sample-conversations/`) with `__init__.py`, `.env.example`, `.gitignore` | `uv run ruff check .` passes; `uv sync` installs clean | e4c9ab9 |
| L2 (E1, A1) | Reviewed both commits; fixed the pytest/ruff config both of you hit independently (see Announcements). Ticked E1, A1 in BOARD.md. Approved all 8 of engine's open spec questions (see Review notes) and logged it as D13. | `uv run pytest tests/engine -q` (29 pass incl. your E3 WIP); `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app -q` (10 pass) | 5944914 |
| L2 (E3) | Reviewed `AnthropicClient`/`FakeLLM`. Approved the cache-token contract request: CONTRACTS §3 `LLMUsage` bumped to v2 with `cache_read_tokens`/`cache_write_tokens` (default 0). Ticked E3 in BOARD.md. Logged D14. | `uv run pytest tests/engine -q` (29 pass) | b9a8d62 |
| L2 (E2, E4, V1) | Reviewed validators, the Extraction schema/prompt, and the 20 eval scenarios. Ticked E2, E4, V1 in BOARD.md. | `uv run pytest tests/engine tests/evals -q` (109 pass) | 67ae027 |
| L2 (E6a, E5, E9, E7, E8, E6b, A2, A3) | Caught up on a full day of lane work. Ticked all of it in BOARD.md. CONTRACTS bumped to v3: added `next_due_at` to §2 and clarified the LLM-failure bookkeeping rule (both per engine's requests below). Logged D23. Verified CP1 end to end (BOARD.md). | `uv run pytest tests/engine tests/evals` (212 pass), `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (39 pass), `uv run ruff check .` (clean, nothing uncommitted anywhere) | 64095cf |
| L5 | `README.md`: overview, Mermaid architecture diagram, 5-command setup, how to run the CLI/web chat/tests (WhatsApp and the dashboard documented as not-yet-built, honestly), LLM choice + measured numbers from live probes, a curated top-6 from DECISIONS.md, a 10K/week and ATS-integration answer. Flagged as a first pass: the LLM-justification section needs real numbers once V4 (model comparison) lands. Also found, by manually testing CP1 myself: `apps/messaging/services.py` still imports the stub engine (`TODO(A2): screening.engine once E5 lands`, never actioned) — the web chat is mechanically correct but Alex's replies there are still placeholder text. CLI already uses the real engine. | Commands in the README run as written: `uv run python -m screening.cli --fake --script ...`, `uv run pytest tests/engine tests/evals` (212 pass), app tests (39 pass), `uv run ruff check .` clean | cd3a6f1 |

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

**App:** thanks for the correction on the `tests/app` stall — you're right, it was a real bug (`run_worker --once` retrying forever), not two processes colliding, and 8d45077 fixes it. I jumped to the wrong read on that; noted for next time to check your own WIP before theorizing about contention.

**Engine (E5 through E6b, all of it):** reviewed `policy.py`/`engine.py` against the transition table and CONTRACTS §2, `cli.py`, `timers.py`, `record.py`/`summary.py`, and `guard.py`. All clean, well-tested (212 pass incl. evals), and the live-probe numbers in your status entries are exactly the kind of evidence the presentation needs — keep writing them that way. Two things resolved, see Announcements: `next_due_at` is now in CONTRACTS §2, and the LLM-failure bookkeeping question is answered (your reading was right, the contract text was just underspecified — fixed, not changed).

**App (A2, A3):** clean. D15–D17 (lock held across the LLM call, IMMEDIATE+WAL on SQLite, errors consume the message rather than retry) are all sound calls for this scale and well-argued in DECISIONS.md. A3's web chat is still on the stub engine per CONTRACTS' explicit CP1 allowance ("stub or real engine") — go ahead and switch to the real one now that E5 is in; should be close to a drop-in given you built A2 against the exact CONTRACTS §2 signatures.

**App, repeating this since it's now a day old and un-actioned:** `apps/messaging/services.py` line 29 still has `from apps.messaging import stub_engine as engine  # TODO(A2): screening.engine once E5 lands`. E5 landed in c8052a5. This is the one thing stopping the web chat from being a real demo — please pick it up next.

## Announcements (contract changes, scope cuts, dependency additions)
- **Pytest config fixed** (both engine and app hit this independently): dropped the global `DJANGO_SETTINGS_MODULE` from `pyproject.toml`. `tests/engine` and `tests/evals` now run with zero Django involvement, as the architecture requires. App tests need the env var explicitly: `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (documented in CLAUDE.md Commands). Also added `pythonpath = ["."]` so plain `uv run pytest` can import `screening` without `-m`.
- **Ruff:** added `extend-exclude = ["**/migrations"]` globally, per app's request.
- **`.gitignore`:** added `media/`, per app's request.
- **CONTRACTS.md bumped to v2:** `LLMUsage` gained `cache_read_tokens`/`cache_write_tokens` (default 0, backward-compatible). D14.
- **CONTRACTS.md bumped to v3:** `next_due_at` added to §2 (engine's implementation, matching app's own proposal, is now the contract). The LLM-failure rule now says explicitly that `last_inbound_at`/`last_outbound_at`/`reminders_sent` update on a holding reply (engine's actual, correct behavior — the old wording was ambiguous, not wrong code). D23.
- Retracted: my "pytest tests/app contention" theory from the last round was wrong — app lane traced it to a real bug (`run_worker --once` not exiting on a repeated error) and fixed it in 8d45077.
