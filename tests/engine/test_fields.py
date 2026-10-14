from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from screening.config import FieldSpec, load_config
from screening.fields import ExperienceAnswer, is_knockout, raw_type, typed, validate
from screening.schemas import ExperienceItem, FieldStatus, FieldValue, Location
from screening.scoring import preference_score, score_breakdown
from screening.validators import StartDateAnswer, validate_boolean, validate_options

CONFIG = load_config()
DRIVER = CONFIG.vacancy("driver")
KITCHEN = CONFIG.vacancy("kitchen_prep")
TODAY = date(2026, 10, 14)


def check(spec: FieldSpec, raw, surname_asked=False):
    return validate(spec, raw, today=TODAY, max_days=183, surname_asked=surname_asked)


# Generic validators


def test_boolean_yes_no_and_unclear():
    assert validate_boolean("yes", name="license").value is True
    assert validate_boolean("no", name="license").value is False
    assert validate_boolean("vague", name="license").outcome == "reask"
    flagged = validate_boolean("expired", name="license")
    assert (flagged.outcome, flagged.note) == ("flag", "license expired")


def test_options_keep_display_order_and_drop_duplicates():
    verdict = validate_options(
        ["weekends", "part_time", "weekends"],
        options=DRIVER.field("availability").options,
        exclusive=[],
    )
    assert verdict.value == ["part_time", "weekends"]


def test_exclusive_option_stands_alone():
    schedule = DRIVER.field("schedule")
    verdict = validate_options(
        ["morning", "flexible"], options=schedule.options, exclusive=schedule.exclusive_options
    )
    assert verdict.value == ["flexible"]


def test_no_option_is_reasked():
    assert validate_options([], options=["a"], exclusive=[]).outcome == "reask"


# Catalog


def test_enum_raw_type_only_allows_the_fields_options():
    adapter = TypeAdapter(raw_type(DRIVER.field("schedule")))
    assert adapter.validate_python(["morning"]) == ["morning"]
    with pytest.raises(ValidationError):
        adapter.validate_python(["weekends"])  # an availability option, not a schedule one


def test_typed_restores_values_after_a_json_round_trip():
    assert typed(DRIVER.field("location"), {"country": "ES", "city": "madrid"}) == Location(
        country="ES", city="madrid"
    )
    assert typed(DRIVER.field("start_date"), "2026-10-19") == date(2026, 10, 19)
    assert typed(DRIVER.field("experience"), [{"platform": "glovo", "years": 1.5}]) == [
        ExperienceItem(platform="glovo", years=1.5)
    ]
    assert typed(DRIVER.field("start_date"), None) is None


def test_only_a_boolean_no_is_a_knockout_value():
    assert is_knockout(DRIVER.field("has_driver_license"), False)
    assert not is_knockout(DRIVER.field("has_driver_license"), True)
    assert not is_knockout(DRIVER.field("availability"), [])


def test_validate_dispatches_by_type():
    assert check(DRIVER.field("full_name"), "Laura", surname_asked=False).outcome == "reask"
    assert check(DRIVER.field("has_driver_license"), "expired").note == "license expired"
    assert check(DRIVER.field("schedule"), ["evening"]).value == ["evening"]
    assert check(DRIVER.field("experience"), ExperienceAnswer(has_experience=False)).value == []
    listed = ExperienceAnswer(
        items=[{"platform": "Glovo", "months": 6}]
    )  # listing implies experience
    assert check(DRIVER.field("experience"), listed).value == [
        ExperienceItem(platform="glovo", years=0.5)
    ]
    assert check(DRIVER.field("start_date"), StartDateAnswer(kind="asap")).value == TODAY


def test_city_is_left_to_the_policy():
    with pytest.raises(ValueError, match="policy"):
        check(DRIVER.field("location"), "Madrid")


# Preference score


def accepted(value) -> FieldValue:
    return FieldValue(value=value, status=FieldStatus.ACCEPTED)


def test_driver_has_no_preferred_fields_so_scores_zero():
    assert preference_score(DRIVER, {"has_driver_license": accepted(True)}) == 0.0


def test_kitchen_license_and_certificate_add_their_weights():
    fields = {"has_driver_license": accepted(True), "food_handler_certificate": accepted(True)}
    assert score_breakdown(KITCHEN, fields) == {
        "has_driver_license": 1.5,
        "food_handler_certificate": 1.0,
    }
    assert preference_score(KITCHEN, fields) == 2.5


def test_a_no_or_a_missing_preferred_field_scores_zero():
    assert preference_score(KITCHEN, {"has_driver_license": accepted(False)}) == 0.0
    assert preference_score(KITCHEN, {}) == 0.0
    flagged = FieldValue(status=FieldStatus.FLAGGED, note="license expired")
    assert preference_score(KITCHEN, {"has_driver_license": flagged}) == 0.0


def test_experience_and_options_formulas():
    vacancy = KITCHEN.model_copy(
        update={
            "fields": [
                FieldSpec(
                    name="exp",
                    type="experience",
                    requirement="preferred",
                    weight=0.5,
                    label={"es": "x"},
                ),
                FieldSpec(
                    name="shift",
                    type="enum_multi",
                    requirement="preferred",
                    weight=2.0,
                    options=["a", "b"],
                    label={"es": "x"},
                ),
            ]
        }
    )
    many_years = [{"platform": "glovo", "years": 12}, {"platform": "rappi", "years": 3}]
    fields = {"exp": accepted(many_years), "shift": accepted(["b"])}
    assert score_breakdown(vacancy, fields) == {"exp": 2.5, "shift": 2.0}  # years capped at 5
