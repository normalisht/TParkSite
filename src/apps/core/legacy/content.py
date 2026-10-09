from pathlib import Path

from django.utils.html import escape

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.legacy.html import clean_html, clean_line, clean_url, parse_date, parse_ru_date, split_lead_link
from apps.core.legacy.media import attach_image, numbered_images

OLD_BANNER_IDS = {0, 1, 2}  # events/0..2.jpg — фон слайдера старой страницы событий


def import_content(db, images: Path, report) -> None:
    for row in db.rows("event"):
        event_date = parse_date(row["date"])
        if event_date is None:
            report.warn(f"Мероприятие #{row['id']} «{row['title']}» без даты — пропущено")
            continue
        event = Event(
            title=clean_line(row["title"], 128) or f"Мероприятие {row['id']}",
            date=event_date,
            description=clean_html(row["description"]),
            link=clean_url(row["link"]),
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

    for row in db.rows("comment"):
        # Старые отзывы — копии с Яндекс Карт: первый абзац — ссылка на отзыв, текст ссылки — его дата.
        text, link, link_text = split_lead_link(clean_html(row["text"]))
        review_date = parse_ru_date(link_text)
        if link and not review_date and link_text:
            text = "\n".join(
                filter(None, [f"<p>{escape(link_text)}</p>", text])
            )  # текст ссылки — не дата: не теряем его
        # Имя не переносим: на сайте все отзывы подписаны «Гость Т-Парка», источник берётся из ссылки.
        review = Review(text=text, link=link, date=review_date, is_published=True)
        attach_image(review, "photo", images / "comments" / f"{row['id']}.jpg", report, missing_ok=True)
        review.save()
        report.add("Отзывы")

    for order, row in enumerate(db.rows("partner")):
        if row["name"] == "temp":
            report.warn(f"Пропущена служебная запись партнёра #{row['id']} «temp»")
            continue
        partner = Partner(name="", link=clean_url(row["link"]), order=order)
        attach_image(partner, "logo", images / "partner" / f"{row['id']}.jpg", report)
        partner.save()
        report.add("Партнёры")

    for order, path in enumerate(numbered_images(images / "gallery")):
        photo = GalleryPhoto(order=order)
        if attach_image(photo, "image", path, report):
            photo.save()
            report.add("Фото галереи")
