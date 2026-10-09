import html
import re

from django.utils.html import strip_tags

from apps.core.models import DEFAULT_TITLE_SUFFIX, PARK_ADDRESS, SiteSettings

SITE_DESCRIPTION = (
    f"Т-Парк — тренинг-парк Дмитрия Сергеева: активный отдых, тренинги и мероприятия на природе. {PARK_ADDRESS}."
)

# Title и description статических страниц, если в настройках сайта поля пустые. Title выводится как есть.
PAGE_DEFAULTS = {
    "home": (
        "Т-Парк — тренинг-парк и активный отдых в Калужской области",
        SITE_DESCRIPTION,
    ),
    "events": (
        "Мероприятия Т-Парка — афиша, Калужская область",
        f"Афиша Т-Парка: ближайшие мероприятия, тренинги и праздники на природе. {PARK_ADDRESS}.",
    ),
    "about": (
        "О Т-Парке — тренинг-парк Дмитрия Сергеева",
        "Т-Парк — тренинг-парк Дмитрия Сергеева в Калужской области: философия, команда, партнёры и что посмотреть рядом.",
    ),
    "reviews": (
        "Отзывы о Т-Парке — Жуковский район, Калужская область",
        f"Отзывы гостей о Т-Парке: впечатления об отдыхе, тренингах и мероприятиях. {PARK_ADDRESS}.",
    ),
    "gallery": (
        "Фотогалерея Т-Парка — Калужская область",
        f"Фотографии Т-Парка: территория, активный отдых, тренинги и мероприятия. {PARK_ADDRESS}.",
    ),
    "contacts": (
        "Контакты Т-Парка — как добраться в село Восход",
        f"Адрес и телефоны Т-Парка: {PARK_ADDRESS}. Схема проезда на карте, WhatsApp и Telegram.",
    ),
}


def plaintext(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", html.unescape(strip_tags(value or ""))).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def make_seo(
    title: str = "", description_html: str = "", image_url: str = "", *, obj=None, default_description: str = ""
) -> dict:
    """SEO страницы: свои поля объекта (`SeoModel`) важнее собранных из названия и текста.

    `title` — полный `<title>`: «Название — Т-Парк, Калужская область»; `og_title` — без окончания.
    """
    custom_title = getattr(obj, "seo_title", "")
    if custom_title:
        full_title = og_title = custom_title
    else:
        suffix = SiteSettings.load().seo_title_suffix or DEFAULT_TITLE_SUFFIX
        full_title, og_title = f"{title} — {suffix}", title
    description = getattr(obj, "seo_description", "") or plaintext(description_html) or default_description
    return {"title": full_title, "og_title": og_title, "description": plaintext(description), "image": image_url}


# Статические страницы: ключ (поля seo_<key>_* в настройках) → название, адрес, поле с текстом страницы.
STATIC_PAGES = {
    "home": ("Главная", "/", "home_intro"),
    "events": ("Мероприятия", "/events/", "events_intro"),
    "about": ("О нас", "/about/", "about_text"),
    "reviews": ("Отзывы", "/reviews/", None),
    "gallery": ("Галерея", "/gallery/", None),
    "contacts": ("Контакты", "/contacts/", "contacts_text"),
}


def page_fallback(key: str, site: SiteSettings) -> tuple[str, str]:
    """Title и description статической страницы, если поля в настройках пустые: текст страницы → умолчания."""
    default_title, default_description = PAGE_DEFAULTS[key]
    text_field = STATIC_PAGES[key][2]
    page_text = plaintext(getattr(site, text_field)) if text_field else ""
    return default_title, page_text or default_description


def page_seo(key: str) -> dict:
    """SEO статической страницы: поля из настроек сайта, а если пусто — `page_fallback`."""
    site = SiteSettings.load()
    default_title, default_description = page_fallback(key, site)
    title = getattr(site, f"seo_{key}_title") or default_title
    description = getattr(site, f"seo_{key}_description") or default_description
    return {"title": title, "og_title": title, "description": plaintext(description), "image": ""}


def absolute_url(request, url: str) -> str:
    return request.build_absolute_uri(url) if url else ""
