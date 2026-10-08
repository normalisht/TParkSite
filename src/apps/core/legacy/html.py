import html
import re
from datetime import date

from django.utils.html import strip_tags

from apps.core.fields import sanitize_html

_TITLE_RE = re.compile(r"<(strong|h[1-3])[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
# Пустые абзацы, которыми старый CKEditor добивал отступы: <p>&nbsp;</p>, <p><br></p>.
_EMPTY_P = r"\s*<p>(?:\s|&nbsp;|\xa0|<br\s*/?>)*</p>\s*"
_EDGE_EMPTY_RE = re.compile(rf"^(?:{_EMPTY_P})+|(?:{_EMPTY_P})+$")


def clean_html(value) -> str:
    html_text = sanitize_html((value or "").replace("\r\n", "\n").replace("\r", "\n"))
    return _EDGE_EMPTY_RE.sub("", html_text).strip()


def clean_line(value, max_length: int) -> str:
    """Однострочный текст: схлопывает пробелы и переводы строк, режет до длины поля."""
    return re.sub(r"\s+", " ", value or "").strip()[:max_length]


_LEAD_LINK_RE = re.compile(r'^\s*<p>\s*<a\s[^>]*?href="([^"]*)"[^>]*>(.*?)</a>\s*</p>\s*', re.IGNORECASE | re.DOTALL)
_RU_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def split_lead_link(body: str) -> tuple[str, str, str]:
    """Отделяет первый абзац, состоящий из одной ссылки: (остаток HTML, адрес, текст ссылки)."""
    match = _LEAD_LINK_RE.match(body or "")
    if not match:
        return body, "", ""
    url = clean_url(html.unescape(match.group(1)))
    if not url:
        return body, "", ""
    text = re.sub(r"\s+", " ", html.unescape(strip_tags(match.group(2)))).strip()
    return body[match.end() :].strip(), url, text


def parse_ru_date(value: str) -> date | None:
    """Дата вида 20.07.2022 или 6.06.2021."""
    match = _RU_DATE_RE.match((value or "").strip())
    if not match:
        return None
    day, month, year = map(int, match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


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


def clean_url(value) -> str:
    """Только абсолютные http(s)-ссылки: заглушки вроде «#» дали бы на сайте мёртвую кнопку."""
    url = (value or "").strip()[:500]
    return url if url.startswith(("http://", "https://")) else ""
