"""Общие поля моделей: HTML с очисткой и изображения с пережатием."""

from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django_prose_editor.fields import ProseEditorField, create_sanitizer
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit
from PIL import Image

HTML_EXTENSIONS = {
    "Bold": True,
    "Italic": True,
    "Heading": {"levels": [2, 3]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "HardBreak": True,
    "Link": {"enableTarget": True, "protocols": ["http", "https", "mailto", "tel"]},
}

_sanitizer = create_sanitizer(HTML_EXTENSIONS)


def sanitize_html(html: str) -> str:
    """Та же очистка, что применяет редактор при сохранении формы (нужна импорту)."""
    return _sanitizer(html or "")


def HtmlField(verbose_name: str, **kwargs) -> ProseEditorField:
    kwargs.setdefault("blank", True)
    return ProseEditorField(verbose_name, extensions=HTML_EXTENSIONS, sanitize=True, **kwargs)


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(file) -> None:
    if getattr(file, "_committed", False):
        return  # файл уже в хранилище — проверяли при загрузке; отсутствие файла на диске не должно блокировать сохранение
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Файл больше 20 МБ.")
    try:
        position = file.tell()
        with Image.open(file) as image:
            image_format = image.format
        file.seek(position)
    except Exception as exc:
        raise ValidationError("Файл не похож на изображение.") from exc
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Допустимые форматы: jpg, png или webp.")


@deconstructible
class UploadTo:
    """Кладёт файл в папку `prefix` под случайным именем — без коллизий и кириллицы в путях."""

    def __init__(self, prefix: str):
        self.prefix = prefix

    def __call__(self, instance, filename: str) -> str:
        return f"{self.prefix}/{uuid4().hex}{Path(filename).suffix.lower()}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and other.prefix == self.prefix

    def __hash__(self):
        return hash(self.prefix)


def photo_field(verbose_name: str, prefix: str, *, size=(1920, 1080), fmt="JPEG", **kwargs):
    kwargs.setdefault("blank", True)
    return ProcessedImageField(
        verbose_name=verbose_name,
        upload_to=UploadTo(prefix),
        processors=[ResizeToFit(*size, upscale=False)],
        format=fmt,
        options={"quality": 85},
        validators=[validate_image_upload],
        **kwargs,
    )


def image_spec(source: str, width: int, height: int, *, crop: bool = True) -> ImageSpecField:
    processor = ResizeToFill(width, height) if crop else ResizeToFit(width, height, upscale=False)
    return ImageSpecField(source=source, processors=[processor], format="WEBP", options={"quality": 80})
