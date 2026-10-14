# Сезонное оформление (зима и Новый год) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** сайт сам переходит в зимнее или новогоднее оформление по датам из админки: морозный фон шапок страниц, снег, на Новый год — гирлянда, свой логотип на сезон и сезонная плашка со ссылкой.

**Architecture:** новая модель `Season` (по записи на сезон, набор фиксирован: «Новый год», «Зима»), привязана к `SiteSettings` и редактируется inline-вкладкой «Сезонное оформление» в настройках сайта. Чистая логика выбора сезона — `apps/core/seasons.py` (`pick`); контекст-процессор `site` кладёт в контекст `season`, `base.html` ставит `<html data-season="…">`, и весь декор — это CSS в `tailwind/source.css` поверх существующих `.page-hero` и `partials/hero_decor.html`. Без JS и без новых зависимостей.

**Tech Stack:** Django 6.1, django-imagekit (спека логотипа), Unfold (`StackedInline` с `tab = True`), Tailwind 4 через `django-tailwind-cli`, pytest + pytest-django, Playwright (e2e).

**Spec:** отдельного документа нет — требования согласованы в разговоре 2026-10-14 и сведены в «Решения» ниже.

## Решения

| Вопрос | Решение | Почему |
|---|---|---|
| Где хранить сезоны | Модель `Season` (FK на `SiteSettings`, `kind` уникален), две записи создаёт data-миграция; в админке — inline без добавления и удаления | У каждого сезона одинаковый набор полей (даты, режим, логотип, плашка); 2×8 полей в `SiteSettings` раздули бы синглтон и форму |
| Даты | Строка «ДД.ММ» (`start`, `end`), повторяется каждый год; конец раньше начала — период через Новый год | Админ не должен каждый год заново вводить год; `DateField` требует год |
| Режим | `mode`: «По датам» / «Включено» (сейчас, без учёта дат) / «Выключено» | «Включено» — посмотреть оформление до сезона и включить вручную при раннем снеге; отдельный глобальный переключатель не нужен |
| Пересечение | Включённый вручную важнее дат; среди равных — `PRIORITY = [NEW_YEAR, WINTER]` | По умолчанию «Зима» 01.12–28.02 содержит «Новый год» 15.12–14.01 — в праздники должна побеждать новогодняя тема |
| Даты по умолчанию | «Новый год» 15.12–14.01, «Зима» 01.12–28.02, оба «По датам» | Старый Новый год включительно; админ поправит |
| Где плашка | Полоса `bg-navy` сразу **под** шапкой (уезжает при прокрутке), на всех страницах с `base.html` | Над sticky-шапкой она ломает мобильное меню (`h-[calc(100dvh-100%)]` от низа шапки не влезет в экран на высоту плашки) |
| Ссылка плашки | `CharField` с валидатором: путь на сайте (`/…`, но не `//` и `/\`) или `http(s)://…` | `URLField` не принимает относительные пути; `javascript:` и протокол-относительные ссылки — дыра |
| Логотип на сезон | `Season.logo` + `logo_img` (та же `logo_spec`, что у основного); в шапке: сезонный → основной → стандартный. В JSON-LD `Organization` — всегда основной | Поисковикам нужен постоянный логотип организации |
| Декор | Только CSS: фон `.page-hero` и пятна перекрашиваются по `html[data-season]`, снег — два псевдоэлемента с `transform` (компоновщик, без перерисовки), гирлянда — повторяющийся SVG в data-URI с мерцанием. Анимации — только при `prefers-reduced-motion: no-preference`. Всё внутри `.page-hero` (`overflow-hidden`), `pointer-events-none`, `aria-hidden` | Нет JS, не влияет на LCP, не перекрывает текст и клики |
| ETag/304 | Сезон зависит только от даты и настроек — одинаков для всех запросов дня | Правило проекта: в публичных шаблонах нет значений, меняющихся от запроса |
| Тесты и дата | Автофикстура в `tests/conftest.py` подменяет `apps.core.seasons.today` на 14.10.2026; сезонные тесты подменяют сами | Иначе в декабре половина тестов вёрстки и логотипа начнёт падать |

## Global Constraints

- Весь пользовательский текст (админка, сайт, справка) — на русском.
- Оранжевый (brand) — только кликабельное; серый текст не светлее `ink/65`.
- В публичных шаблонах нет значений, зависящих от запроса (ETag/304).
- Комментарии `{# … #}` — только однострочные.
- Админки наследуются от `SiteModelAdmin`; инлайны — из `unfold.admin`.
- Меняешь заметное администратору — обнови справку (`templates/admin/help/sections/settings.html`) и `help_text`.
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Период через Новый год (15.12–14.01): 31.12 и 01.01 — внутри, 15.01 и 14.12 — снаружи (тест в задаче 1).
2. «29.02» как граница в невисокосный год не роняет сайт; кривая дата, попавшая в базу в обход формы, не роняет сайт — сезон просто не показывается (тесты в задачах 1 и 2).
3. Записей сезонов нет (импорт со `--flush` удаляет `SiteSettings` каскадом) — сайт работает в обычном оформлении, а открытие настроек в админке и сам импорт создают записи заново (тесты в задачах 2 и 5).
4. Файл сезонного логотипа пропал — в шапке основной логотип, а без него стандартный, без 500 (тест в задаче 3).
5. Ссылка плашки `javascript:…`, `//evil.com`, `/\evil.com` — отклоняются формой (тест в задаче 1).

---

## Структура файлов

| Файл | Что меняется |
|---|---|
| `src/apps/core/seasons.py` (новый) | `Kind`, `Mode`, `PRIORITY`, `today()`, разбор и проверка «ДД.ММ», `covers`, `pick`, `validate_site_link` |
| `src/apps/core/models.py` | модель `Season`, функция `logo_display_width` вместо свойства `SiteSettings.header_logo_display_width` |
| `src/apps/core/migrations/0022_season.py`, `0023_create_seasons.py` (новые) | схема и две записи |
| `src/apps/core/apps.py` | `register_file_cleanup(Season)` |
| `src/apps/core/context_processors.py` | `season` в контексте, `header_logo(site, season)` |
| `src/apps/core/admin.py` | `SeasonInline`, создание недостающих сезонов в `change_view` |
| `src/apps/core/legacy/site.py` | `Season.ensure_for(site)` после импорта |
| `src/templates/base.html` | `data-season`, плашка |
| `src/templates/partials/season_banner.html` (новый) | плашка |
| `src/templates/partials/hero_decor.html` | классы пятен, снег, гирлянда |
| `src/tailwind/source.css` | цвета `frost`, сезонные стили |
| `src/templates/admin/help/sections/settings.html` | справка |
| `src/tests/conftest.py`, `src/tests/test_seasons.py` (новый), `src/tests/test_admin.py`, `src/tests/test_admin_help.py`, `src/tests/e2e/test_seasons.py` (новый) | тесты |
| `CLAUDE.md`, `docs/decisions.md` | документация |

---

### Task 1: Логика сезонов (`apps/core/seasons.py`)

**Files:**
- Create: `src/apps/core/seasons.py`
- Create: `src/tests/test_seasons.py`

**Interfaces:**
- Produces:
  - `Kind(models.TextChoices)`: `NEW_YEAR = "new_year"`, `WINTER = "winter"`; `Mode(models.TextChoices)`: `AUTO = "auto"`, `ON = "on"`, `OFF = "off"`; `PRIORITY: list[Kind]`.
  - `today() -> date`
  - `parse_day_month(value: str) -> tuple[int, int]` — `(месяц, день)`, `ValueError` на неверном вводе.
  - `format_day_month(value: str) -> str` — «1.12» → «01.12».
  - `validate_day_month(value: str) -> None`, `validate_site_link(value: str) -> None` — `ValidationError`.
  - `covers(start: str, end: str, day: date) -> bool`
  - `pick(seasons: Iterable, day: date | None = None)` — объект с атрибутами `kind`, `mode`, `start`, `end` или `None`.

- [ ] **Step 1: Написать падающие тесты**

`src/tests/test_seasons.py`:

```python
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
    [(date(2026, 12, 15), True), (date(2026, 12, 31), True), (date(2027, 1, 1), True), (date(2027, 1, 14), True),
     (date(2027, 1, 15), False), (date(2026, 12, 14), False), (date(2026, 7, 1), False)],
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
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_seasons.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.core.seasons'`.

- [ ] **Step 3: Реализация**

`src/apps/core/seasons.py`:

```python
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


class Mode(models.TextChoices):
    AUTO = "auto", "По датам"
    ON = "on", "Включено"
    OFF = "off", "Выключено"


# Если подходят несколько сезонов, показывается тот, что раньше: «Новый год» лежит внутри «Зимы».
PRIORITY = [Kind.NEW_YEAR, Kind.WINTER]

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


def pick(seasons: Iterable, day: date | None = None):
    """Сезон для показа или None (обычное оформление): включённый вручную важнее дат, среди равных — по PRIORITY."""
    day = day or today()
    ranked = sorted(seasons, key=lambda s: PRIORITY.index(s.kind))
    if forced := [s for s in ranked if s.mode == Mode.ON]:
        return forced[0]
    return next((s for s in ranked if s.mode == Mode.AUTO and _covers_safely(s, day)), None)


_url_validator = URLValidator(schemes=["http", "https"], message="Адрес страницы сайта (/events/…) или ссылка https://….")


def validate_site_link(value: str) -> None:
    """Путь на этом сайте (/events/…) или адрес http(s)://…; `javascript:`, `//чужой.сайт` и `/\\чужой.сайт` — нет."""
    if value.startswith("/") and not value.startswith(("//", "/\\")):
        return
    _url_validator(value)
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest tests/test_seasons.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add src/apps/core/seasons.py src/tests/test_seasons.py
git commit -m "Сезонное оформление: выбор сезона по датам"
```

---

### Task 2: Модель `Season`, миграции, фиксированная дата в тестах

**Files:**
- Modify: `src/apps/core/models.py` (импорты; после `class SiteSettings` — `logo_display_width`; новый класс после `class FounderFact`)
- Create: `src/apps/core/migrations/0022_season.py` (через `makemigrations`), `src/apps/core/migrations/0023_create_seasons.py`
- Modify: `src/apps/core/apps.py`, `src/apps/core/legacy/site.py`, `src/tests/conftest.py`
- Test: `src/tests/test_seasons.py`

**Interfaces:**
- Consumes: всё из задачи 1.
- Produces:
  - `Season` (поля `settings` FK `related_name="seasons"`, `kind`, `mode`, `start`, `end`, `logo`, `logo_width`, `logo_height`, спека `logo_img`, `banner_text`, `banner_link`; `Season.Kind`, `Season.Mode`; `Season.DEFAULT_DATES`; `Season.ensure_for(site) -> None`).
  - `logo_display_width(width: int | None, height: int | None) -> int | None` в `apps.core.models`; свойство `SiteSettings.header_logo_display_width` пока остаётся (его единственный пользователь — `context_processors.py`, переделка и удаление свойства — задача 3).

- [ ] **Step 1: Фиксированная дата для всех тестов**

В `src/tests/conftest.py` добавить импорт `from datetime import date` и фикстуру:

```python
@pytest.fixture(autouse=True)
def off_season(monkeypatch):
    """Сезонное оформление выбирается по сегодняшней дате — тесты идут в «обычный» день, сезонные подменяют дату сами."""
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 10, 14))
```

- [ ] **Step 2: Падающие тесты модели**

Дописать в `src/tests/test_seasons.py` (импорты — в начало файла):

```python
from apps.core.models import Season, SiteSettings


