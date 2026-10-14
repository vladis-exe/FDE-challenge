# Decisions

Append-only. Format: `## D<n> [lane] Title`, then decision, why, and trade-off in 2–4 lines. These feed the README and the presentation.

## D1 [lead] Django over FastAPI
Django gives the recruiter tool auth, admin, ORM, migrations and templates for free, which matters in a 3-day build. The screening engine stays framework-free, so this choice only affects the shell.

## D2 [lead] Functional core, imperative shell
`screening/` is pure Python: state in, state + messages + events out. It is unit-testable and evaluable without a database, and the same engine serves WhatsApp, web chat, the CLI and evals.

## D3 [lead] Code decides, the LLM speaks
The LLM extracts values and writes replies. Validation, stage transitions and outcomes are deterministic code. That makes outcomes auditable (GDPR Art. 22, EU AI Act) and immune to prompt injection.

## D4 [lead] Location = country + city
No zone or postal-code layer. Aliases and neighborhoods map to their city. Simpler config; a production rollout would add zones if the client routes by hub.

## D5 [lead] License is a boolean; unclear goes to human review
Expired, in-progress or foreign licenses are not auto-rejected. A false rejection loses a good candidate; a review costs a recruiter a minute.

## D6 [lead] Start date = resolved ISO date + pointer to the source message
The original wording lives in the stored message, so it isn't duplicated. Resolution uses that message's timestamp in the candidate's time zone, not processing time.

## D7 [lead] Sequential processing per conversation, reply only to the latest
Every message updates state in order. A reply is dropped if a newer message is already waiting, so bursts don't produce stale questions.

## D8 [lead] Database-backed queue + worker command, no Celery/Redis
Fewer moving parts at 1,000 applications a week. `select_for_update(skip_locked)` gives per-conversation locking. Revisit (a real queue, horizontal workers) at 10K/week.

## D9 [lead] Reminders at 15 min, 2 h, 20 h; abandoned at 24 h
All three fit inside WhatsApp's 24 h customer-service window, so no template approval is needed for the demo. Production adds an approved template at 3 days. Quiet hours run 21:00–09:00 local.

## D10 [lead] Two entry points
A job-ad link where the candidate starts the chat (no template needed), and an apply form where the agent messages first (the production path).

## D11 [lead] No agent framework
No LangChain, LangGraph or CrewAI. The orchestration is small, explicit and fully explainable in a live review.

## D12 [lead] LLM: Claude behind a thin client; final model choice by evals
Fast tier for extract/compose and smart tier for summaries by default. V4 decides the final configuration on accuracy, latency and cost per screening.

## D13 [lead] Eight spec gaps resolved for E5, engine's proposed defaults all approved
The engine lane listed 8 behaviors the spec implies but doesn't spell out (consent decline, out-of-area waitlist wording, shared offtopic/abuse/injection strike counter, human handoff timing, resuming after `abandoned`, messages after a final outcome, no-surname handling, vague vs. explicit-unclear license). Each proposal is a direct, literal reading of `process-design.md`'s own text (e.g. the name rule is quoted almost verbatim), so none needed a contract change or a call from Vlad. Full list and reasoning: `status/engine.md` "Open spec questions", 2026-10-12. If any of these turns out wrong in practice, it's a status-file note and a small E5 patch, not a contract change.

## D14 [lead] CONTRACTS v2: split cache tokens out of LLMUsage
`cache_read_tokens` and `cache_write_tokens` added, both defaulting to 0, so existing callers don't break. Cached input is billed at roughly 0.1x and cache writes at 1.25x; folding everything into `input_tokens` (the v1 workaround) overstates cost in A6's analytics and V3/V4's cost-per-conversation numbers, which is exactly the evidence the LLM write-up leans on.

## D15 [app] The worker holds the conversation row lock for the whole engine turn
A turn is one transaction: `select_for_update(skip_locked=True)` claims the conversation, the engine runs, then state, outbound messages and events are written, and only after commit is anything sent. The lock *is* the per-conversation ordering guarantee, with no lease columns or queue. The trade-off is a DB transaction open across an LLM call (1–3 s), which is fine at 1,000 applications/week. At 10K/week we'd claim with a lease and run the LLM outside the transaction.

## D16 [app] SQLite runs IMMEDIATE transactions with WAL
With SQLite's default deferred transactions, a worker turn that reads, waits on the LLM, then writes fails with "database is locked" if the web view inserted a message meanwhile, and that is exactly the burst case. IMMEDIATE + a 20 s busy timeout makes the web insert wait for the turn instead (measured: 1.3 s during a 2 s turn), and WAL keeps chat polling unblocked. Postgres in Docker/deploy needs neither.

## D17 [app] An engine or persist error consumes the message
If a turn raises, the message is marked processed and a `worker_error` event is recorded, instead of being retried. A deterministic bug would otherwise wedge that conversation (and burn LLM calls) forever. The cost is that the candidate gets no reply to that one message; the event makes it visible on the dashboard.

## D18 [engine] Fixed text where words carry legal or outcome meaning; the LLM writes the rest
The opening (AI disclosure, privacy link), the read-back of stored answers, every close, the holding reply and the reminders come word for word from `screening/prompts/messages.yaml`. Mid-conversation replies are LLM-written from a plan that code builds. A disqualification can never be worded wrongly, and the read-back can never misstate a value. The cost: those messages are less adaptive, which is acceptable for a dozen fixed moments.

