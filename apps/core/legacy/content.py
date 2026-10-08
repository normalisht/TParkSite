import re
from pathlib import Path

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.legacy.html import clean_html, parse_date
from apps.core.legacy.media import attach_image, numbered_images

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
OLD_BANNER_IDS = {0, 1, 2}  # events/0..2.jpg — фон слайдера старой страницы событий


def import_content(db, images: Path, report) -> None:
    for row in db.rows("event"):
        event_date = parse_date(row["date"])
        if event_date is None:
            report.warn(f"Мероприятие #{row['id']} «{row['title']}» без даты — пропущено")
            continue
        color = (row["text_color"] or "").strip()
        event = Event(
            title=(row["title"] or "").strip()[:128] or f"Мероприятие {row['id']}",
            date=event_date,
            description=clean_html(row["description"]),
            link=(row["link"] or "").strip()[:500],
            text_color=color if COLOR_RE.match(color) else "",
            show_after_date=bool(row["after_date"]),
        )
        path = images / "events" / f"{row['id']}.jpg"
        attach_image(event, "image", path, report)
        if row["id"] in OLD_BANNER_IDS and path.is_file():
            report.warn(
                f"Фото мероприятия #{row['id']} ({path.name}) совпадает по имени с фоном старого слайдера — проверьте вручную"
            )
        event.save()
        report.add("Мероприятия")

    for order, row in enumerate(db.rows("comment")):
        review = Review(
            author=(row["name"] or "").strip()[:128], text=clean_html(row["text"]), is_published=True, order=order
        )
        attach_image(review, "photo", images / "comments" / f"{row['id']}.jpg", report, missing_ok=True)
        review.save()
        report.add("Отзывы")

    for order, row in enumerate(db.rows("partner")):
        if row["name"] == "temp":
            report.warn(f"Пропущена служебная запись партнёра #{row['id']} «temp»")
            continue
        partner = Partner(name="", link=(row["link"] or "").strip()[:500], order=order)
        attach_image(partner, "logo", images / "partner" / f"{row['id']}.jpg", report)
        partner.save()
        report.add("Партнёры")

    employees = db.rows("employee")
    if employees:
        report.warn(f"Сотрудники не перенесены: {len(employees)} записей-заглушек, заведите их в админке")

    for order, path in enumerate(numbered_images(images / "gallery")):
        photo = GalleryPhoto(order=order)
        if attach_image(photo, "image", path, report):
            photo.save()
            report.add("Фото галереи")
