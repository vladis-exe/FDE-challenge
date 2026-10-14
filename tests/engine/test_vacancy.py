import pytest
from pydantic import ValidationError

from screening.config import FieldSpec, VacancyConfig, load_config
from screening.llm.pricing import call_cost


@pytest.fixture(scope="module")
def config():
    return load_config()


def spec(**values) -> dict:
    return {
        "name": "f",
        "type": "boolean",
        "requirement": "required",
        "label": {"es": "x"},
    } | values


def test_both_vacancies_load(config):
    assert set(config.vacancies) == {"driver", "kitchen_prep"}


def test_unknown_vacancy_lists_the_valid_ids(config):
    with pytest.raises(KeyError, match="driver, kitchen_prep"):
        config.vacancy("astronaut")


def test_driver_keeps_the_original_seven_required_fields_in_order(config):
    driver = config.vacancy("driver")
    assert [f.name for f in driver.asked] == [
        "full_name", "has_driver_license", "location", "availability",
        "schedule", "experience", "start_date",
    ]  # fmt: skip
    assert {f.requirement for f in driver.fields} == {"required"}
    assert driver.field("has_driver_license").outcome_name == "license"
    assert driver.field("schedule").exclusive_options == ["flexible"]


def test_kitchen_prep_asks_preferred_fields_after_required_ones(config):
    kitchen = config.vacancy("kitchen_prep")
    asked = kitchen.asked
    license = kitchen.field("has_driver_license")
    assert license.requirement == "preferred"
    assert license.weight == 1.5
    first_preferred = next(i for i, f in enumerate(asked) if f.requirement == "preferred")
    assert all(f.requirement == "preferred" for f in asked[first_preferred:])
    assert "experience" not in {f.name for f in kitchen.fields}


def test_off_fields_are_never_asked():
    vacancy = VacancyConfig(
        id="v", title={"es": "v"}, fields=[spec(name="a"), spec(name="b", requirement="off")]
    )
    assert [f.name for f in vacancy.asked] == ["a"]


@pytest.mark.parametrize("field_type", ["text", "city"])
def test_text_and_city_cannot_be_preferred(field_type):
    with pytest.raises(ValidationError, match="can't be preferred"):
        FieldSpec(**spec(type=field_type, requirement="preferred"))


@pytest.mark.parametrize(
    "values",
    [
        {"type": "enum_multi"},  # no options
        {"options": ["a"]},  # options on a boolean
        {"type": "enum_multi", "options": ["a"], "exclusive_options": ["b"]},
        {"weight": 1.0},  # weight on a required field
    ],
)
def test_inconsistent_field_specs_are_rejected(values):
    with pytest.raises(ValidationError):
        FieldSpec(**spec(**values))


def test_duplicate_field_names_are_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        VacancyConfig(id="v", title={"es": "v"}, fields=[spec(), spec()])


def test_call_cost_is_cache_aware():
    data = {
        "model": "claude-haiku-5-5",
        "input_tokens": 5_000,
        "cache_read_tokens": 4_000,
        "cache_write_tokens": 0,
        "output_tokens": 100,
    }
    # 1,000 uncached at $0.10/M + 4,000 cached at $0.01/M + 100 out at $0.50/M
    assert call_cost(data) == pytest.approx((1_000 * 0.10 + 4_000 * 0.01 + 100 * 0.50) / 1e6)
    assert call_cost({**data, "model": "unknown"}) == 0.0
