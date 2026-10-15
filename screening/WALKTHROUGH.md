# Walkthrough: two messages through the v4 engine

Two real turns, traced through the current code with `file:line` references. The
events, plans and stored values below are the actual output of running these
messages through `screening.engine` with `FakeLLM` scripted to return the
extraction shown (2026-10-15). The architecture overview is in `README.md`; this
file is for explaining the code line by line.

## Trace 1: a driver candidate answers two questions at once

The candidate has just received the opening ("¿Empezamos?") and replies:

> sí, soy Laura Pérez y tengo carnet de coche

### 1. The engine receives it: `engine.py:86` `handle_message`

- A deep copy of the state gets the bookkeeping that holds whatever happens next:
  `last_inbound_at`, `reminders_sent = 0`, and the message appended to
  `transcript_tail`.
- `engine.py:96`: if the candidate had opted out, return now; nothing is ever sent
  after an opt-out. Media without text would also be answered here, without an
  LLM call.

### 2. Extract: `engine.py:106` → `understand.py:143` `extract`

- `config.vacancy("driver")` loads the job; `extraction_model(vacancy)`
  (`understand.py:67`) returns the Extraction schema for this job, built once with
  `create_model`: one optional key per asked field, each typed by
  `fields.raw_type` (`fields.py:55`). For `driver` that is `full_name: str`,
  `has_driver_license: Literal["yes","no","expired","in_progress","foreign","vague"]`,
  `location: str`, `availability: list[Literal["full_time","part_time","weekends"]]`,
  and so on. Constrained decoding means the model can only return those keys and
  values.
- `system_prompt` (`understand.py:82`) fills `prompts/extract.md` with the job
  title, the field list and the FAQ catalogue. It is identical for every driver
  conversation, so it is cached.
- `user_prompt` (`understand.py:116`) carries everything conversation-specific:
  "Asking for: consent" (`asking_for`, `understand.py:101`), the country, the
  candidate's local date and weekday, the recent transcript, and the message
  inside `<candidate_message>`, marked as data.
- The model returns:
  `{"intent": "answer", "language": "es", "consent": "yes", "fields": {"full_name": "Laura Pérez", "has_driver_license": "yes"}}`

### 3. Decide: `engine.py:108` → `policy.py:145` `decide`

`decide` copies the state and runs `_Turn.run` (`policy.py:190`), the transition
table at the top of `policy.py`, top to bottom:

- Not opted out, not abandoned, not finished; intent isn't opt-out, human request,
  off-topic or abuse (rows 5–8).
- Stage is CONSENT and consent is "yes" (row 10): `consent_at` is set
  (`policy.py:211`) and `consent_given` logged.
- No out-of-area city pending, not at the read-back, so `collect` (`policy.py:291`)
  → `apply_given` (`policy.py:304`), which walks the job's fields in policy order
  (`vacancy.asked`: required first, then preferred).
- `full_name` → `apply_name` (`policy.py:341`). No partial first name is waiting,
  so `fields.validate` → `validate_name` sees two words → accept. `settle`
  (`policy.py:383`) → `store` (`policy.py:414`) sets value, status `accepted` and
  `source_message_id`, logs `field_accepted`, and adds "name: Laura Pérez" to what
  the reply should acknowledge.
- `has_driver_license` → `apply` (`policy.py:318`) → `validate_boolean("yes")` →
  accept `True`. `is_knockout` (`fields.py:69`) is only true for `False`, so this
  isn't the knockout branch at `policy.py:332`. Settled and acknowledged.
- `next_step` (`policy.py:445`) → `next_field` (`policy.py:459`): the first required
  field still missing is `location`. The stage becomes COLLECTING with
  `current_field = "location"` (logged as `stage_entered`).
- `reply` (`policy.py:497`) builds a `ReplyPlan`, with the ask from `field_ask`
  (`policy.py:528`): the field's `label` in Spanish, plus localized options for an
  options field.
- Back in `decide`, `preference_score` is recomputed (`policy.py:155`): 0.0, since
  `driver` has no preferred fields.

### 4. Render: `engine.py:113` → `compose.py:111` `compose_reply`

