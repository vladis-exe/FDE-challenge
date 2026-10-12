import pytest

from apps.messaging import channels, services
from tests.app.fakes import FakeChannel, FakeEngine


@pytest.fixture(autouse=True)
def plain_static_storage(settings, tmp_path):
    # The manifest storage needs collectstatic output; tests render templates without it.
    settings.STATIC_ROOT = tmp_path  # an existing dir, so WhiteNoise doesn't warn
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def engine(monkeypatch) -> FakeEngine:
    fake = FakeEngine()
    monkeypatch.setattr(services, "engine", fake)
    monkeypatch.setattr(services, "final_record", lambda state: {"status": state.status})
    return fake


@pytest.fixture
def channel(monkeypatch) -> FakeChannel:
    fake = FakeChannel()
    monkeypatch.setattr(channels, "channel_for", lambda conversation: fake)
    return fake
