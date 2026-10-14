"""Сезонное оформление сайта: какой сезон показывать сегодня (модель — `apps.core.models.Season`).

Даты сезона повторяются каждый год и хранятся строкой «ДД.ММ»; конец может быть в следующем году (15.12 — 14.01).
Сезон зависит только от даты и настроек — одинаков для всех запросов дня, поэтому ETag/304 не ломаются.
"""

import re
from collections.abc import Iterable
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils import timezone


class Kind(models.TextChoices):
    NEW_YEAR = "new_year", "Новый год"
    WINTER = "winter", "Зима"
    AUTUMN = "autumn", "Осень"


class Mode(models.TextChoices):
    AUTO = "auto", "По датам"
    ON = "on", "Включено"
    OFF = "off", "Выключено"


# Если подходят несколько сезонов, показывается тот, что раньше (старший): «Новый год» лежит внутри «Зимы»,
# а ранняя зима, наступившая по датам, важнее осени, оставленной включённой вручную.
PRIORITY = [Kind.NEW_YEAR, Kind.WINTER, Kind.AUTUMN]

DAY_MONTH_RE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\s*$")


def today() -> date:
    """Сегодня по часовому поясу сайта; тесты подменяют (tests/conftest.py)."""
    return timezone.localdate()


def parse_day_month(value: str) -> tuple[int, int]:
    """«15.12» → (12, 15): (месяц, день) — так даты сравниваются без года. ValueError, если такой даты нет."""
    match = DAY_MONTH_RE.match(value or "")
    if not match:
        raise ValueError(value)
    day, month = int(match[1]), int(match[2])
    date(2000, month, day)  # високосный год: 29.02 допустимо
    return month, day


def format_day_month(value: str) -> str:
    month, day = parse_day_month(value)
    return f"{day:02d}.{month:02d}"


def validate_day_month(value: str) -> None:
    try:
        parse_day_month(value)
    except ValueError:
        raise ValidationError("Дата в виде ДД.ММ, например 15.12.") from None


def covers(start: str, end: str, day: date) -> bool:
    """Попадает ли день в период «с start по end» включительно; конец раньше начала — период через Новый год."""
    first, last, current = parse_day_month(start), parse_day_month(end), (day.month, day.day)
    if first <= last:
        return first <= current <= last
    return current >= first or current <= last


def _covers_safely(season, day: date) -> bool:
    try:
        return covers(season.start, season.end, day)
    except ValueError:
        return False  # кривая дата в базе — не показываем сезон, но и не роняем сайт


def _matches(season, day: date) -> bool:
    return season.mode == Mode.ON or (season.mode == Mode.AUTO and _covers_safely(season, day))


def pick(seasons: Iterable, day: date | None = None):
    """Сезон для показа или None (обычное оформление). «Включено» — как будто даты подходят всегда; из подходящих —
    первый по PRIORITY: ранний снег («Зима» включена в ноябре) не отнимает новогоднюю тему в её даты. Сезон, которого
    нет в коде (строка осталась после удаления), пропускается — иначе упали бы и сайт, и админка."""
    day = day or today()
    shown = [s for s in seasons if s.kind in PRIORITY and _matches(s, day)]
    return min(shown, key=lambda s: PRIORITY.index(s.kind), default=None)


_url_validator = URLValidator(
    schemes=["http", "https"], message="Адрес страницы сайта (/events/…) или ссылка https://…."
)


def validate_site_link(value: str) -> None:
    """Путь на этом сайте (/events/…) или адрес http(s)://…; `javascript:`, `//чужой.сайт` и `/\\чужой.сайт` — нет."""
    if value.startswith("/") and not value.startswith(("//", "/\\")):
        return
    _url_validator(value)
