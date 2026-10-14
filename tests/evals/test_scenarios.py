import pytest
import yaml

from evals.scenario import SCENARIOS_DIR, Scenario, check_against_config, load_all
from screening.config import load_config

# BOARD V1: every one of these must be exercised by at least one scenario.
REQUIRED_COVERAGE = {
    "happy_path", "es_spain_vocabulary", "es_mexico_vocabulary", "english",
    "code_switching", "multi_field_message", "correction_at_confirm", "vague_start_date",
    "faq_question", "emoji_answers", "voice_note",
    "knockout_no_license", "knockout_out_of_area", "ambiguous_city", "license_unclear",
    "prompt_injection", "abuse", "silence", "quiet_hours",
    "unresolved_field", "human_request", "opt_out", "abandonment", "sensitive_details",
    # BOARD V7: the kitchen_prep vacancy
    "preferred_not_knockout", "preferred_asked_once", "preference_tiebreak",
    "required_knockout_generic",
}  # fmt: skip


@pytest.fixture(scope="module")
def scenarios() -> list[Scenario]:
    return load_all()


def test_suite_size_and_ids(scenarios: list[Scenario]) -> None:
    assert 20 <= len(scenarios) <= 25
    files = sorted(p.stem for p in SCENARIOS_DIR.glob("*.yaml"))
    assert [s.id for s in scenarios] == files
    assert len({s.seed for s in scenarios}) == len(scenarios)


def test_coverage(scenarios: list[Scenario]) -> None:
    covered = {tag for s in scenarios for tag in s.covers}
    assert REQUIRED_COVERAGE <= covered, REQUIRED_COVERAGE - covered


def test_every_outcome_is_exercised(scenarios: list[Scenario]) -> None:
    assert {s.expected_status for s in scenarios} == {
        "qualified", "needs_review", "disqualified", "abandoned", "opted_out",
    }  # fmt: skip


def test_phone_prefix_matches_country(scenarios: list[Scenario]) -> None:
    for s in scenarios:
        assert s.phone.startswith({"ES": "+34", "MX": "+52"}[s.country]), s.id


def test_both_vacancies_are_screened(scenarios: list[Scenario]) -> None:
    assert {s.vacancy for s in scenarios} == {"driver", "kitchen_prep"}


def _base() -> dict:
    return yaml.safe_load((SCENARIOS_DIR / "01_es_happy_madrid.yaml").read_text(encoding="utf-8"))


def _fields(**changes: object) -> dict:
    return {"fields": {**_base()["expected"]["fields"], **changes}}


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"expected_status": "disqualified"}, "differs from expected_status"),
        ({"expected": {"flags": ["location"]}}, "flagged fields imply needs_review"),
        ({"starts_at": "2026-10-20T11:05:00"}, "UTC offset"),
        ({"script": [{"when": {"turn": 1, "step": "full_name"}, "text": "hola"}]}, "exactly one"),
        # Checked against the real vacancy and service-area config:
        ({"expected": _fields(location={"country": "ES", "city": "zaragoza"})}, "not a served"),
        ({"expected": _fields(start_date="2026-01-01")}, "outside 0-183"),
        ({"expected": _fields(schedule=["flexible", "morning"])}, "stand alone"),
        ({"expected": _fields(shoe_size="42")}, "not a field of driver"),
        ({"expected": {"fields": {"full_name": "Carlos Méndez Ruiz"}}}, "every required field"),
        ({"expected": {"preference_score": 1.5}}, "the formula gives 0.0"),
        ({"script": [{"when": {"step": "name"}, "text": "hola"}]}, "step 'name' is not one"),
        ({"vacancy": "astronaut"}, "unknown vacancy"),
    ],
)
def test_inconsistent_ground_truth_is_rejected(patch: dict, message: str) -> None:
    data = _base()
    for key, value in patch.items():
        data[key] = {**data[key], **value} if key == "expected" else value
    with pytest.raises(ValueError, match=message):
        scenario = Scenario.model_validate(data)
        problems = check_against_config(scenario, load_config())
        raise ValueError("; ".join(problems))


def test_tiebreak_pair_differs_only_on_a_preferred_field(scenarios: list[Scenario]) -> None:
    by_id = {s.id: s for s in scenarios}
    a = by_id["22_kitchen_tiebreak_with_license_guadalajara"].expected
    b = by_id["23_kitchen_tiebreak_no_license_guadalajara"].expected
    differing = {k for k in a.fields.keys() | b.fields.keys() if a.fields.get(k) != b.fields.get(k)}
    assert differing == {"full_name", "has_driver_license"}
    assert a.status == b.status == "qualified"
    assert a.preference_score > b.preference_score
