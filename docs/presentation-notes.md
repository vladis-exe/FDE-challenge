# Presentation notes

For the live session. Not a rehash of the README — this is what to actually say and do, and
what to do if something goes wrong while people are watching.

## Demo script (~12–15 minutes)

Run this in order. Each step is short on purpose — the point is to show the system working,
not to narrate every line (that's what `docs/code-tour.md` and `screening/README.md` are for,
if asked to go deeper on any one piece).

**1. The engine, bare, both jobs (2 min).**
```bash
uv run python -m screening.cli --country MX --script tests/engine/scripts/demo_mx.txt
```
Let it run to the end uninterrupted — qualified, with a real summary. Point out: real Claude
calls, no mocking, ~2–3 s per turn, state diff and events printed after every turn. Then:
```bash
uv run python -m screening.cli --vacancy kitchen_prep --script tests/engine/scripts/demo_kitchen.txt
```
Same engine, different job, no code change — just a different YAML. This is the one line that
proves Phase 2's generalization claim isn't just a slide.

**2. The web chat, live (3 min).**
`runserver` + `run_worker` in two terminals, open `/chat/?vacancy=driver`. Type a couple of
turns yourself. This is the same engine behind a real worker, real persistence, real polling —
say that explicitly, since it's easy for an audience to assume the CLI and the web app are
different implementations.

**3. The dashboard, from seeded data, not live (4 min).**
Don't re-seed live — `seed_demo` is deterministic but takes a moment and depends on nothing
going wrong at the worst time. Use what's already there. Show, in this order:
- The queue, sorted by status, and inside "qualified" the `kitchen_prep` tie-break pair —
  **this is the one thing to make sure lands**: two candidates, same outcome, ranked by a
  preferred field (a driver's license, worth 1.5 points for a job that doesn't require one).
  Click into both detail pages and show the score breakdown.
- One `needs_review` candidate's detail page: flagged field, source-message link, event
  timeline, final JSON.
- `/dashboard/analytics/`: the funnel, cost-per-conversation tile, the per-job breakdown.

**4. Say the WhatsApp line out loud, don't dodge it (1 min).**
"The WhatsApp webhook is built and unit-tested — signature validation, idempotency, phone
routing. I tried to demo it live against Twilio's sandbox and found their free tier blocks
configuring a custom webhook entirely — confirmed that directly through their own API, not
guessed. That's a platform limitation, not a gap in this code, and I'd rather say that plainly
than fake a screen recording." This is a good moment, not a weak one, if said directly — it
shows real debugging (D35), not an excuse.

**5. One curated sample conversation (2 min).**
Open `docs/sample-conversations/` and pick the one with an engine stumble still visible (a
flagged field, or the "de NL" note). Say why it's shown unedited: it's evidence of a real
evaluation loop (see V8, D32/D33), not a cherry-picked transcript.

**6. Close with the numbers (1 min).**
From `evals/reports/model-comparison.md`: Haiku vs. Sonnet, 20/20 vs 18/20, $0.0059 vs $0.0377
per conversation, $5.88/week vs $37.73/week at 1,000 applications. That's the LLM-choice
justification in one breath.

## Demo-day checklist

- [ ] `uv run pytest tests/engine tests/evals` and `DJANGO_SETTINGS_MODULE=config.settings uv run pytest tests/app` — both green, right before presenting, not the night before.
- [ ] `.env`: a real `ANTHROPIC_API_KEY` with actual remaining credit. If `LLM_MODEL_SMART` is still overridden to Haiku for budget reasons, decide beforehand whether to revert it to Sonnet for the demo — a live summary call reads better on the real config, and it's one line in `.env`.
- [ ] `uv run python manage.py migrate && uv run python manage.py seed_demo` run **before** people arrive, not during. If the fixture is out of date, `--reset` it the day before.
- [ ] A quick CLI smoke run (`--fake`, free) right before, just to confirm the laptop/network/venv didn't rot since the last test.
- [ ] **Fallback plan:** `docs/sample-conversations/` and `evals/reports/v8-v4-engine.md` are the backup if live anything flakes — real transcripts and real numbers, not a recording to fall back on, which is arguably stronger: "here's a real run from yesterday" costs nothing to pull up.
- [ ] Know the one number for each: LLM cost per conversation ($0.0059), full suite pass rate on the generalized engine (20/24, with the 4 explained), budget spent proving it ($0.47 of 5 EUR).