@pytest.mark.django_db
def test_migration_creates_both_seasons():
    seasons = {s.kind: s for s in Season.objects.all()}
    assert set(seasons) == {Kind.NEW_YEAR, Kind.WINTER}
    assert (seasons[Kind.NEW_YEAR].start, seasons[Kind.NEW_YEAR].end) == ("15.12", "14.01")
    assert (seasons[Kind.WINTER].start, seasons[Kind.WINTER].end) == ("01.12", "28.02")
    assert all(s.mode == Mode.AUTO and s.settings_id == SiteSettings.load().pk for s in seasons.values())
    assert [s.kind for s in Season.objects.all()] == [Kind.NEW_YEAR, Kind.WINTER]  # порядок в админке = приоритет


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
    season.end, season.banner_link = "28.02", "javascript:alert(1)"
    with pytest.raises(ValidationError) as exc:
        season.full_clean()
    assert "banner_link" in exc.value.message_dict


def test_logo_display_width():
    from apps.core.models import logo_display_width

    assert logo_display_width(600, 150) == 176
    assert logo_display_width(None, 150) is None
    assert logo_display_width(600, 0) is None
```

- [ ] **Step 3: Тесты падают**

Run: `cd src && uv run pytest tests/test_seasons.py -q`
Expected: FAIL — `ImportError: cannot import name 'Season'`.

- [ ] **Step 4: Модель**

В `src/apps/core/models.py`:

1. Импорт: `from apps.core import about_defaults, seasons` и `from apps.core.seasons import format_day_month, validate_day_month, validate_site_link`.
2. Добавить функцию модуля сразу после `HEADER_LOGO_HEIGHT = 44` (свойство `header_logo_display_width` не трогать — его уберёт задача 3):

```python
def logo_display_width(width: int | None, height: int | None) -> int | None:
    """Ширина логотипа в шапке при высоте `HEADER_LOGO_HEIGHT` — для width/height у <img> (без сдвига вёрстки)."""
    if not (width and height):
        return None
    return round(HEADER_LOGO_HEIGHT * width / height)
