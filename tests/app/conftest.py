import pytest


@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    # The manifest storage needs collectstatic output; tests render templates without it.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