## Architecture talking points

Pick from these when asked, don't recite all of them unprompted:

- **"Why not an agent framework?"** D11. The orchestration is `policy.py` + `engine.py`, a few
  hundred lines, in one language, every call site visible. Offer to open `policy.py` and read
  the transition-table docstring aloud — it's meant to be readable as the spec.
- **"How do you stop the model from making the actual decision?"** D3. `decide()` in
  `policy.py` never imports anything that could call an LLM — structurally, not by convention.
  The model's only two jobs are reading a message into a typed `Extraction` and phrasing a
  reply from a plan code built. Show `code-tour.md`'s "one message" trace if there's time.
- **"What happens when Claude is down?"** `LLMError` → a fixed holding reply, state untouched
  except the transcript. The retry (by the candidate re-sending, or the worker's own loop)
  picks up exactly where it stopped. Nothing is silently lost.
- **"Why did you generalize to multiple jobs?"** D25. Say it plainly: the original brief was one
  client, one role; a real product serves many. The design choice worth defending is that a
  `preferred` field can never substitute for a failed `required` one — it only ever breaks a
  tie, which keeps the GDPR/EU-AI-Act auditability argument (D3) intact even as the system got
  more flexible.
- **"Why Django, why SQLite/Postgres, why no Celery?"** D1, D8. Django for free auth/admin/ORM
  on the shell; the engine itself is framework-free. `select_for_update(skip_locked)` is a
  real queue at this scale, and DECISIONS says exactly where that stops being true (below).

## The 10K/week answer

Two things change, and DECISIONS already names them as the explicit revisit point, not an
afterthought:

1. **D8 / D15 — the lock.** Today, the worker holds a `Conversation` row lock across the entire
   LLM round-trip (1–3 s) — simple, and the lock *is* the ordering guarantee. At 10x volume,
   that lock held that long becomes the bottleneck. The fix: claim with a time-boxed lease
   instead of a held row lock, and make the LLM call *outside* the transaction, writing results
   back with an optimistic check. More code, same core idea.
2. **D8 — the queue itself.** A DB-backed queue with `skip_locked` scales with more worker
   processes up to a point (Postgres connection limits, contention on the `Message` table). A
   real queue (SQS, Redis-backed) would be the next step, but wasn't worth the operational
   complexity at 1,000/week, and D8 says so explicitly rather than treating it as free.

Nothing else needs to change — the engine itself is stateless per turn and already scales
horizontally; it's the persistence/locking layer that has a ceiling.

## What I'd do with more time

In rough priority order, each tied to something concrete already in the repo, not a wishlist:

1. **The 2 skipped V4 repeats** (`evals/reports/model-comparison.md`) — cheap to finish once
   there's budget, would turn "provisional" into a confirmed number.
2. **A real WhatsApp Business number**, not the sandbox — needs Meta Business verification,
   which is a multi-day process, not a code change. The webhook code doesn't change; only the
   number and the approved-template requirement for business-initiated messages do.
3. **A recruiter-facing vacancy editor.** The YAML shape in `screening/config/vacancies/` was
   explicitly designed to be what a form would generate (D25) — building that form is the
   natural next step, not a redesign.
4. **Voice.** The engine is channel-agnostic already (`Channel.WEB`/`WHATSAPP`/`SIM`); adding a
   speech-to-text/text-to-speech adapter and shorter, more fragmented turns is additive.
5. **ATS integration.** `screening.record.final_record(state)` is already the deterministic,
   typed JSON an ATS would want; an outbound webhook on status change is a small addition.
6. **The two open evals findings** (scenario 04's "simón" misread as a name, scenario 13's
   read-back detail) — likely already fixed (E17), just needs the cheap re-verification run
   evals was asked to do.