```

3. После `class FounderFact` добавить:

```python
class Season(models.Model):
    """Сезонное оформление (apps/core/seasons.py): по записи на сезон, набор сезонов фиксирован (`Kind`)."""

    Kind = seasons.Kind
    Mode = seasons.Mode
    DEFAULT_DATES = {Kind.NEW_YEAR: ("15.12", "14.01"), Kind.WINTER: ("01.12", "28.02")}

    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="seasons")
    kind = models.CharField("Сезон", max_length=16, choices=Kind.choices, unique=True, editable=False)
    mode = models.CharField(
        "Показ",
        max_length=8,
        choices=Mode.choices,
        default=Mode.AUTO,
        help_text="«По датам» — тема сама включается и выключается каждый год. «Включено» — сейчас, без учёта дат "
        "(например, посмотреть, как выглядит). Если подходят оба сезона, показывается «Новый год».",
    )
    start = models.CharField("С", max_length=5, validators=[validate_day_month], help_text="День и месяц: 15.12.")
    end = models.CharField(
        "По",
        max_length=5,
        validators=[validate_day_month],
        help_text="Включительно. Может быть в следующем году: 15.12 — 14.01.",
    )
    logo = photo_field(
        "Логотип на сезон",
        "logo",
        size=(3000, 1000),
        fmt=None,
        width_field="logo_width",
        height_field="logo_height",
        help_text="Заменяет логотип в шапке, пока тема показывается; требования — как у основного логотипа "
        "(вкладка «Логотип»). В разметку для поисковиков не попадает. Пусто — основной логотип.",
    )
    logo_width = models.PositiveIntegerField(null=True, editable=False)
    logo_height = models.PositiveIntegerField(null=True, editable=False)
    logo_img = logo_spec("logo", HEADER_LOGO_HEIGHT * 3)
    banner_text = models.CharField(
        "Плашка: текст",
        max_length=160,
        blank=True,
        help_text="Полоса под шапкой на всех страницах, пока тема показывается: например, «Новогодние корпоративы — "
        "бронируйте даты заранее». Пусто — плашки нет.",
    )
    banner_link = models.CharField(
        "Плашка: ссылка",
        max_length=500,
        blank=True,
        validators=[validate_site_link],
        help_text="Куда ведёт плашка: адрес страницы сайта (/events/…) или полная ссылка https://…. "
        "Пусто — плашка без ссылки.",
    )

    class Meta:
        verbose_name = "Сезонное оформление"
        verbose_name_plural = "Сезонное оформление"
        ordering = ["kind"]  # new_year < winter — как в seasons.PRIORITY

    def __str__(self):
        return self.get_kind_display()

    def clean(self):
        for field in ("start", "end"):
            try:
                setattr(self, field, format_day_month(getattr(self, field)))
            except ValueError:
                pass  # ошибку покажет валидатор поля

    @classmethod
    def ensure_for(cls, site: SiteSettings) -> None:
        """Создаёт недостающие сезоны: импорт со сбросом удаляет их вместе с настройками, а добавлять в админке нельзя."""
        for kind, (start, end) in cls.DEFAULT_DATES.items():
            cls.objects.get_or_create(kind=kind, defaults={"settings": site, "start": start, "end": end})
