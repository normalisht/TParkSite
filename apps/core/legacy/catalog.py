from pathlib import Path

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.legacy.html import clean_html
from apps.core.legacy.media import attach_image, numbered_images

LAST = 10_000  # порядок для связей без номера — в конец списка


def _order(value) -> int:
    return max(int(value), 0) if value is not None else LAST


def _import_photos(model, parent_field: str, parent, directory: Path, report, label: str) -> None:
    for order, path in enumerate(numbered_images(directory)):
        photo = model(**{parent_field: parent}, order=order)
        if attach_image(photo, "image", path, report):
            photo.save()
            report.add(label)


def import_catalog(db, images: Path, report) -> None:
    for row in db.rows("category"):
        category = Category(
            id=row["id"],
            name=(row["name"] or "").strip() or f"Категория {row['id']}",
            description=clean_html(row["description"]),
            is_published=bool(row["status"]),
            order=row["number"] if row["number"] is not None and row["number"] >= 0 else 0,
        )
        attach_image(category, "preview", images / "category" / "preview" / f"{row['id']}.jpg", report, missing_ok=True)
        category.save()
        report.add("Категории")
        _import_photos(
            CategoryPhoto, "category", category, images / "category" / str(row["id"]), report, "Фото категорий"
        )

    category_ids = set(Category.objects.values_list("id", flat=True))
    groups = {}
    for row in db.rows("type"):
        groups[row["id"]] = CategoryGroup.objects.create(name=(row["name"] or "").strip(), order=row["number"] or 0)
        report.add("Группы категорий")
    for row in db.rows("category_type"):
        group = groups.get(row["type_id"])
        if group is None or row["category_id"] not in category_ids:
            report.warn(f"Пропущена связь группа–категория #{row['id']}: ссылка на удалённую запись")
            continue
        group.categories.add(row["category_id"])

    for row in db.rows("service"):
        service = Service.objects.create(
            id=row["id"],
            name=(row["name"] or "").strip() or f"Услуга {row['id']}",
            short_description=clean_html(row["short_description"]),
            description=clean_html(row["description"]),
            price=(row["price"] or "").strip()[:32],
            price_unit=(row["time"] or "").strip()[:128],
            is_published=row["status"] is None or bool(row["status"]),
            has_page=bool(row["next"]),
        )
        report.add("Услуги")
        _import_photos(ServicePhoto, "service", service, images / "service" / str(row["id"]), report, "Фото услуг")

    service_ids = set(Service.objects.values_list("id", flat=True))
    seen = set()
    for row in db.rows("service_category"):
        key = (row["category_id"], row["service_id"])
        if row["category_id"] not in category_ids or row["service_id"] not in service_ids:
            report.warn(f"Пропущена связь категория–услуга #{row['id']}: ссылка на удалённую запись")
            continue
        if key in seen:
            continue
        seen.add(key)
        CategoryService.objects.create(category_id=key[0], service_id=key[1], order=_order(row["number"]))
        report.add("Услуги в категориях")
