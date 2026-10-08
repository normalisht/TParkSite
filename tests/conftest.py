import pytest


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Каждый тест пишет медиафайлы во временную папку."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT
