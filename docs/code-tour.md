# Code tour: how a message actually moves through this system

> **This trace predates Phase 2 (CONTRACTS v4).** It was written when there was one hardcoded job
> (seven fixed `CandidateProfile` fields, a per-field `Stage` enum). The engine has since been
> generalized to the vacancy system — `CandidateProfile.fields` is now a dict keyed by whatever
> a vacancy's `FieldSpec` list defines, `Stage` collapsed to four generic phases, and there are two
> live jobs (`driver`, `kitchen_prep`). **For the current architecture, read `screening/README.md`
> instead** — it's engine's own guide, written for exactly this purpose and kept current by the
> lane that owns the code. The *mechanics* traced below (extract → policy.decide → compose →
> guard → persist, one lock per conversation, the LLM called exactly twice per turn) are still
> accurate in shape; only the field model and a few function signatures changed. Worth a reread
> once, matching old names to new, rather than trusting this file's specifics verbatim.

The README gives you the map. This is the walk — one concrete message, traced through the real
function calls, then each module explained on its own. Read this with the files open; every
section names exact functions so you can jump straight to them.

If you only read one section, read **"One message, start to finish"** — it's the whole system in
miniature, and almost every design decision in `DECISIONS.md` exists because of something that
happens in that trace.

## The one rule everything else follows

**Code decides, the LLM speaks.** Concretely: the LLM is called exactly twice per turn
(`extract`, then `compose`), and both calls return a typed, Pydantic-validated object —
never a decision. Everything in between — `screening/policy.py` — is plain Python with no LLM
access at all. If you remember nothing else, remember that `decide()` in `policy.py` cannot call
the network, and that's not a convention, it's structural: the function doesn't import anything
that could.

## One message, start to finish

Say the candidate (new, Mexico, mid-consent) sends: **"va, soy Diego Cantú, y sí tengo licencia"**
(three facts in one message: consent, name, license). Here's exactly what happens.

**1. It lands as a row, not a function call.**
`apps/messaging/views.chat_send` (or the WhatsApp webhook, once A4 exists) calls
`services.store_inbound(conversation, text)` — `apps/messaging/services.py:81`. This just
inserts a `Message` with `processed_at=None` and returns. No engine code runs yet. This
separation (store now, process later) is *why* a crashed worker can't lose a message — the row
is already durable before anything risky happens.

**2. The worker claims the conversation, not the message.**
`run_worker` loops calling `work_once()` → `process_next_inbound()`
(`apps/messaging/services.py:112`). It locks one `Conversation` row with
`select_for_update(skip_locked=True)`, picks that conversation's *oldest* unprocessed message, and
holds the lock until the whole turn — including the LLM calls — is done. That lock **is** the
per-conversation ordering guarantee (D7, D15): two workers can never process the same
conversation's messages out of order, because the second one just skips the locked row and goes
to find other work.

**3. The engine runs, knowing nothing about Django.**
`engine.handle_message(state, message, ctx)` (`screening/engine.py:79`) is called with a
`ConversationState` rebuilt from the JSON column (`ConversationState.model_validate(conversation.state)`)
and an `InboundMessage`. From here until step 7, nothing touches a database — this whole block
is testable with zero I/O except the two LLM calls.

**4. The LLM reads the message — it does not decide anything.**
`extract(state, message, llm, config)` (`screening/understand.py:114`) sends one `structured()`
call to Haiku 5.5 asking for an `Extraction`: `intent="answer"`, `language="es"`,
`consent="yes"`, and `fields={"full_name": "Diego Cantú", "license": "yes"}`. The *system* prompt
(persona rules, FAQ catalogue, few-shot examples) is identical on every call in the whole
conversation, which is why ~5,000 of its ~5,200 tokens are read from cache, not billed at full
price, on every turn after the first.

