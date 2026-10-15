# The screening engine (`screening/`)

A pure-Python engine that screens a job applicant one message at a time. It takes
the conversation state plus one inbound message and returns the new state, the
messages to send and the events to log. It has no Django and no I/O except the LLM
client it is handed, so the same code runs behind WhatsApp, the web chat, the CLI
and the evals.

**Code owns the process; the LLM owns the language.** The model reads messy
answers and phrases replies. Every eligibility decision, stage change and outcome
is made by code from validated values (DECISIONS D3), so nothing a candidate writes
to the model can change an outcome.

## One turn

```
inbound message
   │
   ├─ opted out? media without text? ──▶ answered by code, no LLM call
   │
   ▼
extract      (LLM, fast tier)   the message as a typed Extraction: intent,
   │                            language, and a raw answer per field of this job
   ▼
decide       (code, policy.py)  validate each answer, apply the transition
   │                            table, choose what to say next
   ▼
render       fixed text (messages.yaml) when the words carry legal or outcome
   │         meaning; otherwise compose (LLM, fast tier) phrases code's plan,
   │         then the guard checks the message rules (regenerate once, then trim)
   ▼
TurnResult   new state, outbound messages, events (one llm_call per model call)
```

If any LLM call fails after retries, the candidate gets a fixed "could you say that
again?" reply and the screening state is left as it was, so repeating works.
When a screening ends, the smart tier writes a short note for the recruiter.

## Modules

| Module | What it does |
| --- | --- |
| `engine.py` | The public API (CONTRACTS §2): `new_conversation`, `start`, `handle_message`, `handle_tick`, `next_due_at`. Runs one turn as above. |
| `policy.py` | The state machine. Starts with the transition table (a docstring, written before the code); `decide()` is pure and makes no LLM calls. |
| `understand.py` | Extraction: builds the per-vacancy `Extraction` schema and the prompt context. |
| `compose.py` | `ReplyPlan` → Alex's message, with the guard's regenerate-then-trim loop. |
| `guard.py` | The message rules in code: ≤300 characters, ≤2 sentences, one question and it comes last, ≤1 emoji, plain text. |
| `messages.py` | Fixed messages (`prompts/messages.yaml`) and the read-back of stored answers, both deterministic. |
| `fields.py` | The field-type catalog: per type, the raw answer shape, the stored value, knockout values, validation. |
| `scoring.py` | The preference score and its per-field breakdown (a tie-breaker, never a gate). |
| `record.py` | `final_record(state)`: the final JSON for recruiters and evals, no LLM. |
| `summary.py` | The recruiter note, written once a screening ends. |
| `timers.py` | Reminders (15 min, 2 h, 20 h), quiet hours (21:00–09:00 local), abandonment at 24 h. |
| `locale.py` | The candidate's country and time zone. |
| `validators/` | Pure checks: city matching, names, yes/no, options, experience, start dates. |
| `llm/` | `LLMClient` protocol, `AnthropicClient`, `FakeLLM` for tests, `pricing.py` (cost per `llm_call`). |
| `config/` | `screening.yaml` (timings, limits), `service_areas.yaml`, `faq.yaml`, `vacancies/*.yaml`. |
| `prompts/` | The three LLM prompts and the fixed messages, as readable files (see below). |
| `cli.py` | Run a screening in the terminal. |

## Vacancies: which questions a job asks

Each job is a YAML file in `config/vacancies/` (CONTRACTS §7). It picks fields from
a small, closed catalog of field types; adding a type is an engineering change,
adding or reconfiguring a job is not.

| Type | Answer | Knockout when required? |
| --- | --- | --- |
| `text` | a name (one soft re-ask for the surname) | no |
| `boolean` | yes / no; expired, in progress or foreign → recruiter review | yes: "no" |
| `city` | a served city, from `service_areas.yaml` | yes: a city we don't serve, once confirmed |
| `enum_multi` | one or more of the field's `options` | no |
| `experience` | platforms and how long; none is valid | no |
| `date` | a start date, at most 183 days ahead | no |

