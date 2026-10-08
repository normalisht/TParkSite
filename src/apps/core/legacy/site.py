from pathlib import Path

from apps.core.legacy.html import clean_html, extract_title, phone_digits
from apps.core.models import InfoPage, Phone, SiteSettings

TEXT_FIELDS = {
    "about": "about_text",
    "filosofi": "philosophy_text",
    "structure": "nearby_text",
    "contacts_info": "contacts_text",
}


def import_site(db, images: Path, report) -> None:
    texts, info_rows = {}, []
    for row in db.rows("text"):
        if row["title"]:
            texts[row["title"]] = row["text"] or ""
        else:
            info_rows.append(row)

    site = SiteSettings.load()
    main_text = clean_html(texts.get("main_text"))
    site.home_intro = site.events_intro = main_text
    for key, field in TEXT_FIELDS.items():
        setattr(site, field, clean_html(texts.get(key)))
    site.address = (texts.get("address") or "").strip()[:255]
    site.vk_url = (texts.get("vk") or "").strip()[:500]
    site.save()
    # Карта на новом сайте — только виджет Яндекс Карт: его код из старых данных не получить.
    geolocation = (texts.get("geolocation") or "").strip()
    report.warn(
        "Яндекс Карта не перенесена: вставьте код «Поделиться → Встроить карту» в настройках сайта"
        + (f" (старая ссылка на карту: {geolocation})" if geolocation else "")
    )
    report.add("Настройки сайта")

    telegram = phone_digits(texts.get("insta") or "")
    whatsapp_used = telegram_used = False
    for order, raw in enumerate((texts.get("phone_numbers") or "").split()):
        number = phone_digits(raw)
        if not number:
            report.warn(f"Пропущен некорректный телефон {raw!r}")
            continue
        is_whatsapp = not whatsapp_used
        is_telegram = not telegram_used and number == telegram
        Phone.objects.create(
            settings=site, number=number, order=order, is_whatsapp=is_whatsapp, is_telegram=is_telegram
        )
        whatsapp_used = whatsapp_used or is_whatsapp
        telegram_used = telegram_used or is_telegram
        report.add("Телефоны")

    for row in info_rows:
        body = clean_html(row["text"])
        InfoPage.objects.create(
            id=row["id"],
            title=extract_title(body, f"Страница {row['id']}"),
            body=body,
            is_published=bool(row["status"]),
        )
        report.add("Инфо-страницы")
