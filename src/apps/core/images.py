import logging

from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

AVIF_SUFFIX = "_avif"


def safe_spec_url(obj, spec_name: str) -> str:
    """URL миниатюры imagekit или пустая строка, если объекта или исходника нет либо он битый."""
    if obj is None:
        return ""
    try:
        spec = getattr(obj, spec_name)
        return spec.url if spec else ""
    except Exception:
        logger.warning("Не удалось получить %s для %r", spec_name, obj, exc_info=True)
        return ""


def lightbox_url(photo) -> str:
    """Фото для просмотра во весь экран: WebP-спека `full`, без неё — оригинал."""
    if url := safe_spec_url(photo, "full"):
        return url
    try:
        return photo.image.url
    except AttributeError, ValueError:
        return ""


def _entries(srcset: str) -> list[tuple[str, str]]:
    entries = [item.split() for item in srcset.split(",") if item.strip()]
    if not entries or any(len(e) > 2 for e in entries) or (len(entries) > 1 and any(len(e) != 2 for e in entries)):
        raise ValueError(f"Неверный список спек {srcset!r}: нужно «спека» или «спека 640w, спека 800w».")
    return [(e[0], e[1] if len(e) == 2 else "") for e in entries]


def _candidates(obj, entries, suffix: str = "") -> list[tuple[str, str]]:
    """[(url, дескриптор)] по объявленным у модели спекам; битые и отсутствующие пропускаются."""
    found = []
    for name, descriptor in entries:
        name += suffix
        if suffix and not hasattr(type(obj), name):
            continue
        if url := safe_spec_url(obj, name):
            found.append((url, descriptor))
    return found


def _srcset(candidates) -> str:
    return ", ".join(f"{url} {descriptor}".rstrip() for url, descriptor in candidates)


def _tag(name: str, **attrs) -> str:
    """Тег с атрибутами в порядке вызова (flatatt их сортирует); None и False не выводятся, True — без значения."""
    rendered = format_html_join(
        "",
        "{}",
        (
            (format_html(" {}", k) if v is True else format_html(' {}="{}"', k, v),)
            for k, v in attrs.items()
            if v is not None and v is not False
        ),
    )
    return format_html("<{}{}>", name, rendered)


def picture_html(obj, srcset: str, *, sizes: str = "", wide: str = "", media: str = "", **attrs) -> str:
    """`<picture>`: AVIF-двойники спек (`<спека>_avif`) в `<source>`, WebP — в `<img>`.

    srcset — «спека» или «спека 640w, спека 800w» (src — последняя); wide + media — другой кадр
    для широких экранов (`<source media>`). Атрибуты `<img>` с пустым значением не выводятся, кроме alt.
    Пустая строка, если ни одной миниатюры нет (исходника нет или он битый).
    """
    if obj is None:
        return ""
    entries = _entries(srcset)
    webp = _candidates(obj, entries)
    if not webp:
        return ""
    multi = any(descriptor for _, descriptor in entries)
    sources = []
    if wide:
        wide_entries = _entries(wide)
        wide_sizes = sizes if any(descriptor for _, descriptor in wide_entries) else None
        for suffix, mime in ((AVIF_SUFFIX, "image/avif"), ("", "image/webp")):
            if found := _candidates(obj, wide_entries, suffix):
                sources.append(_tag("source", media=media, type=mime, srcset=_srcset(found), sizes=wide_sizes))
    if avif := _candidates(obj, entries, AVIF_SUFFIX):
        sources.append(_tag("source", type="image/avif", srcset=_srcset(avif), sizes=sizes if multi else None))
    img_attrs = {"src": webp[-1][0]}
    if multi:
        img_attrs |= {"srcset": _srcset(webp), "sizes": sizes or None}
    img_attrs |= {k: v for k, v in attrs.items() if k == "alt" or v != ""}
    img = _tag("img", **img_attrs)
    return mark_safe(f"<picture>{''.join(sources)}{img}</picture>") if sources else img
