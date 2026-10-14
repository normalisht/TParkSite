import io
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Каждый тест пишет медиафайлы во временную папку."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def no_background_thumbnails(monkeypatch):
    """Миниатюры после сохранения создаются в фоновом потоке; в тестах — нет (по требованию тест подменяет сам)."""
    monkeypatch.setattr("apps.core.images.run_in_background", lambda fn: None)


@pytest.fixture(autouse=True)
def off_season(monkeypatch):
    """Сезонное оформление выбирается по сегодняшней дате — тесты идут в «обычный» день, сезонные подменяют дату сами."""
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 10, 14))


@pytest.fixture
def make_image():
    def _make(name: str = "photo.jpg", size=(64, 48), fmt: str = "JPEG") -> SimpleUploadedFile:
        buffer = io.BytesIO()
        Image.new("RGB", size, "orange").save(buffer, fmt)
        content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}[fmt]
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    return _make