Each field is `required`, `preferred` or `off`:

- **required**: asked first, in the file's order. A bad answer gets up to 2
  re-asks, then the field is flagged for review and the conversation moves on. A
  knockout answer disqualifies at once.
- **preferred**: asked once, after every required field, and marked as optional
  to the candidate. Whatever comes back is kept for the preference score; it is
  never re-asked, never flagged, and never disqualifies (a "no license" for
  `kitchen_prep` is just a 0).
- **off**: not asked.

Two jobs ship: `driver` (the original seven fields, all required, license and city
are knockouts) and `kitchen_prep` (no delivery experience; the license is preferred,
weight 1.5, and a food handler certificate is preferred, weight 1.0).

### Adding a job

1. Copy `config/vacancies/kitchen_prep.yaml` to `<id>.yaml`; the `id` must match
   the file name.
2. List its fields with a `type`, a `requirement` and a `label` (what to ask, in
   `es` and `en`). Optionally: `weight` (preferred only), `options` (enum_multi),
   `reason` (the name used in outcome strings, e.g. `license` gives `no_license`),
   `summary` (how the read-back introduces the value), `option_labels` (display
   text per option), `exclusive_options` (options that stand alone, like
   `flexible`). `summary` and `option_labels` accept `es_ES` / `es_MX` overrides
   for country vocabulary.
3. `uv run pytest tests/engine` (the loader rejects inconsistent specs), then
   `uv run python -m screening.cli --fake --vacancy <id>`.

No prompt or code changes are needed: the extraction schema and prompt are built
from the file.

## Prompts

All prompts live in `prompts/`, each opening with a comment that says what it is
for (the comment is stripped before sending).

| File | Model | Purpose |
| --- | --- | --- |
| `extract.md` | fast | Read one message into a typed record. Rules by field type, the job's field list, the FAQ catalogue, examples. |
| `compose.md` | fast | Alex's persona and message rules; turns code's plan into a reply. |
| `summary.md` | smart | The recruiter note. |
| `messages.yaml` | none | Every word-for-word message: the opening (AI disclosure, privacy link), read-back, closes, holding reply, media reply, reminders. |

System prompts are byte-stable per job, and everything conversation-specific goes
in the user message, so prompt caching works: about 5,000 of 5,200 extraction
input tokens are read from cache.

## Running and testing

```bash
uv run pytest tests/engine                       # 269 tests, no network (FakeLLM)
uv run python -m screening.cli --fake            # no API key needed
uv run python -m screening.cli --country MX --script tests/engine/scripts/demo_mx.txt
uv run python -m screening.cli --vacancy kitchen_prep --script tests/engine/scripts/demo_kitchen.txt
```

The CLI prints Alex's replies, the state diff and the events of each turn, then the
final record. The state-machine tests round-trip the state through JSON before
every turn, as the app does, so they exercise the stored shapes.

## Known limits

- A two-word first name alone ("Soy Luis Ángel", "José Luis") counts as a full name, so
  no surname is asked for (seen live in V11 scenario 10). Code can't tell "Luis Ángel"
  from "Luis Pérez" without guessing which words are surnames, and the spec says no
  format policing on names; the cost is an occasional record without a surname, which
  the recruiter fills in on the call.
- Experience on a platform outside the known list is stored as `other`; the
  name the candidate gave isn't kept (CONTRACTS §1).
- A "stop" that is also an insult ("pinche bot, ya deja de preguntar") is honored
  as an opt-out: a request to stop always wins.
- Field labels are written once per language; Mexican vocabulary comes from
  `option_labels`/`summary` overrides and the compose prompt.

Decisions behind the design: DECISIONS.md D3, D12, D18–D22, D25, D28–D29, D32–D34.
