# Status: engine

Last updated: 2026-10-12

## Current task
E6a Compose (basic), in progress. E1, E3, E2, E4 done.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| E1 | `screening/schemas.py` (verbatim from CONTRACTS §1). `screening/config/`: `load_config(path=None)` → `ScreeningConfig`, plus `screening.yaml`, `service_areas.yaml` (6 ES and 5 MX cities with aliases and neighborhoods), `faq.yaml` (6 entries, es+en, `placeholder: true` on client terms) | `uv run pytest tests/engine` (15 pass); `uv run ruff check screening tests/engine` | 56b5071 |
| E3 | `screening/llm/`: `LLMClient` protocol and types (CONTRACTS §3), `AnthropicClient` (`messages.parse` structured output, effort `low` + thinking headroom, cached system block, SDK retries=3 / timeout 30 s, one extra try on an invalid record, refusal/max_tokens/API errors → `LLMError`), `FakeLLM` (scripts by purpose: list or callable; exceptions raised; `.calls` recorded) | `uv run pytest tests/engine` (29 pass). Live smoke on Haiku 5.5: structured 2.4 s, text 0.9 s | 3fe8f62 |
| E3 v2 | `LLMUsage.cache_read_tokens` / `cache_write_tokens` filled (CONTRACTS v2); `input_tokens` stays the total | `uv run pytest tests/engine` | 04f205b |
| E2 | `screening/validators/`: `Verdict` (accept / reask / flag), `match_city` (exact n-grams over names/aliases/neighborhoods, then fuzzy: ≥90 match, ≥80 options, max 3), license (yes/no accepted; expired/in_progress/foreign flagged; vague re-asked), name (one soft surname re-ask), availability/schedule (dedupe, canonical order, flexible alone), experience (months→years, platform aliases, 0–40), start date (asap=today, no past, ≤183 days, vague re-asked), `local_date(received_at, tz)` | `uv run pytest tests/engine` (90 pass) | d5d7ad0 |
| E4 | `screening/understand.py`: `Extraction` (intent, language, consent, confirmation, question, faq_id, typed raw fields) and `extract(state, message, llm=, config=)`. `screening/prompts/extract.md` (rules plus 6 few-shot examples: multi-field, Mexican vocabulary, emoji with expired license, code-switch with FAQ, correction at confirm, injection). `screening/locale.py` (candidate country/timezone) | `uv run pytest tests/engine` (98 pass). Live probe on Haiku 5.5: 8/8 correct; cache read 5,068 of ~5,200 input tokens; ~1.3 s per call (the first call after a schema change took 34 s) | d5c0e5c |

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
None (cache-token request done as CONTRACTS v2, D14)

## Notes for other lanes
- E1 is in (56b5071): `from screening.schemas import ...` and `from screening.config import load_config`.
- `ScreeningConfig.timezone_for("ES"|"MX")` gives the IANA zone.
- After `DEMO_TIME_SCALE`, `reminder_schedule` and `abandon_after` are already scaled timedeltas, and `config.time_scale` holds the factor. Quiet hours are not scaled (wall-clock rule).
- LLM: `from screening.llm import AnthropicClient, FakeLLM, LLMError`. `FakeLLM({"extract": [...], "compose": lambda system, messages: "..."})`. Engine purposes: `extract`, `compose`, `summary`.
- Validators: `from screening.validators import match_city, validate_*`. Evals can reuse `match_city` to score city answers.
- Evals: the first extract call after a schema change can take ~30 s (one-off). Don't count it in latency stats, or warm up first.
- FAQ answers flagged `placeholder: true` are client terms to replace before launch.

## Prep notes (engine-internal)
E3: Anthropic API facts, checked 2026-10-12 against the current claude-api reference, not from memory:
- Structured output: `client.messages.parse(..., output_format=PydanticModel)` returns a validated `response.parsed_output`. The old top-level `output_format` param on `messages.create` is deprecated; the raw form is `output_config={"format": {"type": "json_schema", ...}}`. We use `parse`, not forced tool use: forced `tool_choice` returns a 400 on Sonnet 5.5.
- Haiku 5.5 / Sonnet 5.5: no `temperature`/`top_p` (400 unless default), no assistant prefill (400), thinking adaptive by default. Set `output_config={"effort": "low"}` for extract/compose to keep latency down; Haiku's default effort is `medium`. Thinking can't be turned off on Sonnet 5.5 (`disabled` → 400).
- Always check `stop_reason`: `refusal` (no server-side fallback on Haiku 5.5) and `max_tokens` → treat as `LLMError`.
- Prompt caching: the minimum cacheable prefix on Haiku 5.5 / Sonnet 5.5 is 512 tokens. Put `cache_control: {"type": "ephemeral"}` on the static system block. Keep the system prompt byte-stable: no timestamps or per-candidate data in it, since state goes in messages. Verify with `usage.cache_read_input_tokens`; record cache read tokens in the `llm_call` event too.
- SDK retries: the SDK retries 408/409/429/5xx itself (`max_retries`, default 2). Set `max_retries=3`, plus a per-client `timeout` (e.g. 20s), and map final errors to `LLMError`. A schema-validation failure gets one retry of our own.
- `anthropic` 1.x is built on httpx2. Don't import httpx directly.