**5. Code decides — this is `policy.decide()`, the one function that matters most.**
`decide(state, extraction, message, config)` (`screening/policy.py:159`) builds a `_Turn` working
object over a *copy* of the state (never mutates the input) and calls `turn.run()`. Here's the
actual path for this message:
   - `run()` (`policy.py:195`): status is `in_progress`, intent is `answer` — not opt-out, not
     human-request, not off-topic. Stage is `CONSENT`. `x.consent == "yes"` → sets `consent_at`,
     logs `consent_given`, falls through.
   - No `pending_confirmation` (no city dispute in flight). Stage isn't `CONFIRM`. Falls through
     to `self.collect()`.
   - `collect()` (`policy.py:267`): builds a `raw` dict of every field the extraction populated.
     Here that's `full_name` and `has_driver_license`. It loops `FIELDS` *in spec order* and calls
     `self.apply(name, raw[name], asked=...)` for each one present — so even though the candidate
     answered two things, both get applied in the same turn.
   - `apply("full_name", "Diego Cantú", asked=False)` (`policy.py:300`) → `apply_name` →
     `validate_name` (`screening/validators/fields.py:60`) sees two words, accepts outright.
     `settle()` stores it, logs `field_accepted`, and queues `"name: Diego Cantú"` onto
     `self.acknowledge` — this is what tells the *next* LLM call what to say thanks for.
   - `apply("has_driver_license", "yes", asked=False)` → `validate_license("yes")`
     (`fields.py:49`) → `Verdict.accept(True)`. Not a knockout (that's the `False` branch,
     handled separately in `apply()` — a disqualifying "no" never even reaches `settle()`).
   - Back in `collect()`: `next_step()` (`policy.py:401`) finds the next missing field —
     `location` — and queues `Ask(field="location")` as the reply.
   - `reply()` (`policy.py:448`) builds a `ReplyPlan`: language `es`, country (from the phone
     prefix or chat picker hint), `acknowledge=["name: Diego Cantú", "has a valid driver's
     license"]`, `ask=Ask(field="location")`. **This plan is the entire interface between the
     deterministic half of the system and the LLM half.** The policy never writes a word of the
     reply; it writes a *plan* for one to be written from.

**6. The LLM writes — and code checks what it wrote.**
Back in `engine.handle_message`, the `ReplyPlan` goes to `compose_reply()`
(`screening/compose.py:115`), which turns it into a system/user prompt pair and calls
`llm.text(purpose="compose", ...)`. Say the draft comes back as *"¡Genial, Diego! Veo que
tienes licencia. ¿En qué ciudad vives?"* — three sentences, one too many. `check_reply()`
(`screening/guard.py:26`) catches that deterministically (it counts sentences with a regex, it
doesn't ask the model to grade itself) and `compose_reply` sends one retry with the broken rule
quoted back verbatim. If the retry *still* breaks a rule, `trim_reply()` cuts it down
mechanically — no second LLM call, just string surgery that keeps the question and drops from the
front. This is D21, and it's the difference between "usually fine" and "provably always within
spec" for something as simple as message length.

**7. Only now does anything touch the database.**
Back in `process_next_inbound`, the `TurnResult` (new state + outbound messages + events) is
handed to `_persist_turn()` (`services.py:197`), which writes the conversation's JSON state, the
mirrored filter columns (`status`, `stage`, `country`, `city`...), the `Event` rows, and the
outbound `Message` rows — **all in one transaction**. Only after that transaction commits does
`_send()` (`services.py:257`) actually deliver anything. If the process died one line earlier,
nothing was sent but nothing was lost either: the inbound message is still unprocessed, and the
worker picks it up again next loop.

That's the whole system. Every other file either feeds one of these seven steps or handles the
edge cases (silence, media, abuse, FAQ, corrections) that the same `_Turn.run()` dispatches to
before reaching `collect()`.

## `screening/schemas.py` — the shared vocabulary

Everything else is typed against this file; CONTRACTS §1 is a copy of it. The one shape worth
understanding deeply is `FieldValue[T]`:

```python
class FieldValue(BaseModel, Generic[T]):
    value: T | None = None
    status: FieldStatus = FieldStatus.MISSING   # missing | accepted | flagged
    source_message_id: str | None = None
    attempts: int = 0
    note: str | None = None
```

Every one of the seven profile fields is one of these, not a bare value. That's deliberate: a
`None` full_name and a *flagged* full_name both need to render as "we don't have this" in the
final record, but they mean different things to a recruiter (never answered vs. answered badly
twice) and `status` is how that distinction survives all the way to `final_record()`.
`source_message_id` is the provenance story — every stored fact points at the exact inbound
message that produced it, which is what a recruiter clicks through to on the dashboard (once A5
exists) and what makes "why did the agent think that" answerable after the fact.

`ConversationState` is the one piece of mutable truth. It's JSON in a Django column
(`Conversation.state`), round-tripped through `model_validate`/`model_dump(mode="json")` on every
turn — there's no ORM model for a candidate's profile, on purpose: the engine owns that shape, not
Django's migrations.

## `screening/policy.py` — the state machine

The module docstring *is* the spec: a 23-row transition table, checked top to bottom, first match
wins. Reading the table top-down tells you the actual priority order of every rule in the system:
opted-out candidates are silently ignored (row 1) before anything else is even considered; a
human request always wins over whatever field was being collected (row 6); off-topic messages get
exactly one redirect before being flagged (rows 7-8).

The implementation is one class, `_Turn`, that holds per-turn working state (`self.acknowledge`,
`self.retry`, `self.attempt_used`...) so the dozen or so methods can read and write it without
threading it through every call. A few methods are worth knowing by name because they're where
almost every behavior question resolves:

- **`fail(name, reason)`** (`policy.py:382`) is the *only* place attempts are counted and fields
  get flagged. Two re-asks, then flagged, every time — there's no other path to a flag for a
  normal field. This single function is why the agent can never loop forever on a bad answer.
- **`settle(name, verdict, asked)`** (`policy.py:357`) is the only place a field moves to
  `accepted` or `flagged`. It also detects *corrections* (`field_corrected` vs `field_accepted`)
  by comparing against the previous value — the event type a reader sees in the transcript is
  computed here, not passed in.
- **`resolve_pending()`** (`policy.py:244`) is the out-of-area confirmation dance (rows 12-15):
  a city that doesn't match any configured city doesn't disqualify immediately — it sets
  `pending_confirmation` and asks the candidate to confirm that's really where they are, because a
  typo shouldn't cost someone the job.
- **`collect()`** (`policy.py:267`) is why answering three questions in one message works: it
  loops every field the extraction populated, in spec order, applying each one — not just the
  field that was actually asked.

## `screening/understand.py` and the extraction prompt

One function, `extract()`, one Pydantic schema (`Extraction`), one Haiku call. The system prompt
(`screening/prompts/extract.md`) is static text with the FAQ catalogue formatted in — the catalog
changes; the prompt structure doesn't, which is what keeps it cache-eligible. The *user* message
(`user_prompt()`, `understand.py:88`) carries everything that does change: what field is being
asked, the candidate's local date and weekday (so "el lunes que viene" resolves against the right
calendar, not UTC), and a tail of recent conversation for context. This split — static system,
dynamic user — is the pattern every LLM call in the codebase follows (`compose.py` and
`summary.py` do the same), and it's the entire reason the cache-hit numbers in the README are
real.

