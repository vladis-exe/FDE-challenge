# Evals

Simulated candidates screen against the real engine, in memory, on a fake clock. Each run
is scored against exact ground truth.

```bash
uv run python -m evals.run --suite smoke     # 6 scenarios, ~50 s, ~$0.12: run after any prompt change
uv run python -m evals.run                   # all 24 scenarios, ~5 min, ~$0.50
uv run python -m evals.run --only 13_expired_license_bilbao
uv run python -m evals.run --name haiku --fast-model claude-haiku-5-5   # a named, committable report
uv run python -m evals.run --fake            # offline plumbing check: no API key, no cost
```

`DEMO_TIME_SCALE` must be unset: the fake clock already skips the waiting. The command
exits non-zero if any scenario fails.

## How a run works

1. **Scenario** (`scenarios/*.yaml`, schema in `scenario.py`): the vacancy it screens for
   (`driver` or `kitchen_prep`), a persona, the facts the candidate knows, how they write,
   and the exact record the engine must produce, including the preference score. Loading a
   scenario checks that ground truth against the real vacancy and service-area config. The
   fake clock starts at `starts_at`, so relative dates ("el lunes que viene") have one right
   answer. Scripted turns and pauses fire at a step: `consent`, a field name, or `confirm`.
2. **Simulator** (`simulator.py`): Sonnet 5.5 plays the candidate. It writes short messages
   with typos and slang, sometimes answers two things at once, and sometimes sidetracks.
   The moments a run must not skip (an injection, a voice note, a correction at the
   read-back) are scripted verbatim. Pauses tick `handle_tick` through reminders and quiet
   hours. Current models take no sampling seed, so a seeded RNG decides typing delays and
   style quirks; that is what makes runs comparable.
3. **Scoring** (`scoring.py`): every score has a one-sentence definition, printed in the
   report next to the number.
4. **Output**: `runs/<timestamp>/` (gitignored) has a JSON and a Markdown transcript per
   scenario, `scores.json` and `report.md`. With `--name`, the report and its transcripts
   are also written to `reports/`, to commit.

The candidate's own LLM cost is not counted in cost per conversation; it adds ~$0.015 per
scenario to the bill.
