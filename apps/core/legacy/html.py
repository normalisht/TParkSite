import html
import re
from datetime import date

from django.utils.html import strip_tags

from apps.core.fields import sanitize_html

_TITLE_RE = re.compile(r"<(strong|h[1-3])[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)


def clean_html(value) -> str:
    return sanitize_html(value or "").strip()


def extract_title(body: str, fallback: str) -> str:
    match = _TITLE_RE.search(body or "")
    if match:
        text = re.sub(r"\s+", " ", html.unescape(strip_tags(match.group(2)))).strip()
        if text:
            return text[:255]
    return fallback


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def phone_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else None