## `screening/llm/` — the one place that talks to Anthropic

`AnthropicClient.structured()` and `.text()` (`screening/llm/anthropic_client.py`) are the only
two methods anything else is allowed to call. Both:
- use `messages.parse(output_format=...)` for schema-validated decoding, not a hand-rolled JSON
  parse and not forced tool use (which 400s on Sonnet 5.5 — found the hard way, see
  `status/engine.md`'s prep notes);
- ask for `effort: "low"` with the thinking budget kept (current models can't fully disable
  thinking without breaking model swaps) plus a fixed headroom added to `max_tokens`, so a short
  reply budget never gets eaten by invisible thinking tokens;
- map every failure — a refusal, a cut-off answer, an API error, an unparseable record after one
  retry — to the same `LLMError`. Nothing upstream ever sees an SDK exception; it's always
  `LLMError`, and `engine.handle_message` catches exactly that one type.

`FakeLLM` (`screening/llm/fake.py`) is why 212 tests run in under two seconds with no API key:
every test scripts exact responses keyed by `purpose` ("extract", "compose", "summary") and
records every call on `.calls` for assertions. `--fake` in the CLI (`screening/cli.py:164`) is a
*different*, cruder fake — a keyword stub good enough to walk the CLI without an API key, not used
in tests.

## `screening/compose.py` + `screening/guard.py` — the only creative part, fenced in

This is the one place in the whole engine where the LLM's actual words reach the candidate for
something other than a fixed string. `ReplyPlan` (`compose.py:50`) is what the policy hands over —
notice it has no free-text field for "what to say," only structured slots (`acknowledge`,
`faq_answer`, `ask`). `instructions()` (`compose.py:61`) turns that into a numbered list in plain
English/Spanish for the model to follow. The guard (`guard.py`) is pure regex and string
manipulation — no LLM grading its own homework — checking sentence count, question count and
position, emoji count, and absence of markdown formatting. D21's number (4 of 18 first drafts
broke a rule, 0 of 18 after the guard) is the evidence that this loop is worth its one occasional
extra API call.

## `screening/messages.py` — the words that are never model-written