```

- [ ] **Step 5: Миграции**

Run: `cd src && uv run manage.py makemigrations core -n season`
Expected: создан `apps/core/migrations/0022_season.py` с `CreateModel(name="Season", …)`.

Создать `src/apps/core/migrations/0023_create_seasons.py`:

```python
from django.db import migrations

# Копия Season.DEFAULT_DATES: миграция не должна зависеть от текущего кода модели.
DEFAULT_DATES = {"new_year": ("15.12", "14.01"), "winter": ("01.12", "28.02")}


def create_seasons(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Season = apps.get_model("core", "Season")
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    for kind, (start, end) in DEFAULT_DATES.items():
        Season.objects.get_or_create(kind=kind, defaults={"settings": site, "start": start, "end": end})


class Migration(migrations.Migration):
    dependencies = [("core", "0022_season")]

    operations = [migrations.RunPython(create_seasons, migrations.RunPython.noop)]
```

- [ ] **Step 6: Удаление файлов и импорт**

В `src/apps/core/apps.py`: импорт `from apps.core.models import InfoPage, Season, SiteSettings` и строка `register_file_cleanup(Season)` после `register_file_cleanup(InfoPage)`.

В `src/apps/core/legacy/site.py` сразу после `site = SiteSettings.load()` (строка 24): `Season.ensure_for(site)` и `Season` в импорт из `apps.core.models`.

- [ ] **Step 7: Тесты проходят**

Run: `cd src && uv run pytest tests/test_seasons.py tests/legacy -q`
Expected: PASS (если `tests/legacy` проверяет число записей по моделям и падает на `Season` — добавить ожидание двух сезонов в тот тест).

- [ ] **Step 8: Коммит**

```bash
git add src/apps/core src/tests/conftest.py src/tests/test_seasons.py
git commit -m "Модель сезонного оформления и сезоны по умолчанию"
```

---

### Task 3: Сезон в контексте, логотип, плашка, разметка декора

**Files:**
- Modify: `src/apps/core/context_processors.py`
- Modify: `src/templates/base.html:2,36`
- Create: `src/templates/partials/season_banner.html`
- Modify: `src/templates/partials/hero_decor.html`
- Test: `src/tests/test_seasons.py`

**Interfaces:**
- Consumes: `seasons.pick`, `Season`, `logo_display_width` (задачи 1–2).
- Produces: в контексте шаблонов `season` (`Season` или `None`); `header_logo(site, season=None) -> dict`; классы `hero-spot-warm`, `hero-spot-cool`, `season-snow`, `season-garland`, `season-banner` (стили — задача 4).

- [ ] **Step 1: Падающие тесты**

Дописать в `src/tests/test_seasons.py` (импорты — в начало файла, к остальным):

```python
import re
from pathlib import Path

from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.test_seo import _organization


def _set_today(monkeypatch, day):
    monkeypatch.setattr("apps.core.seasons.today", lambda: day)


def _header(html):
    return html.split("<header", 1)[1].split("</header>", 1)[0]


@pytest.mark.django_db
def test_off_season_page_has_no_decor(client):
    Season.objects.update(banner_text="Корпоративы")
    html = client.get("/").content.decode()
    assert '<html lang="ru" class="motion-safe:scroll-smooth">' in html
    assert "season-snow" not in html and "season-banner" not in html


@pytest.mark.django_db
def test_new_year_decor_and_banner(client, monkeypatch):
    _set_today(monkeypatch, date(2026, 12, 31))
    Season.objects.filter(kind=Kind.NEW_YEAR).update(banner_text="Корпоративы <b>", banner_link="/events/")
    html = client.get("/").content.decode()
    assert '<html lang="ru" class="motion-safe:scroll-smooth" data-season="new_year">' in html
    assert 'class="season-snow' in html and 'class="season-garland' in html
    banner = html.split('class="season-banner', 1)[1].split("</div>", 1)[0]
    assert '<a href="/events/"' in banner and "Корпоративы &lt;b&gt;" in banner
    # Плашка — под шапкой, а не над ней (иначе мобильное меню не влезает в экран).
    assert html.index("</header>") < html.index('class="season-banner') < html.index('<main id="content"')


@pytest.mark.django_db
def test_winter_has_snow_without_garland_and_banner_without_link(client, monkeypatch):
    _set_today(monkeypatch, date(2027, 2, 1))
    Season.objects.filter(kind=Kind.WINTER).update(banner_text="Зимние программы")
    html = client.get("/").content.decode()
    assert 'data-season="winter"' in html
    assert 'class="season-snow' in html and "season-garland" not in html
    banner = html.split('class="season-banner', 1)[1].split("</div>", 1)[0]
    assert "<a " not in banner and "Зимние программы" in banner


@pytest.mark.django_db
def test_season_without_banner_text_has_no_banner(client, monkeypatch):
    _set_today(monkeypatch, date(2027, 2, 1))
    Season.objects.update(banner_link="/events/")
    assert "season-banner" not in client.get("/").content.decode()


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
    # Файл сезонного логотипа пропал — основной.
    Path(season.logo.path).unlink()
    header = _header(client.get("/").content.decode())
    assert re.search(r'width="176" height="44"', header)


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
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_seasons.py -q`
Expected: FAIL — нет `data-season`, `season-snow`, `season-banner`, сезонного логотипа.

- [ ] **Step 3: Контекст-процессор**

В `src/apps/core/models.py` удалить свойство `SiteSettings.header_logo_display_width` (его заменяет `logo_display_width`; проверить: `grep -rn header_logo_display_width src` — пусто после правки ниже).

В `src/apps/core/context_processors.py`:

```python
from apps.core import seasons
from apps.core.models import HEADER_LOGO_HEIGHT, InfoPage, Season, SiteSettings, logo_display_width
```

Заменить `header_logo`:

```python
def _uploaded_logo(obj, field: str, spec: str) -> dict | None:
    width = logo_display_width(getattr(obj, f"{field}_width"), getattr(obj, f"{field}_height"))
    if getattr(obj, field) and width and (url := safe_spec_url(obj, spec)):
        return {"url": url, "width": width, "height": HEADER_LOGO_HEIGHT}
    return None


def header_logo(site: SiteSettings, season: Season | None = None) -> dict:
    """Логотип для шапки: сезонный, если идёт сезон, иначе из настроек; нет файла или миниатюры — следующий,
    в конце — стандартный."""
    candidates = [(season, "logo", "logo_img"), (site, "header_logo", "header_logo_img")]
    for obj, field, spec in candidates:
        if obj is not None and (logo := _uploaded_logo(obj, field, spec)):
            return logo
    path, width, height = DEFAULT_HEADER_LOGO
    return {"url": static(path), "width": width, "height": height}
```

В `_site_context` после `phones = …`:

```python
    # Сезонное оформление (apps/core/seasons.py): одна выборка на запрос, None — обычное.
    season = seasons.pick(settings_obj.seasons.all())
```

и в словаре: `"season": season,` и `"header_logo": header_logo(settings_obj, season),`.

- [ ] **Step 4: Шаблоны**

`src/templates/base.html`, строка 2:

```django
<html lang="ru" class="motion-safe:scroll-smooth"{% if season %} data-season="{{ season.kind }}"{% endif %}>
```

после `{% include "partials/header.html" %}`:

```django
  {% include "partials/season_banner.html" %}
```

`src/templates/partials/season_banner.html`:

```django
{# Сезонная плашка (Season.banner_text): под шапкой и уезжает при прокрутке — над шапкой мобильное меню не влезло бы в экран. #}
{% if season.banner_text %}
<div class="season-banner bg-navy text-white">
  {% if season.banner_link %}
  <a href="{{ season.banner_link }}" class="mx-auto flex min-h-11 max-w-6xl items-center justify-center gap-1.5 px-4 py-2 text-center text-sm font-semibold hover:underline">
    <span>{{ season.banner_text }}</span><span class="icon h-4 w-4 text-brand-300" aria-hidden="true">{% include "icons/chevron-right.svg" %}</span>
  </a>
  {% else %}
  <p class="mx-auto max-w-6xl px-4 py-2.5 text-center text-sm font-semibold">{{ season.banner_text }}</p>
  {% endif %}
</div>
{% endif %}
```

`src/templates/partials/hero_decor.html` целиком:

```django
{# Мягкие пятна фирменных цветов за текстом шапки (.page-hero) — только декор; в сезон пятна перекрашивает CSS, поверх — снег, на Новый год — гирлянда. #}
<div class="hero-spot-warm pointer-events-none absolute -right-24 -top-32 -z-10 h-96 w-96 rounded-full bg-brand-300/35 blur-3xl" aria-hidden="true"></div>
<div class="hero-spot-cool pointer-events-none absolute -bottom-40 left-1/4 -z-10 h-96 w-96 rounded-full bg-pine-300/25 blur-3xl" aria-hidden="true"></div>
{% if season %}
<div class="season-snow pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true"></div>
{% if season.kind == "new_year" %}<div class="season-garland pointer-events-none absolute inset-x-0 top-0 -z-10 h-11" aria-hidden="true"></div>{% endif %}
{% endif %}
```

- [ ] **Step 5: Тесты проходят, остальные не сломались**

Run: `cd src && uv run pytest -q`
Expected: PASS всё (в том числе `tests/test_pages_home.py::test_header_logo_*`, `tests/test_query_counts.py`, `tests/test_layout.py::test_skip_link_and_reduced_motion`).

- [ ] **Step 6: Коммит**

```bash
git add src/apps/core/context_processors.py src/templates src/tests/test_seasons.py
git commit -m "Сезон в шаблонах: data-season, логотип на сезон, плашка"
```

---

### Task 4: Стили — морозная шапка, снег, гирлянда; e2e-проверка

**Files:**
- Modify: `src/tailwind/source.css` (`@theme` — цвета; новый блок без слоя после правил `.js-slider`)
- Create: `src/tests/e2e/test_seasons.py`

**Interfaces:**
- Consumes: классы и `data-season` из задачи 3.
- Produces: CSS-переменные `--color-frost-50/100/300`.

- [ ] **Step 1: Падающий e2e-тест**

`src/tests/e2e/test_seasons.py`:

```python
"""Сезонное оформление в браузере: декор не перехватывает клики, уважает «уменьшить движение», не распирает экран."""

from datetime import date

import pytest

pytest.importorskip("playwright")

from apps.core.models import Season, SiteSettings
from tests.e2e.test_mobile_layout import FIND_OVERFLOW

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

ANIMATION = "(sel) => getComputedStyle(document.querySelector(sel), '::before').animationName"


@pytest.fixture
def new_year(monkeypatch):
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 12, 31))
    Season.ensure_for(SiteSettings.load())  # transaction=True очищает базу — записи из миграции пропадают
    Season.objects.filter(kind=Season.Kind.NEW_YEAR).update(
        banner_text="Новогодние корпоративы в Т-Парке — бронируйте даты заранее", banner_link="/events/"
    )


def test_decor_is_inert_and_animated(live_server, page, new_year):
    page.goto(live_server.url + "/")
    for sel in (".season-snow", ".season-garland"):
        assert page.eval_on_selector(sel, "el => getComputedStyle(el).pointerEvents") == "none"
    assert page.evaluate(ANIMATION, ".season-snow") == "season-snow"
    hero_bg = page.eval_on_selector(".page-hero", "el => getComputedStyle(el).backgroundImage")
    assert "linear-gradient" in hero_bg and "226, 238, 248" in hero_bg  # frost-100 #e2eef8
    page.click(".season-banner a")
    assert page.url.endswith("/events/")


def test_reduced_motion_stops_snow(live_server, browser, new_year):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(live_server.url + "/")
    assert page.evaluate(ANIMATION, ".season-snow") == "none"
    context.close()


@pytest.mark.parametrize("width", [320, 375])
def test_banner_fits_narrow_screen_and_menu_still_fits(live_server, browser, new_year, width):
    context = browser.new_context(viewport={"width": width, "height": 700}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(live_server.url + "/")
    assert page.evaluate(FIND_OVERFLOW) == []
    page.click("header button.md\\:hidden")
    # Панель меню (partials/header.html): absolute top-full, высота 100dvh минус шапка.
    panel = page.locator('header div.overflow-y-auto[x-show="open"]')
    panel.wait_for(state="visible")
    assert panel.bounding_box()["y"] + panel.bounding_box()["height"] <= 700 + 1  # меню не уходит за низ экрана
    context.close()
```

- [ ] **Step 2: Тест падает**

Run: `make e2e ARGS="tests/e2e/test_seasons.py"` (из корня)
Expected: FAIL — у `.season-snow::before` `animationName == "none"`, фон шапки без `226, 238, 248`.

- [ ] **Step 3: Цвета**

В `@theme` в `src/tailwind/source.css`, после `--color-heather-700`:

```css
  /* Морозный голубой — сезонное оформление (html[data-season], apps/core/seasons.py) */
  --color-frost-50: #f3f8fc;
  --color-frost-100: #e2eef8;
  --color-frost-300: #b7d3ea;
```

- [ ] **Step 4: Сезонные стили**

В `src/tailwind/source.css` после правил `.js-slider .swiper-button-…` (без слоя):

```css
/* Сезонное оформление (apps/core/seasons.py): <html data-season="winter|new_year"> ставит base.html, снег и гирлянду
   выводит partials/hero_decor.html, всё — внутри .page-hero (overflow-hidden). Без слоя — иначе утилиты пятен
   (bg-brand-300/35) и градиент .page-hero из слоя components перебьют. Анимации — только без «уменьшить движение». */
html[data-season="winter"] .page-hero {
  background-image: linear-gradient(to bottom right, var(--color-frost-100), var(--color-frost-50) 55%, #fff);
}
html[data-season="new_year"] .page-hero {
  background-image: linear-gradient(to bottom right, var(--color-frost-100), var(--color-sand-100) 55%, var(--color-brand-50));
}
html[data-season="winter"] .hero-spot-warm { background-color: color-mix(in oklab, var(--color-frost-300) 55%, transparent); }
html[data-season="new_year"] .hero-spot-cool { background-color: color-mix(in oklab, var(--color-frost-300) 45%, transparent); }

/* Снег: два слоя (крупные медленнее, мелкие быстрее) — плитка из радиальных градиентов на псевдоэлементе выше шапки
   на одну плитку; он сдвигается transform-ом ровно на плитку (компоновщик, без перерисовки), шов не виден.
   Снежинка — белая точка с голубой каймой: просто белую на светлом фоне не видно. */
.season-snow::before,
.season-snow::after {
  content: "";
  position: absolute;
  inset: calc(-1 * var(--tile)) 0 0;
  background-size: var(--tile) var(--tile);
}
.season-snow::before {
  --tile: 220px;
  opacity: .9;
  background-image:
    radial-gradient(circle at 12% 18%, #fff 0 3px, var(--color-frost-300) 3.5px, transparent 4.5px),
    radial-gradient(circle at 58% 42%, #fff 0 2.5px, var(--color-frost-300) 3px, transparent 4px),
    radial-gradient(circle at 84% 8%, #fff 0 3px, var(--color-frost-300) 3.5px, transparent 4.5px),
    radial-gradient(circle at 34% 76%, #fff 0 2.5px, var(--color-frost-300) 3px, transparent 4px),
    radial-gradient(circle at 76% 88%, #fff 0 3px, var(--color-frost-300) 3.5px, transparent 4.5px);
}
.season-snow::after {
  --tile: 140px;
  opacity: .8;
  background-image:
    radial-gradient(circle at 22% 34%, #fff 0 1.5px, var(--color-frost-300) 2px, transparent 2.5px),
    radial-gradient(circle at 68% 64%, #fff 0 1.5px, var(--color-frost-300) 2px, transparent 2.5px),
    radial-gradient(circle at 90% 22%, #fff 0 1px, var(--color-frost-300) 1.5px, transparent 2px),
    radial-gradient(circle at 44% 92%, #fff 0 1px, var(--color-frost-300) 1.5px, transparent 2px);
}
@keyframes season-snow { to { transform: translateY(var(--tile)); } }

/* Гирлянда (Новый год): провод с лампочками — плитка 200×44 по горизонтали; ::after — свечение ламп, мерцает. */
.season-garland {
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='44'%3E%3Cpath d='M0 4Q100 34 200 4' fill='none' stroke='%232b4757' stroke-opacity='.45' stroke-width='1.5'/%3E%3Cg fill='%232b4757' fill-opacity='.7'%3E%3Crect x='38' y='13.6' width='4' height='4' rx='1'/%3E%3Crect x='78' y='18.4' width='4' height='4' rx='1'/%3E%3Crect x='118' y='18.4' width='4' height='4' rx='1'/%3E%3Crect x='158' y='13.6' width='4' height='4' rx='1'/%3E%3C/g%3E%3Cellipse cx='40' cy='23.1' rx='4' ry='5.5' fill='%23e5484d'/%3E%3Cellipse cx='80' cy='27.9' rx='4' ry='5.5' fill='%23f5b82e'/%3E%3Cellipse cx='120' cy='27.9' rx='4' ry='5.5' fill='%233f9142'/%3E%3Cellipse cx='160' cy='23.1' rx='4' ry='5.5' fill='%234a8fd6'/%3E%3C/svg%3E") repeat-x 0 0 / 200px 44px;
}
.season-garland::after {
  content: "";
  position: absolute;
  inset: 0;
  opacity: .6;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='44'%3E%3Cg fill-opacity='.35'%3E%3Ccircle cx='40' cy='23.1' r='10' fill='%23e5484d'/%3E%3Ccircle cx='80' cy='27.9' r='10' fill='%23f5b82e'/%3E%3Ccircle cx='120' cy='27.9' r='10' fill='%233f9142'/%3E%3Ccircle cx='160' cy='23.1' r='10' fill='%234a8fd6'/%3E%3C/g%3E%3C/svg%3E") repeat-x 0 0 / 200px 44px;
}
@keyframes season-twinkle { from { opacity: .15; } to { opacity: .9; } }

@media (prefers-reduced-motion: no-preference) {
  .season-snow::before { animation: season-snow 16s linear infinite; }
  .season-snow::after { animation: season-snow 9s linear infinite; }
  .season-garland::after { animation: season-twinkle 1.6s ease-in-out infinite alternate; }
}
```

- [ ] **Step 5: Сборка и переменные в CSS**

Run: `cd src && uv run manage.py tailwind build && grep -o -- "--color-frost-[0-9]*" static/css/tailwind.css | sort -u`
Expected: три переменные `--color-frost-50/100/300`. Если их нет (Tailwind выкинул «неиспользуемые» переменные темы) — вынести три строки в отдельный блок `@theme static { … }` и пересобрать.

- [ ] **Step 6: e2e проходит**

Run: `make e2e ARGS="tests/e2e/test_seasons.py tests/e2e/test_mobile_layout.py"` (из корня)
Expected: PASS.

- [ ] **Step 7: Визуальная проверка**

Снять скриншоты главной, страницы категории и `/info/<slug>/` в зимнем и новогоднем сезоне на 390 и 1280 px (скрипт Playwright в scratchpad, `today` подменить через `monkeypatch` в одноразовом тесте или временно включить «Включено» у сезона в dev-базе). Проверить глазами: снежинки видны, но не мешают читать заголовок; гирлянда не наезжает на заголовок на 320–390 px; плашка читается. Подобрать `opacity`/размеры снежинок, если нужно, — правки только в CSS.

- [ ] **Step 8: Коммит**

```bash
git add src/tailwind/source.css src/tests/e2e/test_seasons.py
git commit -m "Сезонное оформление: морозная шапка, снег и гирлянда на CSS"
```

---

### Task 5: Админка, справка, документация

**Files:**
- Modify: `src/apps/core/admin.py` (импорты, `SeasonInline` после `FounderFactInline`, `SiteSettingsAdmin.inlines`, `change_view`)
- Modify: `src/templates/admin/help/sections/settings.html`
- Modify: `src/tests/test_admin.py:41` (`_settings_post`), `src/tests/test_admin_help.py`
- Test: `src/tests/test_seasons.py`
- Modify: `CLAUDE.md`, `docs/decisions.md`

**Interfaces:**
- Consumes: `Season`, `seasons.pick` (задачи 1–2).

- [ ] **Step 1: Падающие тесты**

Дописать в `src/tests/test_seasons.py` (импорт — в начало файла):

```python
from django.urls import reverse

SETTINGS_URL = reverse("admin:core_sitesettings_change", args=[1])


def _season_post(seasons_data):
    """Форма настроек: пустые прочие инлайны + вкладка сезонов."""
    data = {"address": "село Восход"}
    for prefix in ("phones", "park_formats", "founder_facts"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0", f"{prefix}-MIN_NUM_FORMS": "0"})
    data.update({"seasons-TOTAL_FORMS": str(len(seasons_data)), "seasons-INITIAL_FORMS": str(len(seasons_data)),
                 "seasons-MIN_NUM_FORMS": "0"})
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
    assert html.count("Показывается на сайте") == 1 and html.count("Не показывается") == 1


@pytest.mark.django_db
def test_admin_saves_season_and_normalizes_dates(admin_client):
    season = Season.objects.get(kind=Kind.WINTER)
    fields = {"mode": "on", "start": "5.12", "end": "1.3", "banner_text": "Зима!", "banner_link": "/events/"}
    response = admin_client.post(SETTINGS_URL, _season_post([(season, fields)]))
    assert response.status_code == 302, response.content.decode()[:2000]
    season.refresh_from_db()
    assert (season.mode, season.start, season.end, season.banner_link) == ("on", "05.12", "01.03", "/events/")


@pytest.mark.django_db
def test_admin_rejects_bad_season_input(admin_client):
    season = Season.objects.get(kind=Kind.WINTER)
    fields = {"mode": "auto", "start": "31.02", "end": "01.03", "banner_link": "javascript:alert(1)"}
    html = admin_client.post(SETTINGS_URL, _season_post([(season, fields)])).content.decode()
    assert "Дата в виде ДД.ММ" in html and "Адрес страницы сайта" in html


@pytest.mark.django_db
def test_admin_restores_missing_seasons(admin_client):
    Season.objects.all().delete()
    assert admin_client.get(SETTINGS_URL).status_code == 200
    assert Season.objects.count() == 2
```

В `src/tests/test_admin.py` в `_settings_post` (строка 41) добавить `"seasons"` в кортеж префиксов:

```python
    for prefix in ("park_formats", "founder_facts", "seasons"):
```

В `src/tests/test_admin_help.py`:
- в `test_help_sections_complete` добавить `"Сезонное оформление"` в кортеж фраз;
- в `test_fields_explain_where_they_show` — `assert "под шапкой" in _help(Season, "banner_text")` и `assert "поисковиков" in _help(Season, "logo")`, импорт `Season` из `apps.core.models`.

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_seasons.py tests/test_admin.py tests/test_admin_help.py -q`
Expected: FAIL — на странице нет «Сезонное оформление», в справке нет фразы.

- [ ] **Step 3: Inline в админке**

В `src/apps/core/admin.py`: импорты `from unfold.admin import StackedInline` (рядом с `TabularInline`), `from apps.core import seasons`, `Season` в импорт моделей. После `FounderFactInline`:

```python
class SeasonInline(StackedInline):
    """Сезонное оформление: набор сезонов фиксирован (apps/core/seasons.py) — без добавления и удаления."""

    model = Season
    extra = 0
    tab = True
    can_delete = False
    fields = ["status", "mode", ("start", "end"), "logo", "banner_text", "banner_link"]
    readonly_fields = ["status"]

    def has_add_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ("start", "end"):
            field.widget.attrs["placeholder"] = "ДД.ММ"
        return field

    @admin.display(description="Сейчас")
    def status(self, obj):
        return "Показывается на сайте" if seasons.pick(Season.objects.all()) == obj else "Не показывается"
```

В `SiteSettingsAdmin`: `inlines = [PhoneInline, ParkFormatInline, FounderFactInline, SeasonInline]` и метод:

```python
    def change_view(self, request, object_id, form_url="", extra_context=None):
        Season.ensure_for(SiteSettings.load())  # после импорта со сбросом записей сезонов нет, а добавить их нельзя
        return super().change_view(request, object_id, form_url, extra_context)
```

- [ ] **Step 4: Справка**

В `src/templates/admin/help/sections/settings.html`:
- пункт «Логотип» заменить на: `<li><b>Логотип</b> — логотип в шапке. Пусто — стандартный. На время зимней или новогодней темы его можно заменить сезонным (вкладка «Сезонное оформление»).</li>`
- после пункта «Юридическое» добавить:

```html
  <li><b>Сезонное оформление</b> — зимняя и новогодняя темы: голубоватый фон шапок страниц и снег, на Новый год ещё гирлянда. У каждого сезона — свой логотип и плашка под шапкой на всех страницах (например, «Новогодние корпоративы» со ссылкой на страницу программ; пустой текст — плашки нет). «Показ»: «По датам» — тема сама включается и выключается каждый год, конец может быть в следующем году (15.12 — 14.01); «Включено» — сразу, без учёта дат, удобно посмотреть заранее; «Выключено» — не показывать. Если подходят оба сезона, показывается «Новый год». Строка «Сейчас» показывает, видна ли тема на сайте.</li>
```

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: PASS, ruff без замечаний (`test_no_missing_migrations` тоже зелёный).

- [ ] **Step 6: Документация**

`CLAUDE.md`, раздел `apps/core`, после пункта про `maps.py` добавить:

```markdown
  - `seasons.py` + модель `Season` — сезонное оформление («Новый год», «Зима»; набор фиксирован, записи — data-миграция `0023_create_seasons`, недостающие создаёт открытие настроек в админке и `import_legacy`): даты «ДД.ММ» каждый год (конец может быть в следующем году), режим «По датам» / «Включено» / «Выключено», при пересечении — `PRIORITY` (Новый год). Контекст `season` → `<html data-season>`, весь декор — CSS (`tailwind/source.css`: морозный `.page-hero`, снег, гирлянда; разметка — `partials/hero_decor.html`), плашка `partials/season_banner.html` — под шапкой (над ней ломает мобильное меню), логотип на сезон в шапке (в JSON-LD — всегда основной). Тесты идут 14.10.2026 — `today()` подменяет `tests/conftest.py`; inline «Сезонное оформление» в настройках сайта;
```

`docs/decisions.md`, в конец таблицы технических решений:

```markdown
| 44 | **Сезонное оформление** — модель `Season` (фиксированный набор, inline в настройках), даты «ДД.ММ» без года, режимы «По датам» / «Включено» / «Выключено», декор только на CSS по `html[data-season]`, плашка под шапкой | Тема включается сама каждый год и одинакова весь день (ETag/304 целы); без JS и библиотек — не влияет на LCP; над sticky-шапкой плашка ломала бы мобильное меню |
```

- [ ] **Step 7: Финальная проверка**

Run: `cd src && uv run pytest -q` и (из корня) `make e2e` и `uv run --project src pre-commit run --all-files`
Expected: всё зелёное.

- [ ] **Step 8: Коммит**

```bash
git add src/apps/core/admin.py src/templates/admin src/tests CLAUDE.md docs/decisions.md
git commit -m "Сезонное оформление в админке и справке"
```
