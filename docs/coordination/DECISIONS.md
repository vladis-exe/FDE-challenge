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

## D26 [evals] Haiku 5.5 runs the conversation; Sonnet 5.5 writes the summary
Measured in V4 (`evals/reports/model-comparison.md`): the full 20-scenario suite with the fast tier (extract and compose) on Haiku 5.5 vs Sonnet 5.5, smart tier (summary) on Sonnet in both. Haiku: 20/20 scenarios, 100% outcomes and fields, $0.0059 per conversation, 2.5 s median per message. Sonnet: 18/20 (it twice stored only the surname after a surname re-ask), $0.0377, 3.0 s. Code makes every decision (D3), so the model's job is reading messy messages and phrasing replies, and Haiku already scores at the ceiling of these scenarios. Sonnet stays on the summary: one call per conversation, read by a recruiter, and not yet scored by the eval. Trade-off: the evidence is one repeat per configuration (the API credits ran out before repeats 2–3), so the report is marked provisional. The next test is Haiku for the summary too, which would cut cost to about $0.002 per conversation but needs a summary-quality check first.

## D28 [engine] A read-back restatement is a confirmation, and read-back rounds are capped
(Renumbered from engine's own D26 — collided with evals' D26, both lanes appended on the same day without seeing each other's entry yet. Content unchanged.)

Evals found the identical read-back re-sent up to 8 times when a candidate restated a correct value. Now a message at the read-back that changes no stored value counts as "yes, that's right"; a bare "no" or a real correction is one round, and past `max_attempts_per_field` rounds the screening ends as needs_review (`unresolved:confirm`) instead of looping. The round counter lives in `pending_confirmation` (`{"type": "readback", "rounds": n}`), which already means "awaiting the candidate's confirmation", so no contract field was added.

## D29 [engine] The extraction schema is built per vacancy
(Renumbered from engine's own D27, for the same reason as D28 above. Content unchanged.)

`Extraction.fields` is a Pydantic model generated from the vacancy's FieldSpecs (`create_model`, cached), so constrained decoding can only return this job's fields, and enum fields only their own options. A generic "any field" dict would let the model invent keys that code then has to reject. The prompt describes reading rules by field type, not by field name, so a new vacancy needs no prompt edit; it stays byte-stable per vacancy, so prompt caching still applies.

## D30 [lead] CONTRACTS v4.1: four additive FieldSpec keys
Engine requested, and Vlad approved directly in the engine session (2026-10-14): `reason` (outcome-string name, so `driver`'s `no_license`/`license_unclear` stay unchanged under the generic code), `summary` (the read-back noun per locale, replacing a hardcoded label table), `option_labels` (enum_multi display text per option/locale), `exclusive_options` (enum_multi options that stand alone, e.g. `flexible` — previously hardcoded). All four default to empty/`None`, so no existing vacancy file needs to change. Writing this up after the fact, since the approval happened directly between Vlad and the engine session rather than routed through lead — the contract doc is now caught up to what's actually built (CONTRACTS §7, `screening/config/vacancy.py`).

## D31 [app] Which job a conversation screens for, when the entry point doesn't say
`/chat/?vacancy=<id>` and `/apply/` name the job explicitly (one link per job ad; the picker is a demo convenience). Two cases the spec doesn't cover: (1) a candidate who messages the WhatsApp number first, with no link, screens for `WHATSAPP_VACANCY` (env, default `driver`), on the reading that one number stands for one job ad; (2) re-applying on `/apply/` resumes only a screening for the *same* job, while a different job starts a second screening, and the webhook routes the candidate's replies to their newest conversation. Trade-off: a candidate mid-screening for one job who applies for another leaves the first one open until it times out (abandoned at 24 h). That's acceptable at demo scale; production would want one number or keyword per job, or an explicit "which job?" step, which is worth asking Vlad before going live.

## D32 [engine] The city matcher must never disqualify by misreading
"City not served" is a knockout, so the matcher errs toward asking. A region alone ("vivo en Jalisco") offers that region's served cities instead of starting the out-of-area process; names that agree ("San Pedro, Monterrey") mean the city they share, and only names that disagree stay ambiguous; anything else that looks unserved needs the candidate's explicit confirmation before it disqualifies. Each of these came from a live run (evals scenario 04, the post-top-up CLI demo). Cost: a few more clarifying questions, each answered in one message.

## D33 [engine] When code can know the answer, fix it in code, not the prompt
Live runs found model slips the prompt alone didn't reliably prevent. Where the answer is knowable without the model, code now supplies it: a surname reply is joined to the stored first name, option questions get their options already in the candidate's country vocabulary from config, the read-back shows the candidate's own detail on a flagged answer, and the summary gets the job title rather than its id. Prompt fixes are kept for what only the model can judge (slang yes/no, a declined question vs. an opt-out). Code fixes are testable without an LLM and can't drift with a model change.

## D34 [engine] Live verification on a budget: targeted probes per fix, full runs left to evals
On the 5 EUR top-up, every engine fix was checked live with the smallest probe that exercises it: the extractor on the exact scenario line, 2–3 times, or one CLI demo per vacancy (cents in total). Full 20+ scenario runs stay with the evals lane (V8), which confirms the fixes in context. The trade-off is less coverage per change, offset by evals' complete runs after each batch.

## D35 [lead] The live WhatsApp sandbox demo is blocked by Twilio's free tier, not by this code
Twilio's Account SID and Auth Token (the real pair, not an API key) are in `.env`; a local server was tunneled with Cloudflare's quick tunnel (no account needed); the webhook correctly rejected an unsigned test request. But every message to the sandbox number got Twilio's own "Standard auto-reply", including the join code — confirmed via Twilio's own message log (`client.messages.list()`) and by checking there was no Messaging Service or owned number silently intercepting it. The sandbox's "when a message comes in" webhook field redirects to an upgrade page on a free account. This is a platform policy, not a configuration mistake: the webhook (`apps/messaging/whatsapp.py`) is fully built and unit-tested — signature validation, idempotency on `MessageSid`, phone routing — and that's the evidence for it working, not a live sandbox run. Upgrading the Twilio account would unblock it; not done, since it's a real cost decision that's Vlad's to make, not assumed here.

## D36 [lead] Dropped replies are removed from the engine's memory, by the shell, through one engine function
Reply-to-latest (spec: only the latest message gets answered) means the worker sometimes discards a reply the engine already wrote into `transcript_tail`. V10 found the cost: the Sonnet summary read those unsent replies and told the recruiter "Alex repitió dos veces" questions the candidate never saw. Only the shell knows what it dropped, and only the engine should edit its own state, so CONTRACTS v4.2 adds `engine.forget_undelivered(state, dropped)`: pure, no LLM, called by the worker (and the evals simulator) before persisting. Rejected: a `suppressed` flag on transcript lines (a schema change every reader would have to honor) and having the engine guess from timestamps.
