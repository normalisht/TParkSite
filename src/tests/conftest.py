import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Каждый тест пишет медиафайлы во временную папку."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def make_image():
    def _make(name: str = "photo.jpg", size=(64, 48), fmt: str = "JPEG") -> SimpleUploadedFile:
        buffer = io.BytesIO()
        Image.new("RGB", size, "orange").save(buffer, fmt)
        content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}[fmt]
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    return _make
