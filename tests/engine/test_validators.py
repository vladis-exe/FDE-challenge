from datetime import UTC, date, datetime

import pytest

from screening.config import load_config
from screening.schemas import Availability, ExperienceItem, Location, Schedule
from screening.validators import (
    RawExperience,
    StartDateAnswer,
    local_date,
    match_city,
    validate_availability,
    validate_experience,
    validate_license,
    validate_name,
    validate_schedule,
    validate_start_date,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


# City matcher


@pytest.mark.parametrize(
    "text, country, city",
    [
        ("Barcelona", "ES", "barcelona"),
        ("barcelona", "ES", "barcelona"),
        ("BCN", "ES", "barcelona"),
        ("gracia", "ES", "barcelona"),  # neighborhood, accent dropped
        ("Gràcia, Barcelona", "ES", "barcelona"),  # neighborhood and city agree
        ("vivo en malasaña", "ES", "madrid"),
        ("Malaga", "ES", "malaga"),
        ("Sevilla, en Triana", "ES", "sevilla"),
        ("CDMX", "MX", "cdmx"),
        ("el DF", "MX", "cdmx"),
        ("Ciudad de México", "MX", "cdmx"),
        ("coyoacan", "MX", "cdmx"),
        ("Zapopan", "MX", "guadalajara"),
        ("san pedro garza garcia", "MX", "monterrey"),
        ("Querétaro", "MX", "queretaro"),
        ("Barcelna", "ES", "barcelona"),  # typo, fuzzy
        ("Guadalajra", "MX", "guadalajara"),  # typo, fuzzy
    ],
)
def test_matches_city_names_aliases_neighborhoods_and_typos(config, text, country, city):
    result = match_city(text, config)
    assert result.kind == "matched", result
    assert result.location == Location(country=country, city=city)


def test_two_different_cities_named_is_ambiguous(config):
    result = match_city("entre Madrid y Barcelona", config)
    assert result.kind == "ambiguous"
    assert {option.city for option in result.options} == {"madrid", "barcelona"}


def test_weak_fuzzy_match_offers_options_instead_of_guessing(config):
    result = match_city("Bilbaino", config)
    assert result.kind == "ambiguous"
    assert "bilbao" in {option.city for option in result.options}
    assert len(result.options) <= 3


@pytest.mark.parametrize("text", ["Zaragoza", "Tijuana", "Lisboa"])
def test_unknown_place_is_not_served(config, text):
    result = match_city(text, config)
    assert result.kind == "not_served"
    assert result.city_text == text


def test_blank_city_is_not_served(config):
    assert match_city("   ", config).kind == "not_served"


# License


def test_license_yes_and_no_are_accepted():
    assert validate_license("yes").outcome == "accept"
    assert validate_license("yes").value is True
    no = validate_license("no")
    assert no.outcome == "accept" and no.value is False


@pytest.mark.parametrize("answer", ["expired", "in_progress", "foreign"])
def test_unclear_license_is_flagged_with_a_note(answer):
    verdict = validate_license(answer)
    assert verdict.outcome == "flag"
    assert verdict.value is None
    assert verdict.note


def test_vague_license_answer_is_reasked():
    assert validate_license("vague").outcome == "reask"


# Name


def test_full_name_is_accepted_without_policing_format():
    verdict = validate_name("  laura   pérez ", surname_asked=False)
    assert verdict.outcome == "accept"
    assert verdict.value == "laura pérez"


def test_first_name_only_gets_one_soft_reask_then_is_accepted():
    assert validate_name("Laura", surname_asked=False).outcome == "reask"
    verdict = validate_name("Laura", surname_asked=True)
    assert verdict.outcome == "accept"
    assert verdict.value == "Laura"
    assert verdict.note == "no surname given"


@pytest.mark.parametrize("raw", ["", "  ", "123", "!!"])
def test_non_name_is_reasked(raw):
    assert validate_name(raw, surname_asked=True).outcome == "reask"


# Availability and schedule


def test_availability_combinations_are_kept_in_canonical_order():
    verdict = validate_availability([Availability.WEEKENDS, Availability.PART_TIME])
    assert verdict.outcome == "accept"
    assert verdict.value == [Availability.PART_TIME, Availability.WEEKENDS]


def test_empty_availability_is_reasked():
    assert validate_availability([]).outcome == "reask"


def test_schedule_duplicates_are_removed():
    verdict = validate_schedule([Schedule.EVENING, Schedule.MORNING, Schedule.EVENING])
    assert verdict.value == [Schedule.MORNING, Schedule.EVENING]


def test_flexible_schedule_stands_alone():
    verdict = validate_schedule([Schedule.MORNING, Schedule.FLEXIBLE])
    assert verdict.outcome == "accept"
    assert verdict.value == [Schedule.FLEXIBLE]


def test_empty_schedule_is_reasked():
    assert validate_schedule([]).outcome == "reask"


# Experience


def test_no_experience_is_accepted_as_empty_list():
    verdict = validate_experience(has_experience=False, items=[])
    assert verdict.outcome == "accept"
    assert verdict.value == []


def test_months_are_converted_and_platforms_normalized():
    verdict = validate_experience(
        has_experience=True,
        items=[
            RawExperience(platform="Uber Eats", months=18),
            RawExperience(platform="DiDi", years=2),
            RawExperience(platform="mensajería de farmacia", years=1),
        ],
    )
    assert verdict.outcome == "accept"
    assert verdict.value == [
        ExperienceItem(platform="uber_eats", years=1.5),
        ExperienceItem(platform="didi_food", years=2),
        ExperienceItem(platform="other", years=1),
    ]


@pytest.mark.parametrize(
    "raw, key",
    [
        ("glovo", "glovo"),
        ("UberEats", "uber_eats"),
        ("uber", "uber_eats"),
        ("Just Eat", "just_eat"),
        ("justeat", "just_eat"),
        ("Rappi", "rappi"),
        ("didi food", "didi_food"),
    ],
)
def test_platform_aliases(raw, key):
    verdict = validate_experience(has_experience=True, items=[RawExperience(platform=raw, years=1)])
    assert verdict.value[0].platform == key


def test_same_platform_twice_keeps_the_longest():
    verdict = validate_experience(
        has_experience=True,
        items=[
            RawExperience(platform="glovo", years=1),
            RawExperience(platform="Glovo", months=30),
        ],
    )
    assert verdict.value == [ExperienceItem(platform="glovo", years=2.5)]


def test_experience_without_duration_is_reasked():
    verdict = validate_experience(has_experience=True, items=[RawExperience(platform="glovo")])
    assert verdict.outcome == "reask"


def test_has_experience_without_items_is_reasked():
    assert validate_experience(has_experience=True, items=[]).outcome == "reask"


@pytest.mark.parametrize("years", [-1, 41])
def test_years_out_of_range_are_reasked(years):
    verdict = validate_experience(
        has_experience=True, items=[RawExperience(platform="glovo", years=years)]
    )
    assert verdict.outcome == "reask"


# Start date


def test_local_date_uses_the_candidates_timezone():
    # 23:30 UTC on Sunday is already Monday in Madrid, but still Sunday in Mexico City.
    received = datetime(2026, 10, 11, 23, 30, tzinfo=UTC)
    assert local_date(received, "Europe/Madrid") == date(2026, 10, 12)
    assert local_date(received, "America/Mexico_City") == date(2026, 10, 11)


def test_asap_means_today():
    verdict = validate_start_date(
        StartDateAnswer(kind="asap"), today=date(2026, 10, 12), max_days=183
    )
    assert verdict.outcome == "accept"
    assert verdict.value == date(2026, 10, 12)


def test_resolved_date_within_range_is_accepted():
    answer = StartDateAnswer(kind="date", resolved=date(2026, 10, 19))
    verdict = validate_start_date(answer, today=date(2026, 10, 12), max_days=183)
    assert verdict.value == date(2026, 10, 19)


def test_today_is_not_in_the_past():
    answer = StartDateAnswer(kind="date", resolved=date(2026, 10, 12))
    assert validate_start_date(answer, today=date(2026, 10, 12), max_days=183).outcome == "accept"


def test_past_date_is_reasked():
    answer = StartDateAnswer(kind="date", resolved=date(2026, 10, 1))
    assert validate_start_date(answer, today=date(2026, 10, 12), max_days=183).outcome == "reask"


def test_date_beyond_the_limit_is_reasked():
    answer = StartDateAnswer(kind="date", resolved=date(2027, 6, 1))
    assert validate_start_date(answer, today=date(2026, 10, 12), max_days=183).outcome == "reask"


def test_vague_start_date_is_reasked_for_a_rough_date():
    verdict = validate_start_date(
        StartDateAnswer(kind="vague"), today=date(2026, 10, 12), max_days=183
    )
    assert verdict.outcome == "reask"


def test_date_kind_without_a_date_is_reasked():
    verdict = validate_start_date(
        StartDateAnswer(kind="date"), today=date(2026, 10, 12), max_days=183
    )
    assert verdict.outcome == "reask"
