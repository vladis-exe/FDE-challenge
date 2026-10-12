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