D18: the opening (AI disclosure + privacy link), the read-back, every close, the holding reply
and reminders come word-for-word from `screening/prompts/messages.yaml` via `fixed()`
(`messages.py:123`). The read-back summary specifically (`summarize()`, `messages.py:156`) is
rendered field-by-field in code from the stored profile — it is *impossible* for the read-back to
state a value the candidate didn't actually give, because it's string formatting over
`state.profile`, not a model paraphrasing it. This is the one place where "the LLM could
hallucinate" would be a real risk (misstating what was recorded, right before asking the
candidate to confirm it) and it's closed by construction, not by prompting.

## `screening/timers.py` + `engine.handle_tick` — reminders without a cron job

There's no scheduled job. The worker just asks `next_due_at(state, config)`
(`screening/timers.py:26`) "when does this conversation need attention next," stores that on
`Conversation.next_tick_at`, and polls for rows where it's passed. `next_due_at` already resolves
quiet hours (`outside_quiet_hours`, `timers.py:52`) — a reminder due at 22:30 comes back as 09:00
tomorrow — so the worker never needs a one-minute retry loop overnight, and nothing special has
to happen for "don't message people at 2am" to just work. `silence_started()` (`timers.py:18`)
measuring from `last_inbound_at` (or the opening, if they never replied) is what makes a late
reply "resume where it stopped" rather than restart a reminder clock.

## The Django shell: why the worker looks the way it does

`apps/messaging/services.py`'s docstring lists five properties, each with its own test. The one
non-obvious piece is **why a transaction is held across an LLM call** (D15): the lock on the
`Conversation` row *is* the ordering guarantee, so it has to stay held for the whole turn,
including the 1-3 second round trip to Claude. That's fine at 1,000 applications/week and would
need rethinking — a lease instead of a row lock, LLM call outside the transaction — at 10K/week
(flagged in D8 and D15 as the explicit revisit point, not a "someday" without a trigger).

The other non-obvious piece is **why SQLite needed tuning** (D16, `config/settings.py:76`):
default deferred transactions mean a worker mid-turn (holding a write lock) and a web view trying
to insert a new inbound message collide with "database is locked" — exactly the burst case this
system has to handle. `IMMEDIATE` transactions plus a 20s busy timeout make the web insert *wait*
instead of failing; WAL keeps the chat's polling reads unblocked meanwhile. None of this exists in
Postgres (deploy), which doesn't have this failure mode.

**Reply-to-latest** (`process_next_inbound`, `services.py:144`) is one line —
`pending.filter(..., id__gt=message.pk).exists()` checked right before persisting — but it's the
answer to "what if the candidate sends two messages while the first is being processed": the turn
still runs and its state update is kept, but its *reply* is marked `suppressed` and never sent,
because a newer message is already waiting and deserves the answer instead. `close` messages are
exempted — a disqualification is never silently dropped.

## Testing strategy, in one sentence per tree

- `tests/engine/` — no Django import anywhere, `FakeLLM` for every LLM-touching test, so the
  whole engine (212 tests) runs in under two seconds and never costs a cent.
- `tests/app/` — needs `DJANGO_SETTINGS_MODULE` explicitly (not globally, so engine/evals tests
  stay Django-free); a fake engine (`tests/app/fakes.py`) and a fake channel stand in for the real
  engine and Twilio.
- `tests/evals/` — validates the *scenario schema* itself (internally consistent ground truth);
  running scenarios against the real engine is V2/V3, still pending.

## Quick answers to questions you'll probably get live

- **"Why not LangChain/an agent framework?"** — D11. The whole orchestration is
  `policy.py` + `engine.py`, a few hundred lines, in one language you already know, with every
  call site visible. Nothing is hidden in a framework's retry/memory/tool-routing logic.
- **"How do you stop the model from hallucinating an eligibility decision?"** — it structurally
  can't: `decide()` never calls an LLM, and the only two places the model's text reaches the
  candidate are `compose_reply` (fenced by the guard) and the fixed messages (not model-written at
  all).
- **"What happens if Claude is down?"** — `LLMError` propagates up to `engine.handle_message`,
  which sends a fixed holding reply and leaves the screening state untouched except the
  transcript — the next retry (by the candidate re-sending, or the worker's own retry loop) picks
  up exactly where it left off. Nothing is lost, nothing silently breaks.
- **"How do you know the reply follows the message rules?"** — you don't ask the model, you check
  it: `guard.check_reply()` is five regexes, not a second LLM call.
