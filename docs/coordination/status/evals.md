# Status: evals

Last updated: 2026-10-12

## Current task
None. V1 done. V2 (simulator) starts once `status/engine.md` shows E9 (CLI) done; E1 and E3 are in. Meanwhile I'm drafting the persona-simulator prompt and the runner skeleton against CONTRACTS §2.

## Done
| Task | What changed | How to verify | Commit |
| --- | --- | --- | --- |
| V1 | 20 scenarios in `evals/scenarios/*.yaml` covering every BOARD V1 case plus unresolved field, human request, opt-out, abandonment and sensitive details. All 5 outcomes are exercised. `evals/scenario.py` holds the Pydantic schema (persona, facts, behaviors, seeded scripted turns, pauses, checks, the `expected` record with `final_record` keys) and validators that reject inconsistent ground truth. Every expected date is exact, given the fake-clock `starts_at`. Dropped the empty `tests/evals/__init__.py`, which shadowed the top-level `evals` package. | `uv run pytest tests/evals -q` (11 pass); `uv run ruff check evals tests/evals` | 46ad528, (this commit) |

## Blocked
None

## Requests (to other lanes or the lead)
- **Lead (FYI):** `tests/evals/__init__.py` made pytest import the test dir as package `evals` (prepend mode puts `tests/` first on `sys.path`, ahead of `pythonpath = ["."]`), which shadowed the real `evals/`. I removed it, so it's fixed for my lane. An empty `tests/__init__.py` would be the general fix if any other test dir ever collides with a top-level package name.

## Contract change requests
None

## Notes for other lanes
- **Engine, ground-truth assumptions in the scenarios** (all from the spec plus D13; tell me if E5 differs and I'll adapt the scorer rather than the engine):
  - An unclear license is stored as `has_driver_license: null` with a flag and `license_unclear` (scenario 13).
  - Human request closes at once with `needs_review` and `human_requested` (18).
  - Abuse: one redirect, then close with `needs_review` and `abuse` (15).
  - Injection is a strike like off-topic, and the outcome still comes from the answers (14).
  - `review_reasons` strings: `license_unclear`, `unresolved:<field>`, `human_requested`, `abuse`.
- **Engine, `service_areas.yaml` (11_out_of_area_zaragoza):** "Zaragoza" is a substring of puebla's alias "Puebla de Zaragoza". With an ES phone hint, it must come back `not_served`, not a fuzzy match to puebla.
- **Engine, `service_areas.yaml` (12_ambiguous_city_san_pedro):** "san pedro" is meant to be ambiguous. Only monterrey has "San Pedro Garza García" today. Adding "San Pedro Cholula" to puebla's neighborhoods (a real Puebla-metro town) would make the matcher return `ambiguous` here. The expected outcome is monterrey either way.
- **Engine, FAQ (08):** the scenario assumes `faq.yaml` keeps covering pay and does not cover private health insurance.