The plan, as code wrote it (`compose.instructions`, `compose.py:52`):

```
1. Briefly acknowledge what they just told you: name: Laura Pérez; has_driver_license: yes.
2. Ask for: location. Ask about: en qué ciudad vive, y el barrio.
```

The model turns it into Alex's words; the guard (`guard.py:26` `check_reply`) checks
≤300 characters, ≤2 sentences, exactly one question and it comes last, ≤1 emoji,
plain text. A failing draft is regenerated once with the broken rules quoted
back, then trimmed (`guard.py:50`) if it still fails.

### 5. The result

```
events:  llm_call(extract), consent_given, field_accepted(full_name),
         field_accepted(has_driver_license=True),
         stage_entered(collecting, location), llm_call(compose)
state:   stage=collecting, current_field=location, preference_score=0.0
reply:   "Genial, Laura. ¿En qué ciudad vives y en qué barrio?"
```

Two questions answered in one message, so the candidate skipped ahead. The model
read the message and wrote the reply; every decision in between was code.

## Trace 2: a kitchen candidate without a license

Same engine, `vacancy_id = "kitchen_prep"`. The candidate has answered every
required field (name, city, availability, schedule, start date), so `next_field`
moved on to the preferred ones, and Alex asked about the license, marked optional.
The candidate replies:

> no, no tengo carnet

- Extraction returns `{"has_driver_license": "no"}`.
- `apply` (`policy.py:318`): `validate_boolean("no")` → accept `False`.
  `is_knockout` is true, but the field's `requirement` is `preferred`, so the
  knockout branch at `policy.py:332` doesn't run (CONTRACTS §7, rule 4). The value
  is stored like any other: `field_accepted(has_driver_license=False)`.
- `next_field` → `food_handler_certificate`, the next preferred field. A preferred
  field is asked once: had the candidate not answered, `fail` (`policy.py:423`)
  would only record that it was asked, with no re-ask, no flag and no review reason.
- `preference_score` (`scoring.py:35`) counts accepted preferred fields only: a
  `False` license scores 0, so the score stays 0.0. Had they said yes, it would be
  1.5 (the field's `weight` in `kitchen_prep.yaml`).

The plan:

```
1. Briefly acknowledge what they just told you: has_driver_license: no.
2. Ask for: food_handler_certificate. Ask about: si tiene el carnet de manipulador
   de alimentos (no es obligatorio). This question is optional for this job.
```

The same "no" in the `driver` job would have taken the knockout branch: status
`disqualified`, `disqualify_reason = "no_license"` (from the field's `reason`), and
the fixed `close_knockout` message naming the requirement, never judging the person.
That difference is the whole of D25, and it comes from one YAML line:
`requirement: required` vs `requirement: preferred`.

## When the screening ends

- The read-back is fixed text (`messages.py:144` `readback` → `messages.py:148`
  `summarize`), so it can't misstate a value. A "yes" closes the screening
  (`policy.py:476` `finish`): `needs_review` if any field is flagged or a review
  reason exists, otherwise `qualified`. A restatement counts as a "yes"; real
  corrections and bare "no"s are rounds capped by `another_round`
  (`policy.py:280`), then `needs_review` + `unresolved:confirm` (D28).
- `engine.py:129` `_write_summary`: the smart tier writes the recruiter note, given
  the job title and the final record. If it fails, `summary` is `None` with an
  `llm_error`, and the close is still sent.
- `record.py:13` `final_record` builds the JSON: accepted fields under `"fields"`,
  flagged ones under `"flags"` with their notes, plus `preference_score`.

## When the LLM fails

`AnthropicClient` (`llm/anthropic_client.py`) retries with the SDK's backoff,
treats a refusal or a cut-off answer as a failure (`_check_stop`, line 115), and
raises `LLMError`. `engine.py:123` catches exactly that: the candidate gets the
fixed holding reply ("¿Me lo puedes repetir?"), an `llm_error` event is logged,
and the screening state (profile, stage, status, attempts) is unchanged, so the
candidate's next message simply works. This ran for real when the API account ran
out of credits: every turn degraded to the holding reply, nothing was lost.
