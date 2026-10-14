"""Сезонное оформление: выбор сезона по датам, модель, вывод на сайте."""

from dataclasses import dataclass
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.core.seasons import (
    Kind,
    Mode,
    covers,
    format_day_month,
    parse_day_month,
    pick,
    validate_day_month,
    validate_site_link,
)


@pytest.mark.parametrize(("value", "expected"), [("15.12", (12, 15)), ("1.3", (3, 1)), (" 29.02 ", (2, 29))])
def test_parse_day_month(value, expected):
    assert parse_day_month(value) == expected


@pytest.mark.parametrize("value", ["", "15-12", "32.01", "30.02", "15.13", "00.10", "1512", "15.12.2026"])
def test_parse_day_month_rejects(value):
    with pytest.raises(ValueError):
        parse_day_month(value)
    with pytest.raises(ValidationError):
        validate_day_month(value)


def test_format_day_month_pads():
    assert format_day_month("1.3") == "01.03"


@pytest.mark.parametrize(
    ("day", "inside"),
    [
        (date(2026, 12, 15), True),
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), True),
        (date(2027, 1, 14), True),
        (date(2027, 1, 15), False),
        (date(2026, 12, 14), False),
        (date(2026, 7, 1), False),
    ],
)
def test_covers_across_new_year(day, inside):
    assert covers("15.12", "14.01", day) is inside


def test_covers_within_year_and_leap_day():
    assert covers("01.12", "28.02", date(2027, 2, 28))
    assert not covers("01.12", "28.02", date(2028, 2, 29))  # 29.02 — после 28.02
    assert covers("01.12", "29.02", date(2027, 3, 1)) is False  # граница 29.02 в невисокосный год не ломает сравнение
    assert covers("10.06", "10.06", date(2026, 6, 10))


@dataclass
class S:
    kind: str
    mode: str = Mode.AUTO
    start: str = "01.12"
    end: str = "28.02"


NEW_YEAR = S(Kind.NEW_YEAR, start="15.12", end="14.01")
WINTER = S(Kind.WINTER)


def test_pick_by_dates_new_year_wins_overlap():
    assert pick([WINTER, NEW_YEAR], date(2026, 12, 31)) is NEW_YEAR
    assert pick([WINTER, NEW_YEAR], date(2026, 12, 5)) is WINTER
    assert pick([WINTER, NEW_YEAR], date(2027, 2, 1)) is WINTER
    assert pick([WINTER, NEW_YEAR], date(2026, 10, 14)) is None


def test_pick_forced_beats_dates_and_off_never_shows():
    forced_winter = S(Kind.WINTER, mode=Mode.ON)
    assert pick([forced_winter, NEW_YEAR], date(2026, 12, 31)) is forced_winter
    assert pick([forced_winter], date(2026, 7, 1)) is forced_winter
    assert pick([S(Kind.NEW_YEAR, mode=Mode.OFF, start="15.12", end="14.01")], date(2026, 12, 31)) is None


def test_pick_ignores_broken_dates():
    """Кривая дата в базе (в обход формы) — сезон не показывается, сайт не падает."""
    assert pick([S(Kind.WINTER, start="31.02", end="bad")], date(2026, 12, 31)) is None


def test_pick_uses_today(monkeypatch):
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2027, 1, 2))
    assert pick([WINTER, NEW_YEAR]) is NEW_YEAR


@pytest.mark.parametrize("value", ["/events/elka/", "https://t-camp.ru/x", "http://example.com"])
def test_site_link_accepts(value):
    validate_site_link(value)


@pytest.mark.parametrize("value", ["javascript:alert(1)", "//evil.com", "/\\evil.com", "events/", "ftp://x.ru"])
def test_site_link_rejects(value):
    with pytest.raises(ValidationError):
        validate_site_link(value)
