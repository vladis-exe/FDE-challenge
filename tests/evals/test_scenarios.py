import pytest
import yaml
from pydantic import ValidationError

from evals.scenario import SCENARIOS_DIR, Scenario, load_all

# BOARD V1: every one of these must be exercised by at least one scenario.
REQUIRED_COVERAGE = {
    "happy_path", "es_spain_vocabulary", "es_mexico_vocabulary", "english",
    "code_switching", "multi_field_message", "correction_at_confirm", "vague_start_date",
    "faq_question", "emoji_answers", "voice_note",
    "knockout_no_license", "knockout_out_of_area", "ambiguous_city", "license_unclear",
    "prompt_injection", "abuse", "silence", "quiet_hours",
    "unresolved_field", "human_request", "opt_out", "abandonment", "sensitive_details",
}  # fmt: skip


@pytest.fixture(scope="module")
def scenarios() -> list[Scenario]:
    return load_all()


def test_suite_size_and_ids(scenarios: list[Scenario]) -> None:
    assert 15 <= len(scenarios) <= 20
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


def _base() -> dict:
    return yaml.safe_load((SCENARIOS_DIR / "01_es_happy_madrid.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"expected_status": "disqualified"}, "differs from expected_status"),
        ({"expected": {"city": "zaragoza"}}, "not a served city"),
        ({"expected": {"start_date": "2026-01-01"}}, "outside 0-183"),
        ({"expected": {"preferred_schedule": ["flexible", "morning"]}}, "flexible stands alone"),
        ({"expected": {"flags": ["location"]}}, "flagged fields imply needs_review"),
        ({"starts_at": "2026-10-20T11:05:00"}, "UTC offset"),
        ({"script": [{"when": {"turn": 1, "stage": "name"}, "text": "hola"}]}, "exactly one"),
    ],
)
def test_inconsistent_ground_truth_is_rejected(patch: dict, message: str) -> None:
    data = _base()
    for key, value in patch.items():
        data[key] = {**data[key], **value} if key == "expected" else value
    with pytest.raises(ValidationError, match=message):
        Scenario.model_validate(data)
