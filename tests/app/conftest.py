import pytest

from apps.messaging import channels, services
from screening.config import load_config
from screening.engine import EngineContext
from screening.llm import FakeLLM
from tests.app.fakes import FakeChannel, FakeEngine


@pytest.fixture(autouse=True)
def plain_static_storage(settings, tmp_path):
    # The manifest storage needs collectstatic output; tests render templates without it.
    settings.STATIC_ROOT = tmp_path  # an existing dir, so WhiteNoise doesn't warn
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch) -> FakeLLM:
    """Every app test gets a scripted LLM; the real AnthropicClient is never built."""
    llm = FakeLLM()
    context = EngineContext(config=load_config(), llm=llm)
    monkeypatch.setattr(services, "engine_context", lambda: context)
    return llm


@pytest.fixture
def engine(monkeypatch) -> FakeEngine:
    fake = FakeEngine()
    monkeypatch.setattr(services, "engine", fake)
    return fake


@pytest.fixture
def channel(monkeypatch) -> FakeChannel:
    fake = FakeChannel()
    monkeypatch.setattr(channels, "channel_for", lambda conversation: fake)
    return fake
