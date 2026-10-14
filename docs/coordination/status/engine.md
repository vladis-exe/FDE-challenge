# Status: engine

Last updated: 2026-10-12

## Current task
**All engine tasks done** (E1–E9, E6b). Now: hardening from the eval scenarios while V2 is built; open for eval-driven fixes.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| E1 | `screening/schemas.py` (verbatim from CONTRACTS §1). `screening/config/`: `load_config(path=None)` → `ScreeningConfig`, plus `screening.yaml`, `service_areas.yaml` (6 ES and 5 MX cities with aliases and neighborhoods), `faq.yaml` (6 entries, es+en, `placeholder: true` on client terms) | `uv run pytest tests/engine` (15 pass); `uv run ruff check screening tests/engine` | 56b5071 |
| E3 | `screening/llm/`: `LLMClient` protocol and types (CONTRACTS §3), `AnthropicClient` (`messages.parse` structured output, effort `low` + thinking headroom, cached system block, SDK retries=3 / timeout 30 s, one extra try on an invalid record, refusal/max_tokens/API errors → `LLMError`), `FakeLLM` (scripts by purpose: list or callable; exceptions raised; `.calls` recorded) | `uv run pytest tests/engine` (29 pass). Live smoke on Haiku 5.5: structured 2.4 s, text 0.9 s | 3fe8f62 |
| E3 v2 | `LLMUsage.cache_read_tokens` / `cache_write_tokens` filled (CONTRACTS v2); `input_tokens` stays the total | `uv run pytest tests/engine` | 04f205b |
| E2 | `screening/validators/`: `Verdict` (accept / reask / flag), `match_city` (exact n-grams over names/aliases/neighborhoods, then fuzzy: ≥90 match, ≥80 options, max 3), license (yes/no accepted; expired/in_progress/foreign flagged; vague re-asked), name (one soft surname re-ask), availability/schedule (dedupe, canonical order, flexible alone), experience (months→years, platform aliases, 0–40), start date (asap=today, no past, ≤183 days, vague re-asked), `local_date(received_at, tz)` | `uv run pytest tests/engine` (90 pass) | d5d7ad0 |
| E4 | `screening/understand.py`: `Extraction` (intent, language, consent, confirmation, question, faq_id, typed raw fields) and `extract(state, message, llm=, config=)`. `screening/prompts/extract.md` (rules plus 6 few-shot examples: multi-field, Mexican vocabulary, emoji with expired license, code-switch with FAQ, correction at confirm, injection). `screening/locale.py` (candidate country/timezone) | `uv run pytest tests/engine` (98 pass). Live probe on Haiku 5.5: 8/8 correct; cache read 5,068 of ~5,200 input tokens; ~1.3 s per call (the first call after a schema change took 34 s) | d5c0e5c |
| E6a | `screening/prompts/compose.md` (Alex persona, hard message rules, how to ask each field). `screening/compose.py` (`ReplyPlan`/`Ask` decided by code → `compose_reply`, fast tier). `screening/prompts/messages.yaml` + `screening/messages.py`: fixed texts (opening with AI disclosure and privacy link, read-back, closes, holding, media, after-close) in es/en with ES/MX vocabulary, and a deterministic read-back summary. `privacy_url` added to `screening.yaml` | `uv run pytest tests/engine` (114 pass). Live probe on Haiku 5.5: 14/18 replies meet every hard rule; the 4 misses are 3 sentences or text after the question → E6b guard | 07114b7 |
| E2 fix | City names shared by two cities ("San Pedro": Monterrey and Guadalajara metros) are ambiguous; the longest match wins ("San Pedro Garza García" → Monterrey). Found via eval scenario 12 | `uv run pytest tests/engine` | 27b27c8 |
| E5 | `screening/policy.py`: the transition table (docstring, committed first in 4717b17) and `decide(state, extraction, message, config)`, which is pure and LLM-free. `screening/engine.py`: `EngineContext`, `new_conversation` (+34 → ES, +52 → MX hint), `start` (fixed opening), `handle_message` (opt-out silence and media first with no LLM; then extract → decide → render; any `LLMError` → holding reply + `llm_error`). Review reasons: `license_unclear`, `unresolved:<field>`, `human_requested`, `offtopic`, `abuse` (match the V1 scenarios) | `uv run pytest tests/engine` (160 pass; 46 in `test_engine.py`, at least one per table row) | c8052a5 |
| E9 | `screening/cli.py`: `uv run python -m screening.cli [--lang es\|en] [--country ES\|MX] [--fake] [--script file]`. Prints Alex's replies, the state diff and the events (`llm_call` with tokens, cache and latency). `--fake` = keyword stub, no API key needed. Colors only on a TTY | `uv run pytest tests/engine` (162 pass). **CP1 live check:** `uv run python -m screening.cli --country MX --script tests/engine/scripts/demo_mx.txt` → qualified after 11 turns (ambiguous "san pedro" → options, FAQ pay answer, "el lunes que viene" → 2026-10-19, schedule correction at the read-back); ~2–3 s per turn, prompts cached | 32c6bab |
| E7 | `screening/timers.py` + `engine.handle_tick`: fixed reminders (kind `reminder`) at 15 min / 2 h / 20 h of silence (counted from the candidate's last message, or from the opening if they never replied); a reminder due in quiet hours waits until 09:00 candidate-local (`reminder_deferred` + `reminder_sent`, one message even if several came due); `abandoned` at 24 h with no message, stage kept. `DEMO_TIME_SCALE` honored via config. New: `engine.next_due_at(state, config=)` | `uv run pytest tests/engine` (173 pass; `test_timers.py` includes the eval scenario 16 timeline) | 7dcc63a |
| E8 | `screening/record.py`: `final_record(state)` (contract JSON; only accepted values; flags as `{field, note}`). `screening/summary.py` + `prompts/summary.md`: Spanish recruiter note on the smart tier, written when the status leaves in_progress or abandoned (close or abandonment); a failure → `summary=None` + `llm_error`, and the close is still sent. Opt-outs get a fixed summary and no LLM call. The CLI prints the final record | `uv run pytest tests/engine` (180 pass). Live: the demo script's summary on Sonnet 5.5 is accurate (mentions the correction and the unanswered pay figure), 2.5 s | 62db461 |
| E6b | `screening/guard.py`: `check_reply` / `trim_reply` for the message rules. `compose_reply` drafts, regenerates once with the broken rules quoted back, then trims; the retry's `llm_call` event carries `retry_for` and `trimmed`. Prompt tuning from live runs: name in at most 1 message in 3, varied openers, no judging answers (not even positively), availability options inside the question | `uv run pytest tests/engine` (201 pass). Live probe: first drafts broke a rule in 4 of 18 → 0 of 18 after the guard. Two demo runs: natural tone, no retries needed | a4cbb86 |
| E4 fixes | The extract prompt now treats "mañana (mismo)" as tomorrow's date, not asap (scenario 16 ground truth); vague areas like "por la zona sur" are not a `city_text` (scenario 17: avoids a false out-of-area confirmation); hedged dates like "cuando sea, pronto supongo" are `vague` (scenario 07). Found by running **every scenario's scripted line** through the live extractor: all 20 lines now give the intent and fields the scenarios expect | `uv run pytest tests/engine` (201 pass); live re-probe 18/18 with regressions | b3562cc, see git log |

## Blocked
None

## Requests (to other lanes or the lead)
None (pytest config and UP046 resolved by the lead in 5944914)

## Spec questions: answered (approved as proposed, D13). E5 builds against these
1. **Consent declined:** which status? The spec says "close, nothing stored". *Proposal:* `opted_out`, empty profile, one close message.
2. **Out-of-area waitlist:** is the "waitlist offer" a sentence in the close ("we'll message you if we open in your city"), or a question whose yes/no we record? The schema has no field for it. *Proposal:* a sentence in the close; nothing recorded beyond the disqualify reason.
3. **Off-topic, abuse and injection strikes:** do all three share `offtopic_strikes`, with one redirect before close + `needs_review` (reasons `offtopic` / `abuse`)? *Proposal:* yes, shared counter, per the edge-case table.
4. **Human requested:** close at once with `needs_review` + `human_requested`, or keep screening? *Proposal:* close at once.
5. **Late reply after `abandoned`:** reopen to `in_progress` and resume? *Proposal:* yes, per "a late reply resumes where it stopped".
6. **Messages after a final outcome** (qualified, disqualified, etc.): *Proposal:* no state change, one short reply ("a recruiter will be in touch"), and FAQ answers still given. After `opted_out`, nothing is sent.
7. **Name with no surname after the one re-ask:** *Proposal:* accept it (status `accepted`, note "no surname given"), not flagged.
8. **License:** a vague answer ("bueno…") gets a yes/no re-ask. An explicit unclear case (expired, in progress, foreign) is flagged at once and screening continues. *Proposal:* as stated.

## Contract change requests
- **Support app's `next_due_at` proposal; it's implemented.** `screening.engine.next_due_at(state, *, config) -> datetime | None` exists (7dcc63a). It includes quiet hours: a reminder due at 22:30 returns 09:00 local. So the worker needs no 1-minute retry loop, and `reminder_deferred` is logged once rather than every minute all night. Please add it to CONTRACTS §2; the app can then drop its own computation.
- (Done: cache-token request, CONTRACTS v2, D14.)

## Notes for other lanes
- **App (A2): the real engine is ready to replace the stub.** `from screening import engine`, `engine.EngineContext(config=load_config(), llm=AnthropicClient())`, same signatures as CONTRACTS §2. `handle_tick` and summaries are live (E7, E8). `from screening.record import final_record` for `Conversation.final_record`. For `next_tick_at`, use `engine.next_due_at(state, config=...)` (see Contract change requests).
- **Lead, please confirm a contract reading:** on an LLM failure, CONTRACTS §2 says "state unchanged except `transcript_tail`". I also update the bookkeeping fields `last_inbound_at`, `reminders_sent = 0` and `last_outbound_at` (the holding reply was sent), because reminders are timed from the candidate's last message. Profile, stage, status, attempts and strikes are untouched.
- E1 is in (56b5071): `from screening.schemas import ...` and `from screening.config import load_config`.
- `ScreeningConfig.timezone_for("ES"|"MX")` gives the IANA zone.
- After `DEMO_TIME_SCALE`, `reminder_schedule` and `abandon_after` are already scaled timedeltas, and `config.time_scale` holds the factor. Quiet hours are not scaled (wall-clock rule).
- LLM: `from screening.llm import AnthropicClient, FakeLLM, LLMError`. `FakeLLM({"extract": [...], "compose": lambda system, messages: "..."})`. Engine purposes: `extract`, `compose`, `summary`.
- Validators: `from screening.validators import match_city, validate_*`. Evals can reuse `match_city` to score city answers.
- **Evals (V1 notes answered):** Zaragoza → `not_served` (fuzzy 61 vs "Puebla de Zaragoza", below the 80 suggestion cut); "san pedro" → ambiguous Guadalajara/Monterrey (I used San Pedro Tlaquepaque, not Cholula; the expected outcome is unchanged); FAQ covers pay, not health insurance; the review-reason strings and outcomes match your ground truth.
- **Evals (V3):** a composed reply that needed the guard shows up as a second `llm_call` with purpose `compose` and `data.retry_for` (plus `data.trimmed`), useful for a message-rule compliance score.
- **Evals:** `screening.record.final_record(state)` is the record to score against `expected`. For silence scenarios, call `engine.next_due_at(state, config=)` to know when to tick.
- Evals: the first extract call after a schema change can take ~30 s (one-off). Don't count it in latency stats, or warm up first.
- Fixed messages: `screening/prompts/messages.yaml` is the reviewable list of every word-for-word message (opening, closes, etc.); V5/presentation can quote it.
- FAQ answers flagged `placeholder: true` are client terms to replace before launch.

## Prep notes (engine-internal)
E3: Anthropic API facts, checked 2026-10-12 against the current claude-api reference, not from memory:
- Structured output: `client.messages.parse(..., output_format=PydanticModel)` returns a validated `response.parsed_output`. The old top-level `output_format` param on `messages.create` is deprecated; the raw form is `output_config={"format": {"type": "json_schema", ...}}`. We use `parse`, not forced tool use: forced `tool_choice` returns a 400 on Sonnet 5.5.
- Haiku 5.5 / Sonnet 5.5: no `temperature`/`top_p` (400 unless default), no assistant prefill (400), thinking adaptive by default. Set `output_config={"effort": "low"}` for extract/compose to keep latency down; Haiku's default effort is `medium`. Thinking can't be turned off on Sonnet 5.5 (`disabled` → 400).
- Always check `stop_reason`: `refusal` (no server-side fallback on Haiku 5.5) and `max_tokens` → treat as `LLMError`.
- Prompt caching: the minimum cacheable prefix on Haiku 5.5 / Sonnet 5.5 is 512 tokens. Put `cache_control: {"type": "ephemeral"}` on the static system block. Keep the system prompt byte-stable: no timestamps or per-candidate data in it, since state goes in messages. Verify with `usage.cache_read_input_tokens`; record cache read tokens in the `llm_call` event too.
- SDK retries: the SDK retries 408/409/429/5xx itself (`max_retries`, default 2). Set `max_retries=3`, plus a per-client `timeout` (e.g. 20s), and map final errors to `LLMError`. A schema-validation failure gets one retry of our own.
- `anthropic` 1.x is built on httpx2. Don't import httpx directly.
