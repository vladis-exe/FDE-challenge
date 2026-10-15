# Status: lead

Last updated: 2026-10-15

## Current task
**Demo readiness round (CP5, BOARD.md):** E18 and V9 done; A13 (app) and E19 (engine) running, then V10 (evals).
Instructions in "Notes for other lanes" below. L4 (Railway deploy) still waits on Vlad's account.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| L1 | uv project (Python 3.12), all deps from BOARD.md installed, ruff + pytest config in pyproject.toml, skeleton dirs (`screening/`, `tests/engine/`, `config/`, `apps/`, `templates/`, `static/`, `tests/app/`, `evals/`, `tests/evals/`, `docs/sample-conversations/`) with `__init__.py`, `.env.example`, `.gitignore` | `uv run ruff check .` passes; `uv sync` installs clean | e4c9ab9 |
| L2 (E1, A1) | Reviewed both commits; fixed the pytest/ruff config both of you hit independently (see Announcements). Ticked E1, A1 in BOARD.md. Approved all 8 of engine's open spec questions (see Review notes) and logged it as D13. | `uv run pytest tests/engine -q` (29 pass incl. your E3 WIP); `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app -q` (10 pass) | 5944914 |
| L2 (E3) | Reviewed `AnthropicClient`/`FakeLLM`. Approved the cache-token contract request: CONTRACTS §3 `LLMUsage` bumped to v2 with `cache_read_tokens`/`cache_write_tokens` (default 0). Ticked E3 in BOARD.md. Logged D14. | `uv run pytest tests/engine -q` (29 pass) | b9a8d62 |
| L2 (E2, E4, V1) | Reviewed validators, the Extraction schema/prompt, and the 20 eval scenarios. Ticked E2, E4, V1 in BOARD.md. | `uv run pytest tests/engine tests/evals -q` (109 pass) | 67ae027 |
| L2 (E6a, E5, E9, E7, E8, E6b, A2, A3) | Caught up on a full day of lane work. Ticked all of it in BOARD.md. CONTRACTS bumped to v3: added `next_due_at` to §2 and clarified the LLM-failure bookkeeping rule (both per engine's requests below). Logged D23. Verified CP1 end to end (BOARD.md). | `uv run pytest tests/engine tests/evals` (212 pass), `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (39 pass), `uv run ruff check .` (clean, nothing uncommitted anywhere) | 64095cf |
| L5 | `README.md`: overview, Mermaid architecture diagram, 5-command setup, how to run the CLI/web chat/tests (WhatsApp and the dashboard documented as not-yet-built, honestly), LLM choice + measured numbers from live probes, a curated top-6 from DECISIONS.md, a 10K/week and ATS-integration answer. Flagged as a first pass: the LLM-justification section needs real numbers once V4 (model comparison) lands. Also found, by manually testing CP1 myself: `apps/messaging/services.py` still imports the stub engine (`TODO(A2): screening.engine once E5 lands`, never actioned) — the web chat is mechanically correct but Alex's replies there are still placeholder text. CLI already uses the real engine. | Commands in the README run as written: `uv run python -m screening.cli --fake --script ...`, `uv run pytest tests/engine tests/evals` (212 pass), app tests (39 pass), `uv run ruff check .` clean | cd3a6f1 |
| Docs | `docs/code-tour.md`: traced one message through every real function it touches (`handle_message` → `extract` → `policy.decide` → `compose_reply`/guard → `_persist_turn`), with exact line references, verified against the actual code (not from memory). Separate from the README — this one's for Vlad to defend any line of it live, not for a stranger skimming the repo. | Spot-checked several claims against source directly (e.g. `policy.py:510`, `:475`) | 16fe455 |
| L2 (A4–A9, V2–V6 catch-up) | A huge amount landed while I wasn't looking: engine's `TODO(A2)` swap, A4–A9, V2–V6 — effectively the entire original scope. Ticked all of it in BOARD.md (including L1 and L3, which I'd apparently never ticked despite doing them). Declared CP2 done (WhatsApp code is tested but the live sandbox run still needs Vlad's Twilio creds — noted honestly, not glossed over). Added `DEMO_RECRUITER_PASSWORD` to `.env.example` per app's request. | Full suite: `uv run pytest tests/engine tests/evals` (233 pass), `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (96 pass, 2 skipped — Postgres-only locking test), `uv run ruff check .` clean | edc60d8 |
| L (Phase 2 routing) | Vlad dropped the 3-day framing and asked for a vacancy-driven field system with a non-knockout preference score (his example: a driver's license as a tiebreaker for a role that doesn't require one). Wrote it up as CONTRACTS v4 (new §7: field-type catalog, `VacancyConfig`/`FieldSpec`, required-then-preferred ordering, the "knockout only when required" rule, the scoring formula) and DECISIONS D25. Added a Phase 2 section to BOARD.md: E10-E15, A10-A12, V7-V8, plus CP4. Updated `process-design.md` (new "Vacancies and preference scoring" section, in product language) and `CLAUDE.md` (pointers so the old fixed-field language isn't read as still-current). Folded in two things that were sitting in your status files: app's `pricing.py` relocation request (now E10) and evals' read-back-loop bug (now explicitly part of E12, since that code's being rewritten anyway). | Nothing to test yet — this is the design, not the implementation. Read CONTRACTS §7 and BOARD's Phase 2 section before starting E10/A10/V7. | edc60d8 |
| L2 (E10-E15, V4, V5) | Engine did the whole of Phase 2 in one sustained push. Reviewed `screening/config/vacancy.py`, the field-type catalog (`fields.py`/`scoring.py`), the v4 `policy.py`/`engine.py` switchover, the per-vacancy extraction schema, and the read-back-loop fix — all clean, see Review notes. Ticked E10-E15, V4 (provisional, see BOARD), V5 in BOARD.md. CONTRACTS bumped to v4.1: added the 4 `FieldSpec` keys engine requested and Vlad already approved directly (`reason`, `summary`, `option_labels`, `exclusive_options`) — the contract doc just hadn't caught up to what's actually built. Logged D30. Fixed a real bug: engine and evals both filed a decision as "D26" the same day without seeing each other's — renumbered engine's two to D28/D29, content unchanged. | `uv run pytest tests/engine` (249 pass). `tests/evals` and `tests/app` are both red right now — expected, not a regression: evals needs V7 (scenarios still v3-shaped) and app needs A10's remainder/A11 (e.g. `apps/dashboard/analytics.py` still references the old per-field `Stage` values). Both lanes already know and have it queued. | 9ece4dd |
| L2 (E16/E16b/E17, A10-A12, V7/V8) — CP4 | Phase 2's live-verification round, all three lanes. Reviewed `screening/README.md` (engine's own guide — genuinely good, kept code-tour.md but flagged it pre-Phase-2 rather than duplicating this), the city-matcher fixes (D32), the code-not-prompt fixes (D33, surname-join, read-back detail, localized option labels, job title in the summary), app's vacancy picker/dashboard/re-seed (A10-A12), and evals' 24-scenario live run on the generalized engine (V8: 20/24, 96%/100%/96%/100%/100%, $0.0062/conv). Ticked A10-A12, V7, V8 in BOARD.md and declared **CP4** with real evidence: the D25 tie-break (2.5 vs. 1.0) is on the actual seeded dashboard, not just a unit test. Rewrote README.md substantially for all of this (real V4/V8 numbers, WhatsApp/dashboard documented as built, Twilio credential-type note carried forward). | Full suite: `uv run pytest tests/engine tests/evals` (312 pass), `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (108 pass, 2 skipped), `uv run ruff check .` clean. Spot-checked `screening/README.md`'s claims and the V8/A11 cost figures against the actual report files, not just the status write-ups. | 7894681 |
| L (WhatsApp sandbox, closed) | Vlad sent the real Twilio Account SID + Auth Token. Set up a local tunnel myself (Cloudflare's quick tunnel, no account needed, since `ngrok` now requires signup), restarted the server with the right `ALLOWED_HOSTS`/`PUBLIC_BASE_URL`, confirmed the webhook rejects an unsigned request. Vlad joined the sandbox and tested live, got Twilio's generic fallback reply every time — including to the join code itself. Diagnosed directly via Twilio's API (`client.messages.list()`, `client.messaging.v1.services.list()`, `client.incoming_phone_numbers.list()`) rather than guessing further: no Messaging Service or owned number is intercepting it, and the sandbox's own webhook field redirects to an upgrade page on Vlad's free-tier account. **Closed as D35**, not a repo bug. Tore down my test server/worker/tunnel afterward (see Announcements). | Diagnosis is in the Twilio API responses themselves, not inference — see D35 for the exact resources checked. | 4d18173 |
| L5, L6, L7 | README closed out (no more "needs Vlad's Twilio creds" — that's resolved, D35 is the actual status now). Wrote `docs/presentation-notes.md` (L6: a 6-step ~15 min demo script, a demo-day checklist, talking points organized by likely question, the 10K/week answer, "what I'd do with more time" tied to specific repo artifacts, not a wishlist) and the two L7 bonus docs: `docs/deployment.md` (consolidates my own scattered Railway notes from earlier status entries into one sequence, including the D35 caveat for the production webhook) and `docs/ats-integration.md` (a sketch against `final_record()` and the Twilio webhook's own signature pattern, reversed). Ticked L6, L7 in BOARD.md. **The original board is done except the actual Railway deploy (L4) — that needs Vlad's own Railway account, not something I can do from here.** | `uv run pytest tests/engine tests/evals` (312 pass), `uv run ruff check .` clean | 8b233da |

## Blocked
None still open from the lanes. (The live WhatsApp sandbox check is **closed, not blocked** — see Done below and D35: it's a Twilio free-tier restriction, confirmed via their own API, not something in this repo to fix.)

## Unblocked, 2026-10-15
- **Anthropic credits are back** (Vlad topped up 5 EUR). Confirmed live with the single cheapest possible call (a 21-input/4-output-token Haiku ping) — didn't spend more than that myself; the real verification runs belong to engine and evals, not me. **Budget is still tight, spend deliberately** (see Announcements: `LLM_MODEL_SMART` stays on Haiku for now). Engine: your Phase 2 live check and the two bug-fix re-verifications are unblocked. Evals: V4 repeats / V8 are unblocked too, but run the smoke suite first and check actual spend before a full 20-scenario repeat.

## Requests (to other lanes or the lead)
None

## Contract change requests
None

## Notes for other lanes
**Demo readiness round (BOARD.md "Demo readiness", CP5).** E18 and V9 done and approved.
**Top-up spend so far: about $0.84 of 5 EUR.**
- **App → A13, start now.** V9's run id is `20261015-070127-v9-final`. (1) `uv run python
  manage.py seed_demo --reset --from-run 20261015-070127-v9-final`; confirm the kitchen summaries
  no longer say "(kitchen_prep)" and the D25 tie-break still shows on the queue; (2) open every
  dashboard page (queue, filters, detail, analytics, CSV export); (3) one manual web-chat
  screening in a real browser with `runserver` + `run_worker` and the live LLM (cents), through to
  its dashboard detail page. Write what you saw, and anything off, in `status/app.md`. Commit as
  `[A13]`. Don't wait for E19: the fixture is a recording, and E19 doesn't change its records.
- **Engine:** nothing open (E19 final at `8b16b86`).
- **Evals → V10, start now (E19 is `5bd51ef`).** First fix the failing harness test (Review
  notes, E19 (b)). Scenario 16 ×3 and 04 ×2 live, then regenerate sample 03
  and update its notes. Budget ≤ $0.10. Commit as `[V10]`.

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

**Everything since (A4-A9, V2-V6, the engine swap):** reviewed by running the full suite rather than line-by-line on every commit (there were a lot, all at once) — 233 engine/evals tests and 96 app tests, all green, ruff clean. Nothing jumped out as wrong going through the status-file write-ups, which are genuinely good (the A9 Postgres-locking mutation test, the A7 fixture note on choosing 20 real transcripts over synthetic ones, V3's baseline numbers). Two things acted on: `DEMO_RECRUITER_PASSWORD` added to `.env.example` (app's request), and the `pricing.py` move + read-back-loop fix both folded into Phase 2 below rather than done as one-off patches, since the code they touch is being rewritten anyway.

**On the Docker/container note (app's "heads-up"):** not touched — not blocking anything right now, and I'd rather not run `sudo docker rm -f` on this machine without asking first. Vlad, that's yours whenever it's convenient: `sudo docker rm -f sazon-pg-test` frees port 55432.

**Engine (E10-E15, the whole of Phase 2):** genuinely impressive turnaround. Spot-checked `screening/config/vacancy.py`, `scoring.py`, and `kitchen_prep.yaml` directly rather than just the status write-up — the scoring formula matches CONTRACTS §7 exactly (boolean: weight-if-true, enum_multi: weight-if-any-match, experience: weight×capped-years), `FieldSpec`'s validators are tighter than what I'd specified (catching `weight` on a non-preferred field, `exclusive_options` not being a subset of `options` — both good calls I hadn't thought to require), and `kitchen_prep.yaml`'s es_ES/es_MX split on `option_labels`/`summary` shows the new config surface is actually usable, not just theoretically general. The four `FieldSpec` additions are now in CONTRACTS v4.1 (D30) — sorry that sat un-written-up for a bit; good call taking it straight to Vlad rather than waiting on me, since it was additive and clearly scoped.

One thing to pick up **once credits are back, before the live verification**: evals' V4 live run surfaced real findings that predate your Phase 2 work and are still open (check `status/evals.md` Notes — I won't duplicate the detail here): "I'd rather not say" sometimes misread as a full opt-out (loses the candidate with no review, 1 of 2 runs), a surname answer fully replacing the first name on Sonnet's fast tier, "de NL" (a Mexican state abbreviation) read as a location answer, and flag notes dropping the candidate's own detail (e.g. a renewal date). None of these need a live call to *fix* — they're prompt/extraction-logic changes — only to *re-verify*. Worth doing alongside the Phase 2 live check rather than a separate round.

**Evals (V4, V5):** the provisional framing on V4 is exactly right — a real decision backed by real (if thin) evidence, clearly labeled as needing more repeats rather than dressed up as final. V5's choice to leave the two engine stumbles ("de NL", the lost renewal date) visible in the curated samples rather than cherry-picking clean ones is the right call for a live presentation — it shows you understand the system's actual failure modes, not just its happy path.

## Review notes, 2026-10-15 (after the restart)
- **E17 `dae92ef` (score always a float):** correct and minimal, with a test. Approved.
- **E17 `7fbfb4b` (`screening/WALKTHROUGH.md`):** spot-checked 12 `file:line` references against
  the current code; all point at the line described. Approved. `docs/code-tour.md` now points to it.
- **V8 re-check `81a2b94`:** 04/13/18 at 6/6 live, $0.048. Approved. The only open finding left
  in `status/evals.md` is "Genial, Simón." → E18.
- **E18 `b318b8b`: sent back.** `first_name` only from an accepted `full_name` and the plan's
  "unknown" wording are approved. The guard's vocative regex flags cities and platforms
  ("Perfecto, Madrid es…", "Genial, Glovo…", "Entendido, Monterrey.") → an extra retry, and a
  garbled trim if the retry repeats it. Engine asked to tighten it (clause-ending word only, skip
  known city/platform names) with those cases as tests. V9 held until then.
- **E18 `7cbb9fb`: approved.** Lookahead is clause-ending only, and `guard.not_names(config)`
  skips places, platforms and Alex. Re-probed: "Simón."/"Pedro," still caught; Madrid, Glovo,
  Barcelona, Monterrey not. 326 engine+evals, 108 app (2 skipped), ruff check + format clean.
- **V9 `9f6b767`: approved.** 23/24 (V8 was 20/24: 04, 13, 18, 19 now pass), fields 100%,
  rules/language 100%, $0.0065/conv, p50 2.3 s, total spend $0.36 of $0.60. The one fail (16) is a
  real engine bug, not noise: routed as E19 with the other two findings. Samples regenerated with
  the Sonnet candidate (the Haiku one leaks meta text): fine, same choice as V5.
- **E19 `5bd51ef`: approved.** Probed `relative_day` (morning uses of "mañana" correctly skipped;
  "hoy no, mañana sí" → None) and the platform matcher ("uber eats en houston" → uber_eats); the
  MX FAQ variant is in. Two follow-ups, neither blocking: (a) **engine:** "mañana o pasado" returns
  1, not None as your message and the docstring say. Tomorrow is a fine reading (the earliest
  day offered), so either keep it and fix the docstring/test, or make it None. Pick one so the
  code and the description agree. (b) **evals:** `tests/evals/test_harness.py::
  test_compare_flags_failures_across_repeats` now fails. It used fake-mode scenario 16 as its
  "known fail", and that failure was the bug E19 fixed. Give it a failure that doesn't depend on an
  engine bug (e.g. a fixture scenario with a deliberately wrong `expected`). Engine: run
  `tests/evals` too before committing a behavior change.
- **E19 follow-up `404b95c`: sent back.** "Several relative days → the earliest" breaks
  negations: "hoy no, mañana sí" → 0, "mañana no, pasado mañana" → 1, so `near_date` would
  overwrite the model's correct reading with the day the candidate refused. Rule now: exactly one
  relative day → code decides; two or more → None, the model's reading stands. My "pick one" note
  was too loose; only the None option was safe.
- **E19 revert `8b16b86`: approved.** Re-probed: the four negations and "mañana o pasado mañana" →
  None; "mañana mismo", "mañana o pasado", "mañana por la mañana" → 1. Engine-level test pins the
  refused-day case. 352 engine+evals pass, ruff clean. Engine lane: nothing open.
- Full suite: 313 engine+evals, 108 app (2 skipped), ruff check clean. `ruff format` flagged
  Python blocks in two lead docs (`code-tour.md`, `CONTRACTS.md`); formatted, now clean tree-wide.

## Phase 2: vacancies, dynamic fields, preference scoring (CONTRACTS v4, D25)

Vlad's call: drop the 3-day framing, keep the quality bar, and generalize past Grupo Sazón's one
hardcoded driver role. His concrete example: a driver's license should disqualify for a driving
role but merely be a tiebreaker — never a disqualifier — for a role that doesn't need one.

**Read before starting anything in Phase 2:** CONTRACTS §7 (the full technical spec — field-type
catalog, `VacancyConfig`, the required-then-preferred ordering rule, the "knockout only when
required" rule, the scoring formula) and `process-design.md`'s new "Vacancies and preference
scoring" section (the same thing in product language). BOARD.md's Phase 2 section has the task
breakdown: **E10 unblocks app and evals, same as E1 did at the start** — nothing else in Phase 2
can start before it lands.

Two things from your own status files are folded into this rather than done separately: app's
`evals/pricing.py` → `screening/llm/pricing.py` relocation request (now part of E10), and evals'
read-back-loop finding (now explicitly called out inside E12, since `policy.py`'s CONFIRM handling
is being rewritten for the generic field list anyway — fix it while that code is already open).

This is a real rework, not a small addition — it touches `schemas.py`, `policy.py`,
`understand.py`, `compose.py`, the app's `Conversation` model, and every eval scenario's
`expected` block. Full reasoning in D25. Ask me if anything in CONTRACTS §7 is ambiguous before
guessing — this is exactly the kind of cross-cutting change where three lanes guessing
differently costs more time than one question would.

**Engine (E16/E16b/E17, the live-verification round):** this was the right way to spend a tight
budget — targeted probes per fix (D34) rather than full reruns, and D32/D33's framing (fix in
code when code can know the answer; the city matcher must never disqualify by misreading) are
exactly the kind of principle that's worth stating once and applying repeatedly, which is what
happened. `screening/README.md` is a genuinely good engine guide — clear module map, the
field-type table, "how to add a job" as a numbered checklist. Nothing to change.

**App (A10-A12):** clean, and the live check methodology (a scratch SQLite DB so dev data
wasn't touched, real worker + real LLM, $0.0039 for two full screenings) is a good pattern to
reuse. The "1.50" → "1.5" fix is the kind of thing that only shows up in a real run, not a unit
test — good catch. A12's refusal to seed a `schema_version` mismatch without being told to
regenerate (rather than silently seeding something the dashboard can't read) is the right
failure mode.

**Evals (V7, V8, V5 refresh):** V7's `load_scenario` recomputing the expected preference score
from the CONTRACTS §7 formula independently, rather than trusting whatever the engine happens to
output, is exactly the kind of ground-truth discipline that makes V8's results trustworthy. V8
leaving two real findings genuinely open (not silently re-run until clean) is the right call —
see below, these need one more cheap pass once you're back.

**Evals, two small follow-ups when you're next on this** (both already fixed in E16/E17 per
engine's notes, just not yet re-verified in context — cheap, 3 scenarios, not a full run):
1. Scenario 04: "simón, empecemos" was read as a name answer in 1 of 3 runs, which may be a
   regression from the generic extraction prompt. Engine added a few-shot for "simón"/"sale"/
   "órale" as consent, not a name.
2. Scenarios 13 and 18: the read-back-detail and FAQ-repetition fixes (E17) should resolve what
   V8 found, per engine's own notes. Worth a `uv run python -m evals.run --only 04 13 18` (a few
   cents) before trusting it closed.

## Announcements (contract changes, scope cuts, dependency additions)
- **2026-10-15, after the restart: `LLM_MODEL_SMART` is back on `claude-sonnet-5-5`** in the
  shared `.env`, ending the temporary Haiku override (D12/D26 stand). Smart is used only for
  summaries, so the cost difference per run is small. New round: BOARD.md "Demo readiness".
- **Pytest config fixed** (both engine and app hit this independently): dropped the global `DJANGO_SETTINGS_MODULE` from `pyproject.toml`. `tests/engine` and `tests/evals` now run with zero Django involvement, as the architecture requires. App tests need the env var explicitly: `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` (documented in CLAUDE.md Commands). Also added `pythonpath = ["."]` so plain `uv run pytest` can import `screening` without `-m`.
- **Ruff:** added `extend-exclude = ["**/migrations"]` globally, per app's request.
- **`.gitignore`:** added `media/`, per app's request.
- **CONTRACTS.md bumped to v2:** `LLMUsage` gained `cache_read_tokens`/`cache_write_tokens` (default 0, backward-compatible). D14.
- **CONTRACTS.md bumped to v3:** `next_due_at` added to §2 (engine's implementation, matching app's own proposal, is now the contract). The LLM-failure rule now says explicitly that `last_inbound_at`/`last_outbound_at`/`reminders_sent` update on a holding reply (engine's actual, correct behavior — the old wording was ambiguous, not wrong code). D23.
- Retracted: my "pytest tests/app contention" theory from the last round was wrong — app lane traced it to a real bug (`run_worker --once` not exiting on a repeated error) and fixed it in 8d45077.
- **`.env.example`:** added `DEMO_RECRUITER_PASSWORD=`, per app's request.
- **CONTRACTS.md bumped to v4 (new §7):** vacancies, dynamic fields, preference scoring. D25. This is the big one — see "Phase 2" above, not a one-line summary.
- **Budget: Vlad is topping up the Anthropic account with 5 EUR and wants it to stretch — spend deliberately, everyone.** `LLM_MODEL_SMART` is now `claude-haiku-5-5` in the shared `.env` (was Sonnet 5.5). This is a temporary override, not a reversal of D12/D26 — revert to `claude-sonnet-5-5` before trusting summary quality or citing D26's cost numbers again. It covers both the engine's own summary call and **evals' simulator persona** (`evals/simulator.py` calls the same `tier="smart"`), which is probably the single biggest cost driver in any live run, bigger than the engine's own extract/compose calls.
  - **Engine:** when credits land, run the minimal targeted checks first (the two CLI scripts, the two bug-fix spot-checks) before anything broader.
  - **Evals:** prioritize the 5-scenario smoke suite over a full 20-scenario run, and hold off on V4 repeats 2-3 / V8's full re-run until there's a sense of how far the 5 EUR is actually going. A full suite run was costing about $0.42 on the old Sonnet-summary config (`status/evals.md` V3); expect less now, but "expect less" isn't a budget, so check as you go.
  - **App:** your own live checks (e.g. A2's worker smoke test) are cheap and infrequent, no change needed from you.
- **CP4 declared, 2026-10-15** (BOARD.md has the evidence). Phase 2 is done across all three lanes. **Budget spent so far from the 5 EUR top-up: ~$0.47** (evals' live runs ~$0.43, app's A10/A11 live check $0.0039, my own $0.00002 credit-check ping). Plenty left, but V4's 2 remaining repeats would cost ~$4-5 on the expensive Sonnet-fast config — that's a real budget call, handed to Vlad, not decided here.
- **Next lead work (L4 deploy, L6 presentation notes):** these are lead tasks, not routed to a lane. L4 (an actual Railway deployment) is a real, external, somewhat-hard-to-reverse action — will confirm with Vlad before doing it rather than just starting. L6 I can draft independently; starting there first.
- **WhatsApp sandbox: closed, D35.** Twilio's free tier blocks configuring a custom sandbox webhook at all (confirmed via their own API — not a repo bug, not something to keep debugging). Torn down my test setup: killed the local `runserver`/`run_worker`/Cloudflare-tunnel processes I'd started, left `.env`'s `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_WHATSAPP_FROM` in place (correct and harmless to keep), reverted `ALLOWED_HOSTS`/`PUBLIC_BASE_URL` to localhost defaults since the tunnel URL is dead now anyway.
- **Final instruction to evals, so the project can be called done:** skip V4 repeats 2-3 (my call — the decision is already clear, 20/20 vs 18/20 at 6.4x the cost, and 2 more repeats would burn most of the remaining budget confirming something not in doubt). Do run the cheap check from the last Review notes entry (`uv run python -m evals.run --only 04 13 18`, a few cents) to confirm E17's fixes hold in context, then evals is done. **Engine and app: nothing outstanding — Phase 2 is complete.**
