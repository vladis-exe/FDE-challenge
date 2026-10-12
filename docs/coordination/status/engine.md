# Status: engine

Last updated: 2026-10-12

## Current task
E3 LLM layer (next). E1 done.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| E1 | `screening/schemas.py` (verbatim from CONTRACTS §1). `screening/config/`: `load_config(path=None)` → `ScreeningConfig`, plus `screening.yaml`, `service_areas.yaml` (6 ES and 5 MX cities with aliases and neighborhoods), `faq.yaml` (6 entries, es+en, `placeholder: true` on client terms) | `uv run python -m pytest tests/engine -p no:django` (15 pass); `uv run ruff check screening tests/engine` | 56b5071 |

## Blocked
None

## Requests (to other lanes or the lead)
- **Lead, pytest config in `pyproject.toml`:**
  1. `DJANGO_SETTINGS_MODULE` is global, so `pytest tests/engine` imports `config.settings` and fails (needs `DJANGO_SECRET_KEY`). BOARD L1 says to scope it to `tests/app`. Suggested fix: drop it from `[tool.pytest.ini_options]` and set it in `tests/app/conftest.py` (or a `tests/app/pytest.ini`). Until then I run `-p no:django`.
  2. Add `pythonpath = ["."]`; plain `uv run pytest` can't import `screening`. Until then I use `uv run python -m pytest`.
- **Lead, ruff:** UP046 flags `class FieldValue(BaseModel, Generic[T])`, which is the contract's own syntax. I kept the contract syntax with `# noqa: UP046`. If you'd rather use `class FieldValue[T](BaseModel)` (it works with pydantic 2.14), update CONTRACTS §1 and I'll switch.

## Open spec questions (needed by E5; each has a proposed default)
1. **Consent declined:** which status? The spec says "close, nothing stored". *Proposal:* `opted_out`, empty profile, one close message.
2. **Out-of-area waitlist:** is the "waitlist offer" a sentence in the close ("we'll message you if we open in your city"), or a question whose yes/no we record? The schema has no field for it. *Proposal:* a sentence in the close; nothing recorded beyond the disqualify reason.
3. **Off-topic, abuse and injection strikes:** do all three share `offtopic_strikes`, with one redirect before close + `needs_review` (reasons `offtopic` / `abuse`)? *Proposal:* yes, shared counter, per the edge-case table.
4. **Human requested:** close at once with `needs_review` + `human_requested`, or keep screening? *Proposal:* close at once.
5. **Late reply after `abandoned`:** reopen to `in_progress` and resume? *Proposal:* yes, per "a late reply resumes where it stopped".
6. **Messages after a final outcome** (qualified, disqualified, etc.): *Proposal:* no state change, one short reply ("a recruiter will be in touch"), and FAQ answers still given. After `opted_out`, nothing is sent.
7. **Name with no surname after the one re-ask:** *Proposal:* accept it (status `accepted`, note "no surname given"), not flagged.
8. **License:** a vague answer ("bueno…") gets a yes/no re-ask. An explicit unclear case (expired, in progress, foreign) is flagged at once and screening continues. *Proposal:* as stated.

## Contract change requests
None

## Notes for other lanes
- E1 is in (56b5071): `from screening.schemas import ...` and `from screening.config import load_config`.
- `ScreeningConfig.timezone_for("ES"|"MX")` gives the IANA zone.
- After `DEMO_TIME_SCALE`, `reminder_schedule` and `abandon_after` are already scaled timedeltas, and `config.time_scale` holds the factor. Quiet hours are not scaled (wall-clock rule).
- FAQ answers flagged `placeholder: true` are client terms to replace before launch.

## Prep notes (engine-internal)
E3: Anthropic API facts, checked 2026-10-12 against the current claude-api reference, not from memory:
- Structured output: `client.messages.parse(..., output_format=PydanticModel)` returns a validated `response.parsed_output`. The old top-level `output_format` param on `messages.create` is deprecated; the raw form is `output_config={"format": {"type": "json_schema", ...}}`. We use `parse`, not forced tool use: forced `tool_choice` returns a 400 on Sonnet 5.5.
- Haiku 5.5 / Sonnet 5.5: no `temperature`/`top_p` (400 unless default), no assistant prefill (400), thinking adaptive by default. Set `output_config={"effort": "low"}` for extract/compose to keep latency down; Haiku's default effort is `medium`. Thinking can't be turned off on Sonnet 5.5 (`disabled` → 400).
- Always check `stop_reason`: `refusal` (no server-side fallback on Haiku 5.5) and `max_tokens` → treat as `LLMError`.
- Prompt caching: the minimum cacheable prefix on Haiku 5.5 / Sonnet 5.5 is 512 tokens. Put `cache_control: {"type": "ephemeral"}` on the static system block. Keep the system prompt byte-stable: no timestamps or per-candidate data in it, since state goes in messages. Verify with `usage.cache_read_input_tokens`; record cache read tokens in the `llm_call` event too.
- SDK retries: the SDK retries 408/409/429/5xx itself (`max_retries`, default 2). Set `max_retries=3`, plus a per-client `timeout` (e.g. 20s), and map final errors to `LLMError`. A schema-validation failure gets one retry of our own.
- `anthropic` 1.x is built on httpx2. Don't import httpx directly.
