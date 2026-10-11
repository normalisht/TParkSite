"""Удаляет миниатюры imagekit, которые не нужны ни одной текущей спеке.

Папку CACHE целиком удалять нельзя: imagekit в процессе помнит «файл есть» без срока,
и до перезапуска сайт отдавал бы битые картинки.
"""

import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from imagekit.registry import cachefile_registry, generator_registry


def expected_cache_files() -> set[str]:
    """Имена (относительно MEDIA_ROOT) всех миниатюр текущих спек для всех фото в базе."""
    names = set()
    for generator_id in generator_registry.get_ids():
        for file in cachefile_registry.get(generator_id):
            if file.name:
                names.add(file.name)
    return names


class Command(BaseCommand):
    help = "Удаляет из CACHE/images миниатюры, не нужные ни одной текущей спеке (остаются после смены размеров или качества)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Только показать, сколько будет удалено.")
        parser.add_argument(
            "--min-age",
            type=int,
            default=60,
            help="Не трогать файлы моложе стольких минут (по умолчанию 60): их могли создать для только что загруженного фото.",
        )

    def handle(self, *args, dry_run=False, min_age=60, **options):
        media = Path(settings.MEDIA_ROOT)
        cache_dir = media / settings.IMAGEKIT_CACHEFILE_DIR
        if not cache_dir.is_dir():
            self.stdout.write("Папки миниатюр нет — удалять нечего.")
            return
        keep = expected_cache_files()
        cutoff = time.time() - min_age * 60
        count = size = 0
        for path in sorted(p for p in cache_dir.rglob("*") if p.is_file()):
            stat = path.stat()
            if path.relative_to(media).as_posix() in keep or stat.st_mtime > cutoff:
                continue
            count += 1
            size += stat.st_size
            if not dry_run:
                path.unlink()
        if not dry_run:
            folders = sorted((p for p in cache_dir.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True)
            for folder in folders:
                if not any(folder.iterdir()):
                    folder.rmdir()
        verb = "Будет удалено" if dry_run else "Удалено"
        self.stdout.write(f"{verb}: {count} файлов, {size / 1024 / 1024:.1f} МБ. Нужных миниатюр: {len(keep)}.")
