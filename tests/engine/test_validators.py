from datetime import UTC, date, datetime

import pytest

from screening.config import load_config
from screening.schemas import ExperienceItem, Location
from screening.validators import (
    RawExperience,
    StartDateAnswer,
    local_date,
    match_city,
    relative_day,
    validate_boolean,
    validate_experience,
    validate_name,
    validate_options,
    validate_start_date,
)

AVAILABILITY = ["full_time", "part_time", "weekends"]
SCHEDULE = ["morning", "afternoon", "evening", "flexible"]


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


def test_name_shared_by_two_cities_is_ambiguous(config):
    result = match_city("en san pedro", config)
    assert result.kind == "ambiguous"
    assert {option.city for option in result.options} == {"monterrey", "guadalajara"}


def test_longer_match_beats_the_shared_name_inside_it(config):
    result = match_city("San Pedro Garza García, Monterrey", config)
    assert result.kind == "matched"
    assert result.location.city == "monterrey"


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


# Yes/no fields (the license)


def test_license_yes_and_no_are_accepted():
    assert validate_boolean("yes", name="license").value is True
    no = validate_boolean("no", name="license")
    assert no.outcome == "accept" and no.value is False


@pytest.mark.parametrize(
    "answer, note",
    [
        ("expired", "license expired"),
        ("in_progress", "license in progress"),
        ("foreign", "license from another country"),
    ],
)
def test_unclear_license_is_flagged_with_a_note(answer, note):
    verdict = validate_boolean(answer, name="license")
    assert (verdict.outcome, verdict.value, verdict.note) == ("flag", None, note)


def test_vague_license_answer_is_reasked():
    assert validate_boolean("vague", name="license").outcome == "reask"


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


# Option fields (availability, schedule)


def test_availability_combinations_are_kept_in_canonical_order():
    verdict = validate_options(["weekends", "part_time"], options=AVAILABILITY, exclusive=[])
    assert verdict.outcome == "accept"
    assert verdict.value == ["part_time", "weekends"]


def test_empty_availability_is_reasked():
    assert validate_options([], options=AVAILABILITY, exclusive=[]).outcome == "reask"


def test_schedule_duplicates_are_removed():
    verdict = validate_options(["evening", "morning", "evening"], options=SCHEDULE, exclusive=[])
    assert verdict.value == ["morning", "evening"]


def test_flexible_schedule_stands_alone():
    verdict = validate_options(["morning", "flexible"], options=SCHEDULE, exclusive=["flexible"])
    assert verdict.outcome == "accept"
    assert verdict.value == ["flexible"]


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


# Regions (a state or province is not a city: never treat it as out of the area)


@pytest.mark.parametrize(
    "text, cities",
    [
        ("vivo en Nuevo León", {"monterrey"}),
        ("NL", {"monterrey"}),
        ("en Jalisco", {"guadalajara"}),
        ("Andalucía", {"sevilla", "malaga"}),
        ("Comunidad de Madrid", {"madrid"}),
        ("Euskadi", {"bilbao"}),
    ],
)
def test_a_region_offers_its_served_cities(config, text, cities):
    result = match_city(text, config)
    assert result.kind == "ambiguous", result
    assert {option.city for option in result.options} == cities


def test_a_city_named_with_its_region_is_the_city(config):
    result = match_city("Monterrey, Nuevo León", config)
    assert result.kind == "matched"
    assert result.location.city == "monterrey"


def test_a_region_with_no_served_city_is_still_not_served(config):
    assert match_city("Aragón", config).kind == "not_served"


@pytest.mark.parametrize("text", ["San Pedro, Monterrey", "en san pedro, monterrey"])
def test_names_that_agree_on_one_city_pick_that_city(config, text):
    """Live run: after "Guadalajara o Monterrey?", the extractor returned "San Pedro, Monterrey"."""
    result = match_city(text, config)
    assert result.kind == "matched"
    assert result.location.city == "monterrey"


# E19 (V9 findings): relative days in code, platforms named with a place


@pytest.mark.parametrize(
    "text, offset",
    [
        ("mañana mismo", 1),
        ("mañana mismo si hace falta", 1),
        ("pasado mañana", 2),
        ("hoy", 0),
        ("hoy mismo", 0),
        ("tomorrow works", 1),
        ("I can start today", 0),
        ("the day after tomorrow", 2),
        ("puedo empezar mañana por la mañana", 1),  # the second "mañana" is "morning"
    ],
)
def test_relative_days_are_read_in_code(text, offset):
    assert relative_day(text) == offset


@pytest.mark.parametrize(
    "text",
    [
        "por las mañanas",  # morning, not tomorrow
        "en la mañana",
        "el lunes",
    ],
)
def test_no_relative_day_means_none(text):
    assert relative_day(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "mañana o pasado mañana, no sé",
        # Lead review: a candidate often rules a day out. Picking either in code could
        # store the refused day, so the model's reading must stand.
        "hoy no, mañana sí",
        "hoy no puedo, pasado mañana",
        "mañana no, pasado mañana",
        "tomorrow no, day after tomorrow",
    ],
)
def test_two_different_days_leave_it_to_the_model(text):
    assert relative_day(text) is None


def test_a_bare_pasado_is_not_a_second_day():
    assert relative_day("mañana o pasado") == 1  # only "mañana" is a relative day here


@pytest.mark.parametrize(
    "raw, key",
    [
        ("uber eats en houston", "uber_eats"),
        ("Glovo (en Italia)", "glovo"),
        ("didi food mty", "didi_food"),
        ("Deliveroo", "other"),
    ],
)
def test_a_platform_named_with_a_place_is_still_that_platform(raw, key):
    verdict = validate_experience(has_experience=True, items=[RawExperience(platform=raw, years=2)])
    assert verdict.value[0].platform == key