## D19 [engine] The LLM resolves start dates; code validates them
The extractor gets the candidate's local date and weekday and returns an ISO date (or asap/vague). Code then checks: asap means today, no past dates, at most 183 days ahead. The model handles "el lunes que viene" and "after my exams on the 20th" better than dateparser, and the rule still runs in code. Trade-off: one more thing the extraction prompt must get right, covered by the few-shot examples and evals.

## D20 [engine] Thinking stays on at low effort, with output headroom
Current Haiku and Sonnet think by default, and turning thinking off is model-specific (`disabled` vs `between_tools`), which would break V4's model swaps. We keep it on, ask for low effort and add 2,048 tokens of headroom to `max_tokens`. Measured: about 1.3 s per extract and 1 s per compose on Haiku 5.5, with the static system prompts cached (about 5,000 of 5,200 input tokens read from cache).

## D21 [engine] The reply guard checks the message rules in code: regenerate once, then trim
Every composed reply is checked for ≤300 characters, ≤2 sentences, exactly one question at the end, ≤1 emoji and plain text. If it fails, it's regenerated once with the broken rules quoted back; if it still fails, it's trimmed deterministically. Live probe: 4 of 18 first drafts broke a rule, 0 of 18 final replies did. Cost: an occasional second fast-tier call, about 1 s.

## D22 [engine] next_due_at includes quiet hours
The engine tells the worker when the next tick is due, already moved to 09:00 local if a reminder falls in quiet hours. The worker doesn't poll every minute overnight, `reminder_deferred` is logged once, and the timing logic lives in one place. If several reminders came due overnight, only one message is sent.

## D23 [lead] CONTRACTS v3: next_due_at added; LLM-failure bookkeeping clarified
Two items engine and app converged on independently, both approved as implemented (no code changed, contract caught up to it):
- `screening.engine.next_due_at(state, *, config) -> datetime | None` added to §2, so the worker stops duplicating E7's reminder-timing logic (app's own proposal, built by engine against it directly).
- The "state unchanged except `transcript_tail`" line on LLM failure was read literally by app as excluding `last_inbound_at`/`last_outbound_at`/`reminders_sent`, but engine updates them (the holding reply is real outbound contact, and reminder timing would drift otherwise). The contract now says so explicitly. Checked against `screening/engine.py` directly: matches.

## D24 [app] A recruiter override writes the engine state, not just the status column
The worker copies `state.status` onto `Conversation.status` on every turn, so an override that only changed the column would be undone by the candidate's next message. The override sets both (plus a rebuilt `final_record`), logs a `ReviewAction` and a `recruiter_override` event, and never calls the engine. From then on the engine treats the screening as finished. Overriding an in-progress screening therefore ends it, which is the intent when a recruiter decides.

## D25 [lead] CONTRACTS v4: vacancies, dynamic fields, preference scoring over knockouts
With the original scope shipped (CP1–CP3 substantially done: engine, app, evals all at or near feature-complete), Vlad asked to generalize past the single hardcoded Grupo Sazón driver role: a second vacancy, or client, needs a different required-field set without an engineer editing Python, and a field that's a hard requirement for one role (driver's license) should be able to be a pure plus for another — prefer the candidate who has one, in a tie, for a role that doesn't need it.

**What changes:** `CandidateProfile` goes from 7 hardcoded fields to `fields: dict[str, FieldValue[Any]]`, keyed by a per-vacancy `FieldSpec` list (`screening/config/vacancies/<id>.yaml`) drawn from a small, closed, engineer-owned field-type catalog (`text`, `boolean`, `city`, `enum_multi`, `experience`, `date` — each reusing an existing validator). Each field gets a `requirement`: `required` (today's behavior — re-ask, flag, knockout), `preferred` (asked once, never re-asked, never flags, never disqualifies, contributes a weighted `preference_score`), or `off`. Required fields are always collected before preferred ones, preserving the "knockouts first" fail-fast design. Full spec: CONTRACTS §7.

**Why config, not a full rules DSL:** letting recruiters add arbitrary new validation logic would mean an unaudited field could silently decide an outcome — directly against D3's auditability argument (GDPR Art. 22, EU AI Act). Letting them *compose* from a fixed, engineer-reviewed catalog of field types keeps every decision explainable while still making "which fields, which order, required vs. nice-to-have" a config change, not a code change. A full authoring UI is future work; the YAML shape is designed to be what that UI would eventually generate.

**Why scoring never overrides a knockout:** explicitly scoped as a tie-breaker among already-qualified candidates, not a path to qualifying someone who failed a requirement. A `preferred` field that would have been a knockout under `required` (e.g. `has_driver_license: false`) is deliberately downgraded to a plain stored value when the field is merely preferred — never a disqualification, by design. This is the direct implementation of Vlad's "in a draw I'd hire the one who has it" example.

**Trade-off:** this is a real, structural rework (`CandidateProfile`, `policy.py`'s field iteration and knockout handling, the extraction schema, the compose layer's field labels, the app's `Conversation` model, every eval scenario's `expected` block) touching nearly every file the other 23 decisions were made about. Taken on explicitly, with the 3-day framing dropped by Vlad's own call — the quality bar doesn't move, only the time budget does.
