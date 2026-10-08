from pathlib import Path

from django.core.files import File
from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def numbered_images(directory: Path) -> list[Path]:
    """Картинки папки по номеру в имени (2.jpg раньше 10.jpg); прочие имена — в конце по алфавиту."""
    if not directory.is_dir():
        return []
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(files, key=lambda p: (0, int(p.stem), "") if p.stem.isdigit() else (1, 0, p.name))


def attach_image(instance, field_name: str, path: Path, report, *, missing_ok: bool = False) -> bool:
    """Кладёт файл в поле изображения (с пережатием). Битый файл — предупреждение, а не падение импорта."""
    if not path.is_file():
        if not missing_ok:
            report.warn(f"Нет файла {path}")
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        with path.open("rb") as fh:
            getattr(instance, field_name).save(path.name, File(fh), save=False)
    except Exception as exc:  # noqa: BLE001 — любой битый файл: предупреждение, а не падение импорта
        report.warn(f"Не удалось загрузить {path}: {exc}")
        return False
    return True
