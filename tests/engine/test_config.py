from datetime import time, timedelta

import pytest
from pydantic import ValidationError

from screening.config import ScreeningConfig, load_config, parse_duration


@pytest.fixture(autouse=True)
def no_demo_scale(monkeypatch):
    monkeypatch.delenv("DEMO_TIME_SCALE", raising=False)


def test_loads_shipped_config():
    config = load_config()
    assert config.reminder_schedule == [
        timedelta(minutes=15),
        timedelta(hours=2),
        timedelta(hours=20),
    ]
    assert config.abandon_after == timedelta(hours=24)
    assert config.quiet_hours.start == time(21, 0)
    assert config.quiet_hours.end == time(9, 0)
    assert config.max_attempts_per_field == 2
    assert config.max_offtopic_strikes == 1
    assert config.start_date_max_days == 183
    assert config.transcript_tail_size == 12
    assert config.message_limits.max_chars == 300
    assert config.time_scale == 1.0


def test_service_areas_cover_both_countries():
    config = load_config()
    assert config.timezone_for("ES") == "Europe/Madrid"
    assert config.timezone_for("MX") == "America/Mexico_City"
    es_keys = {city.key for city in config.service_areas["ES"].cities}
    mx_keys = {city.key for city in config.service_areas["MX"].cities}
    assert es_keys == {"madrid", "barcelona", "valencia", "sevilla", "malaga", "bilbao"}
    assert mx_keys == {"cdmx", "guadalajara", "monterrey", "puebla", "queretaro"}


def test_city_keys_are_unique_across_countries():
    """Location.city stores only the key, so a key must identify one city."""
    config = load_config()
    keys = [city.key for area in config.service_areas.values() for city in area.cities]
    assert len(keys) == len(set(keys))


def test_every_faq_entry_has_both_languages():
    config = load_config()
    assert config.faq
    for entry in config.faq:
        assert {"es", "en"} <= set(entry.answer), entry.id  # plus optional es_ES/es_MX
        assert set(entry.questions) == {"es", "en"}, entry.id


def test_demo_time_scale_compresses_reminders_but_not_quiet_hours(monkeypatch):
    monkeypatch.setenv("DEMO_TIME_SCALE", "60")
    config = load_config()
    assert config.reminder_schedule[0] == timedelta(seconds=15)
    assert config.abandon_after == timedelta(minutes=24)
    assert config.quiet_hours.start == time(21, 0)
    assert config.time_scale == 60


def test_rejects_non_positive_time_scale(monkeypatch):
    monkeypatch.setenv("DEMO_TIME_SCALE", "0")
    with pytest.raises(ValueError):
        load_config()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("15m", timedelta(minutes=15)),
        ("2h", timedelta(hours=2)),
        ("30s", timedelta(seconds=30)),
        ("1d", timedelta(days=1)),
        ("1.5h", timedelta(minutes=90)),
    ],
)
def test_parse_duration(raw, expected):
    assert parse_duration(raw) == expected


def test_rejects_reminders_after_abandonment():
    config = load_config()
    data = config.model_dump()
    data["abandon_after"] = "1h"
    with pytest.raises(ValidationError):
        ScreeningConfig.model_validate(data)
