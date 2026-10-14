"""Сезонное оформление: выбор сезона по датам, модель, вывод на сайте."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from PIL import Image

from apps.core.models import Season, SiteSettings
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
from tests.test_seo import _organization


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
AUTUMN = S(Kind.AUTUMN, start="01.09", end="31.10")


def test_pick_autumn_and_priority():
    assert pick([AUTUMN, WINTER, NEW_YEAR], date(2026, 10, 14)) is AUTUMN
    # Включённая вручную осень в декабре уступает зиме и Новому году в их даты.
    forced_autumn = S(Kind.AUTUMN, mode=Mode.ON)
    assert pick([forced_autumn, WINTER, NEW_YEAR], date(2026, 12, 5)) is WINTER
    assert pick([forced_autumn, WINTER, NEW_YEAR], date(2026, 7, 14)) is forced_autumn


def test_pick_by_dates_new_year_wins_overlap():
    assert pick([WINTER, NEW_YEAR], date(2026, 12, 31)) is NEW_YEAR
    assert pick([WINTER, NEW_YEAR], date(2026, 12, 5)) is WINTER
    assert pick([WINTER, NEW_YEAR], date(2027, 2, 1)) is WINTER
    assert pick([WINTER, NEW_YEAR], date(2026, 10, 14)) is None


def test_pick_forced_shows_any_day_but_new_year_still_wins_its_dates():
    """«Включено» — как будто даты подходят всегда; «Новый год» в свои даты всё равно важнее (ранний снег в ноябре
    не отнимает у сайта новогоднюю тему и плашку)."""
    forced_winter = S(Kind.WINTER, mode=Mode.ON)
    assert pick([forced_winter, NEW_YEAR], date(2026, 12, 31)) is NEW_YEAR
    assert pick([forced_winter, NEW_YEAR], date(2026, 11, 20)) is forced_winter
    assert pick([forced_winter], date(2026, 7, 1)) is forced_winter
    forced_new_year = S(Kind.NEW_YEAR, mode=Mode.ON, start="15.12", end="14.01")
    assert pick([WINTER, forced_new_year], date(2026, 12, 5)) is forced_new_year
    assert pick([S(Kind.NEW_YEAR, mode=Mode.OFF, start="15.12", end="14.01")], date(2026, 12, 31)) is None


def test_pick_ignores_broken_dates():
    """Кривая дата в базе (в обход формы) — сезон не показывается, сайт не падает."""
    assert pick([S(Kind.WINTER, start="31.02", end="bad")], date(2026, 12, 31)) is None


def test_pick_skips_unknown_kind():
    """Строка с сезоном, которого больше нет в коде (переименовали без миграции), не роняет сайт и админку."""
    assert pick([S("summer", mode=Mode.ON), WINTER], date(2026, 12, 5)) is WINTER


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


@pytest.mark.django_db
def test_migration_creates_both_seasons():
    seasons = {s.kind: s for s in Season.objects.all()}
    assert set(seasons) == {Kind.NEW_YEAR, Kind.WINTER, Kind.AUTUMN}
    assert (seasons[Kind.AUTUMN].start, seasons[Kind.AUTUMN].end) == ("01.09", "31.10")
    assert (seasons[Kind.NEW_YEAR].start, seasons[Kind.NEW_YEAR].end) == ("15.12", "14.01")
    assert (seasons[Kind.WINTER].start, seasons[Kind.WINTER].end) == ("01.12", "28.02")
    assert all(s.mode == Mode.AUTO and s.settings_id == SiteSettings.load().pk for s in seasons.values())


@pytest.mark.django_db
def test_ensure_for_restores_deleted_seasons():
    site = SiteSettings.load()
    Season.objects.filter(kind=Kind.WINTER).update(start="05.12")
    Season.objects.filter(kind=Kind.NEW_YEAR).delete()
    Season.ensure_for(site)
    assert Season.objects.get(kind=Kind.NEW_YEAR).start == "15.12"
    assert Season.objects.get(kind=Kind.WINTER).start == "05.12"  # существующие не трогаем


@pytest.mark.django_db
def test_clean_normalizes_dates_and_validates():
    season = Season.objects.get(kind=Kind.WINTER)
    season.start, season.end = "1.12", "28.2"
    season.full_clean()
    assert (season.start, season.end) == ("01.12", "28.02")
    season.end = "31.02"
    with pytest.raises(ValidationError) as exc:
        season.full_clean()
    assert "end" in exc.value.message_dict


def test_logo_display_width():
    from apps.core.models import logo_display_width

    assert logo_display_width(600, 150) == 176
    assert logo_display_width(None, 150) is None
    assert logo_display_width(600, 0) is None


def _set_today(monkeypatch, day):
    monkeypatch.setattr("apps.core.seasons.today", lambda: day)


def _header(html):
    return html.split("<header", 1)[1].split("</header>", 1)[0]


@pytest.mark.django_db
def test_off_season_page_has_no_decor(client):
    html = client.get("/").content.decode()
    assert '<html lang="ru" class="motion-safe:scroll-smooth">' in html
    assert "season-particles" not in html


@pytest.mark.parametrize(
    ("day", "kind", "garland"),
    [
        (date(2026, 12, 31), "new_year", True),
        (date(2027, 2, 1), "winter", False),
        (date(2026, 10, 14), "autumn", False),
    ],
)
@pytest.mark.django_db
def test_season_decor(client, monkeypatch, day, kind, garland):
    """Снег или листья — один слой частиц (вид задаёт CSS по data-season), гирлянда — только на Новый год."""
    _set_today(monkeypatch, day)
    html = client.get("/").content.decode()
    assert f'<html lang="ru" class="motion-safe:scroll-smooth" data-season="{kind}">' in html
    assert 'class="season-particles' in html
    assert ('class="season-garland' in html) is garland


@pytest.mark.django_db
def test_season_logo_replaces_header_logo(client, monkeypatch, make_image):
    _set_today(monkeypatch, date(2026, 12, 31))
    site = SiteSettings.load()
    site.header_logo = make_image("main.png", size=(600, 150), fmt="PNG")
    site.save()
    season = Season.objects.get(kind=Kind.NEW_YEAR)
    season.logo = make_image("ny.png", size=(400, 200), fmt="PNG")
    season.save()
    header = _header(client.get("/").content.decode())
    assert re.search(r'<img src="/media/CACHE/[^"]+\.webp" alt="Т-Парк" width="88" height="44"', header)
    # В разметке для поисковиков — основной логотип.
    assert _organization(client)["logo"] == f"http://testserver{site.header_logo.url}"


@pytest.mark.django_db
def test_season_logo_falls_back_when_file_missing(client, monkeypatch, make_image):
    """Файла сезонного логотипа нет (а миниатюра ещё не создана) — в шапке основной."""
    _set_today(monkeypatch, date(2026, 12, 31))
    site = SiteSettings.load()
    site.header_logo = make_image("main.png", size=(600, 150), fmt="PNG")
    site.save()
    season = Season.objects.get(kind=Kind.NEW_YEAR)
    season.logo = make_image("ny.png", size=(400, 200), fmt="PNG")
    season.save()
    Path(season.logo.path).unlink()
    assert re.search(r'width="176" height="44"', _header(client.get("/").content.decode()))


@pytest.mark.django_db
def test_season_logo_ignored_off_season(client, make_image):
    season = Season.objects.get(kind=Kind.NEW_YEAR)
    season.logo = make_image("ny.png", size=(400, 200), fmt="PNG")
    season.save()
    assert re.search(r'<img src="/static/img/logo-header\.png"', _header(client.get("/").content.decode()))


@pytest.mark.django_db
def test_no_season_rows_renders_plain_site(client, monkeypatch):
    _set_today(monkeypatch, date(2026, 12, 31))
    Season.objects.all().delete()
    response = client.get("/")
    assert response.status_code == 200 and "data-season" not in response.content.decode()


@pytest.mark.django_db
def test_season_keeps_etag_and_costs_one_query(client, monkeypatch):
    _set_today(monkeypatch, date(2026, 12, 31))
    first = client.get("/")
    assert first["ETag"] == client.get("/")["ETag"]
    assert client.get("/", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304
    with CaptureQueriesContext(connection) as ctx:
        client.get("/")
    assert sum('"core_season"' in q["sql"] for q in ctx.captured_queries) == 1


SETTINGS_URL = reverse("admin:core_sitesettings_change", args=[1])


def _season_post(seasons_data):
    """Форма настроек: пустые прочие инлайны + вкладка сезонов."""
    data = {"address": "село Восход"}
    for prefix in ("phones", "park_formats", "founder_facts"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0", f"{prefix}-MIN_NUM_FORMS": "0"})
    data.update(
        {
            "seasons-TOTAL_FORMS": str(len(seasons_data)),
            "seasons-INITIAL_FORMS": str(len(seasons_data)),
            "seasons-MIN_NUM_FORMS": "0",
        }
    )
    for i, (season, fields) in enumerate(seasons_data):
        data.update({f"seasons-{i}-id": str(season.pk), f"seasons-{i}-settings": "1"})
        data.update({f"seasons-{i}-{key}": value for key, value in fields.items()})
    return data


@pytest.mark.django_db
def test_admin_shows_season_tab_and_status(admin_client, monkeypatch):
    _set_today(monkeypatch, date(2026, 12, 31))
    html = admin_client.get(SETTINGS_URL).content.decode()
    assert "Сезонное оформление" in html
    assert 'placeholder="ДД.ММ"' in html
    assert html.count("Показывается на сайте") == 1 and html.count("Не показывается") == 2
    # Сезоны в форме — по старшинству: кто важнее при пересечении, тот выше.
    assert html.index(">Новый год<") < html.index(">Зима<") < html.index(">Осень<")


@pytest.mark.django_db
def test_admin_saves_season_and_normalizes_dates(admin_client):
    season = Season.objects.get(kind=Kind.WINTER)
    fields = {"mode": "on", "start": "5.12", "end": "1.3"}
    response = admin_client.post(SETTINGS_URL, _season_post([(season, fields)]))
    assert response.status_code == 302, response.content.decode()[:2000]
    season.refresh_from_db()
    assert (season.mode, season.start, season.end) == ("on", "05.12", "01.03")


@pytest.mark.django_db
def test_admin_rejects_bad_season_input(admin_client):
    season = Season.objects.get(kind=Kind.WINTER)
    fields = {"mode": "auto", "start": "31.02", "end": "01.03"}
    html = admin_client.post(SETTINGS_URL, _season_post([(season, fields)])).content.decode()
    assert "Дата в виде ДД.ММ" in html


@pytest.mark.django_db
def test_admin_restores_missing_seasons(admin_client):
    Season.objects.all().delete()
    assert admin_client.get(SETTINGS_URL).status_code == 200
    assert Season.objects.count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("day", "kind"), [(date(2026, 12, 31), "new_year"), (date(2027, 2, 1), "winter"), (date(2026, 10, 14), "autumn")]
)
def test_drawn_season_logo_by_default(client, monkeypatch, day, kind):
    """Без своих логотипов в сезон — нарисованный вариант стандартного (scripts/draw_season_logos.py), того же размера."""
    _set_today(monkeypatch, day)
    header = _header(client.get("/").content.decode())
    assert f'<img src="/static/img/logo-header-{kind}.png" alt="Т-Парк" width="119" height="44"' in header


@pytest.mark.django_db
def test_uploaded_main_logo_beats_drawn_season_logo(client, monkeypatch, make_image):
    """Нарисованный вариант — от стандартного логотипа: если загружен свой основной, в сезон показывается он."""
    _set_today(monkeypatch, date(2026, 12, 31))
    site = SiteSettings.load()
    site.header_logo = make_image("main.png", size=(600, 150), fmt="PNG")
    site.save()
    assert re.search(r'width="176" height="44"', _header(client.get("/").content.decode()))


@pytest.mark.parametrize("kind", list(Kind))
def test_drawn_season_logos_match_default(kind):
    """Есть вариант для каждого сезона, размер — как у стандартного (3× от 119×44), лёгкий: грузится вместе с LCP."""
    path = Path(settings.BASE_DIR) / f"static/img/logo-header-{kind}.png"
    assert Image.open(path).size == (357, 132)
    assert path.stat().st_size < 8 * 1024
