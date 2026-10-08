import csv
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.legacy.catalog import import_catalog
from apps.core.legacy.content import import_content
from apps.core.legacy.reader import LegacyDB
from apps.core.legacy.report import Report
from apps.core.legacy.site import import_site
from apps.core.models import InfoPage, Phone, SiteSettings

CONTENT_MODELS = [
    CategoryService,
    CategoryPhoto,
    ServicePhoto,
    CategoryGroup,
    Service,
    Category,
    Event,
    Review,
    Partner,
    Employee,
    GalleryPhoto,
    InfoPage,
    Phone,
    SiteSettings,
]


class LegacyImportError(Exception):
    pass


def has_content() -> bool:
    return Category.objects.exists() or Service.objects.exists() or Event.objects.exists()


def flush_content() -> None:
    for model in CONTENT_MODELS:
        model.objects.all().delete()


def _media_files() -> set[Path]:
    root = Path(settings.MEDIA_ROOT)
    return {p for p in root.rglob("*") if p.is_file()} if root.exists() else set()


def export_prices(db: LegacyDB, path: Path, report: Report) -> None:
    rows = db.rows("price")
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "service_id", "price", "time"])
        writer.writerows([r["id"], r["service_id"], r["price"], r["time"]] for r in rows)
    report.add(f"Строк таблицы price выгружено в {path}", len(rows))


def run_import(db_path: Path, images_dir: Path, *, flush: bool = False, price_csv: Path | None = None) -> Report:
    if not images_dir.is_dir():
        raise LegacyImportError(f"Папка с изображениями не найдена: {images_dir}")
    if has_content() and not flush:
        raise LegacyImportError("В базе уже есть контент. Запустите с --flush, чтобы заменить его.")
    db = LegacyDB(db_path)
    report = Report()
    before = _media_files()
    try:
        try:
            with transaction.atomic():
                if flush:
                    flush_content()
                import_site(db, images_dir, report)
                import_catalog(db, images_dir, report)
                import_content(db, images_dir, report)
        except Exception:
            # БД откатилась — удаляем файлы, которые успел записать импорт.
            for path in _media_files() - before:
                path.unlink(missing_ok=True)
            raise
        if price_csv:
            export_prices(db, price_csv, report)
    finally:
        db.close()
    return report
