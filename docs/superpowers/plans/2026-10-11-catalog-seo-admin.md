# Каталог, SEO и админка после аудита — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Закрыть кодовые пункты аудита по каталогу, SEO и админке:
- sitemap без «сирот» и `Clean-param` с `ysclid`;
- цены в «₽» без «договорная руб»;
- редиректы при смене адреса страницы;
- черновики мероприятий, прошедшие — по ссылке, но без индексации;
- админка: поиск «сирот», группы меню в форме категории, различимые дубли, подсказки, русская страница удаления;
- настройки сайта — один запрос на страницу;
- команда приведения контента к единому виду.

**Architecture:**
- **Кеш на запрос:** новый модуль `apps/core/request_cache.py`. Через него контекст-процессоры и JSON-LD берут `SiteSettings` и меню один раз.
- **Редиректы:** модель `apps.core.Redirect`. Записи создаются автоматически в `save()` моделей со slug (`apps/core/redirects.py`), а отдаются из `RedirectFallbackMiddleware` на 404.
- **Правила текста** — чистые функции в `apps/core/content_fixes.py`, команда `normalize_content` применяет их к полям (по умолчанию — только показ правок).

**Tech Stack:** Django 6.1, Unfold, pytest-django.

**Spec:** `docs/site-audit-2026-10-11.md`. Этот план закрывает:
- P1 «Данные и адреса» — пп. 12 (редиректы и help_text; переименование slug делает администратор, см. roadmap), 13 (кодовая часть);
- P2 — пп. 21 (баг `price_display` и команда нормализации), 24;
- P3 — пп. 33, 40 (запросы к БД), 44, 46, 47.

**Ветка:** `feat/catalog-seo-admin` от `main` (после влития `fix/launch-hardening` или параллельно — планы не пересекаются по файлам, кроме `config/settings.py`: при конфликте слить вручную).

## Global Constraints

- Весь пользовательский текст — на русском. Бренд пишется «Т-Парк».
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Миграции: `uv run manage.py makemigrations <app> -n <имя>`. Сгенерированный файл просмотреть, лишние `AlterField` не коммитить.
- Админки наследуются от `apps.core.admin_utils.SiteModelAdmin`.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; pre-commit (ruff) должен проходить.
- Архитектурные изменения вносятся в `CLAUDE.md` (раздел Architecture) в той же задаче. Это касается:
  - новых модулей и middleware;
  - модели `Redirect`;
  - команды `normalize_content`.
- Публичные адреса существующих страниц не меняются.

## Review Focus

1. **Переименовали slug, потом вернули прежний (A → B → A).**
   - Ожидание: обе страницы без петли редиректов, по адресу A — 200.
   - Тест: задача 5, `test_rename_back_removes_redirect`.
2. **Цена — не число.** «договорная», «от 3500», «15 000».
   - Ожидание: «договорная» без «₽», «от 3500 ₽», «15 000 ₽».
   - Тест: задача 3, параметризованный `test_price_display`.
3. **Ссылка с метками на старый slug** (`/category/old/?utm_source=vk`).
   - Ожидание: 301 на новый адрес с теми же метками.
   - Тест: задача 5, `test_redirect_keeps_query_string`.
4. **Нормализация запущена дважды.**
   - Ожидание: второй прогон — 0 правок (идемпотентность), латинские T-park/T-camp в «О нас» не трогаются.
   - Тест: задача 10, `test_command_is_idempotent` и `test_fix_text_keeps_latin_formats`.
5. **Удаление категории, когда услуга входит ещё в одну.**
   - Ожидание: предупреждение называет только услуги, у которых это единственная категория.
   - Тест: задача 6, `test_delete_warns_only_about_services_left_without_category`.

---

### Task 1: Настройки сайта и меню — один раз на запрос

**Files:**
- Create: `src/apps/core/request_cache.py`
- Modify: `src/apps/core/models.py` (`SiteSettings.for_request`)
- Modify: `src/apps/core/context_processors.py`, `src/apps/catalog/context_processors.py`, `src/apps/texts/context_processors.py`
- Modify: `src/apps/core/structured_data.py` (`organization`, `service`, `event`)
- Test: `src/tests/test_query_counts.py` (новый)

**Interfaces:**
- Produces:
  - `cached_on_request(request, key: str, factory: Callable[[], T]) -> T`;
  - `SiteSettings.for_request(request) -> SiteSettings`.

- [ ] **Step 1: Падающие тесты** — `src/tests/test_query_counts.py`:

```python
"""Число запросов к БД не растёт с числом услуг и не повторяется на каждый шаблон админки."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Category, CategoryService, Service
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


def _queries_to(table: str, client, url: str) -> int:
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return sum(f'"{table}"' in q["sql"] for q in ctx.captured_queries)


def _category_with_services(n: int) -> Category:
    category = Category.objects.create(name=f"Парк {n}", is_published=True)
    for i in range(n):
        service = Service.objects.create(name=f"Услуга {n}-{i}", price="100")
        CategoryService.objects.create(category=category, service=service)
    return category


def test_category_page_settings_queries_do_not_grow_with_services(client):
    SiteSettings.load()
    small, big = _category_with_services(1), _category_with_services(6)
    small_count = _queries_to("core_sitesettings", client, small.get_absolute_url())
    assert _queries_to("core_sitesettings", client, big.get_absolute_url()) == small_count
    assert small_count <= 2  # контекст-процессор + make_seo (окончание заголовка)


def test_admin_form_loads_settings_once_per_request(admin_client):
    SiteSettings.load()
    category = Category.objects.create(name="Парк")
    url = reverse("admin:catalog_category_change", args=[category.pk])
    assert _queries_to("core_sitesettings", admin_client, url) <= 2  # контекст-процессор + справка SEO-вкладки
    # Меню витрины — 1; после задачи 6 поле «Группы меню» добавит ещё 2 (варианты и отмеченные). Без кеша — 5–6.
    assert _queries_to("catalog_categorygroup", admin_client, url) <= 3
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_query_counts.py -v`
Expected: FAIL — на большой категории запросов к настройкам больше, в админке их 5+.

- [ ] **Step 3: Модуль кеша** — `src/apps/core/request_cache.py`:

```python
"""Значения, общие для всего запроса: считаются один раз.

Контекст-процессоры выполняются на каждый шаблон, отрендеренный с request (в админке Unfold — 5–6 раз на страницу),
а JSON-LD спрашивает настройки сайта для каждой услуги. Кеш живёт в атрибуте запроса и умирает вместе с ним.
"""

from collections.abc import Callable


def cached_on_request[T](request, key: str, factory: Callable[[], T]) -> T:
    cache = request.__dict__.setdefault("_tpark_cache", {})
    if key not in cache:
        cache[key] = factory()
    return cache[key]
```

- [ ] **Step 4: `SiteSettings.for_request`** — в `apps/core/models.py`, рядом с `load()`:

```python
    @classmethod
    def for_request(cls, request) -> SiteSettings:
        """Настройки один раз на запрос (контекст-процессоры, JSON-LD); без запроса — как `load()`."""
        if request is None:
            return cls.load()
        from apps.core.request_cache import cached_on_request

        return cached_on_request(request, "site_settings", cls.load)
```

- [ ] **Step 5: Контекст-процессоры**

`apps/core/context_processors.py`: функцию `site` переименовать в `_site_context`, внутри `SiteSettings.load()` заменить на `SiteSettings.for_request(request)`. Затем добавить:

```python
from apps.core.request_cache import cached_on_request


def site(request):
    return cached_on_request(request, "site_context", lambda: _site_context(request))
```

`apps/catalog/context_processors.py`: так же — тело `menu` перенести в `_menu`, а `menu` обернуть:

```python
from apps.core.request_cache import cached_on_request


def menu(request):
    return cached_on_request(request, "menu_context", _menu)
```

(`_menu` без аргументов: `request` ему не нужен.)

`apps/texts/context_processors.py`:

```python
from django.utils.functional import SimpleLazyObject

from apps.core.request_cache import cached_on_request
from apps.texts.models import SiteText


def site_texts(request):
    """Все тексты сайта одним запросом на страницу — и только если она выводит хотя бы один (`{% text %}`)."""
    return {
        "site_texts": SimpleLazyObject(
            lambda: cached_on_request(request, "site_texts", lambda: dict(SiteText.objects.values_list("key", "text")))
        )
    }
```

- [ ] **Step 6: JSON-LD** — в `apps/core/structured_data.py` в функциях `organization`, `service`, `event` заменить `SiteSettings.load()` на `SiteSettings.for_request(request)`. В `service` — `SiteSettings.for_request(request).address_region`.

- [ ] **Step 7: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

Если второй assert админского теста даёт 3 и больше, посмотреть `ctx.captured_queries` (поле `sql`) и найти лишний источник. Не ослаблять тест, пока источник не понятен.

- [ ] **Step 8: CLAUDE.md** — в раздел `apps/core` после `files.py`:

```markdown
  - `request_cache.py` — `cached_on_request`: значение один раз на запрос; через него `SiteSettings.for_request(request)` (контекст-процессоры, JSON-LD) и сами контекст-процессоры `site`/`menu`/`site_texts` (в админке Unfold они вызываются на каждый шаблон);
```

- [ ] **Step 9: Коммит**

```bash
git add src/apps/core/request_cache.py src/apps/core/models.py src/apps/core/context_processors.py src/apps/catalog/context_processors.py src/apps/texts/context_processors.py src/apps/core/structured_data.py src/tests/test_query_counts.py CLAUDE.md
git commit -m "Настройки сайта, меню и тексты — один раз на запрос (категория: 28 → ~14 запросов, админка — без повторов)"
```

---

### Task 2: Sitemap без «сирот», robots с `ysclid`

**Files:**
- Modify: `src/apps/core/sitemaps.py:36-38`
- Modify: `src/apps/core/views.py:9` (`TRACKING_PARAMS`)
- Test: `src/tests/test_seo.py`

- [ ] **Step 1: Падающие тесты**

В `src/tests/test_seo.py` поправить `test_sitemap_lists_only_public_pages`: услуга «Со страницей» теперь должна быть в опубликованной категории. После `Service.objects.create(name="Со страницей", has_page=True)`:

```python
    open_category = Category.objects.get(name="Открытая")
    CategoryService.objects.create(category=open_category, service=Service.objects.get(name="Со страницей"))
```

Добавить новые тесты:

```python
def test_sitemap_skips_services_hidden_from_navigation(client):
    shown = Category.objects.create(name="Видна", is_published=True)
    hidden = Category.objects.create(name="Скрыта", is_published=False)
    in_menu = Service.objects.create(name="Зиплайн", has_page=True)
    CategoryService.objects.create(category=shown, service=in_menu)
    CategoryService.objects.create(category=hidden, service=in_menu)  # в двух категориях — один раз в sitemap
    only_hidden = Service.objects.create(name="Каяк", has_page=True)
    CategoryService.objects.create(category=hidden, service=only_hidden)
    Service.objects.create(name="Батут", has_page=True)  # без категории
    xml = client.get("/sitemap.xml").content.decode()
    assert xml.count("/service/ziplain/") == 1
    assert "/service/kaiak/" not in xml
    assert "/service/batut/" not in xml


def test_robots_cleans_yandex_and_tracking_params(client):
    clean = next(
        line for line in client.get("/robots.txt").content.decode().splitlines() if line.startswith("Clean-param:")
    )
    for param in ("ysclid", "_openstat", "utm_referrer", "from", "utm_source", "yclid"):
        assert param in clean.removeprefix("Clean-param: ").split("&"), param
```

(Slug проверены: `ziplain`, `kaiak`, `batut`.)

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_seo.py -v`
Expected: падают новые тесты (`kaiak`/`batut` есть в sitemap, `ysclid` нет в Clean-param).

- [ ] **Step 3: Реализация**

`apps/core/sitemaps.py`:

```python
class ServiceSitemap(ModelSitemap):
    def items(self):
        # Только услуги, которые видно через навигацию: со своей страницей и хотя бы в одной опубликованной категории.
        return (
            Service.objects.published()
            .filter(has_page=True, category_links__category__is_published=True)
            .distinct()
            .order_by("id")
        )
```

`apps/core/views.py`:

```python
TRACKING_PARAMS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "utm_referrer",
    "yclid",
    "ysclid",  # Яндекс сам добавляет его к переходам из выдачи
    "_openstat",
    "from",
    "gclid",
    "fbclid",
]
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest tests/test_seo.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add src/apps/core/sitemaps.py src/apps/core/views.py src/tests/test_seo.py
git commit -m "SEO: в sitemap только услуги из опубликованных категорий; Clean-param с ysclid, _openstat, utm_referrer, from"
```

---

### Task 3: Цена — «₽» только у числа

**Files:**
- Create: `src/apps/catalog/prices.py`
- Modify: `src/apps/catalog/models.py` (`Service.price_display`, help_text `price`)
- Test: `src/tests/test_catalog_models.py`
- Modify (ожидания): тесты, где проверяется «руб» — найти через `grep -rn "руб" src/tests`

**Interfaces:**
- Produces:
  - `apps.catalog.prices.format_price(text: str) -> str`;
  - `Service.price_display` — «900 ₽ / час», «от 3500 ₽ / участник», «15 000 ₽», «договорная».

- [ ] **Step 1: Падающий тест** — в `src/tests/test_catalog_models.py`:

```python
@pytest.mark.parametrize(
    ("price", "unit", "expected"),
    [
        ("900", "час", "900 ₽ / час"),
        ("15000", "", "15 000 ₽"),
        ("15 000", "день", "15 000 ₽ / день"),
        ("от 3500", "участник", "от 3500 ₽ / участник"),
        ("договорная", "", "договорная"),
        ("договорная", "час", "договорная / час"),
        ("", "час", ""),
    ],
)
def test_price_display(price, unit, expected):
    # В выводе неразрывные пробелы (перед «₽» и в «15 000»); сравниваем с обычными.
    assert Service(name="Услуга", price=price, price_unit=unit).price_display.replace("\u00a0", " ") == expected
```

(Если в файле нет `import pytest` и `from apps.catalog.models import Service` — добавить.)

- [ ] **Step 2: Тест падает**

Run: `cd src && uv run pytest tests/test_catalog_models.py -k price_display -v`
Expected: FAIL («900 руб / час», «договорная руб»).

- [ ] **Step 3: Реализация** — `src/apps/catalog/prices.py`:

```python
"""Цена услуги для витрины: «₽» только у числа, тысячи — через неразрывный пробел от 10 000."""

import re

_NUMBER = re.compile(r"^(?P<prefix>от\s+)?(?P<amount>\d[\d\s ]*)$", re.IGNORECASE)
NBSP = " "


def _group(digits: str) -> str:
    # 1500 — без пробела (так принято для четырёхзначных), 15 000 — с неразрывным пробелом.
    if len(digits) < 5:
        return digits
    return f"{int(digits):,}".replace(",", NBSP)


def format_price(text: str) -> str:
    text = (text or "").strip()
    match = _NUMBER.match(text)
    if not match:
        return text  # «договорная», «бесплатно» — как есть
    digits = re.sub(r"\D", "", match["amount"])
    prefix = "от " if match["prefix"] else ""
    return f"{prefix}{_group(digits)}{NBSP}₽"
```

В `Service` (`apps/catalog/models.py`):

```python
    @property
    def price_display(self) -> str:
        if not self.price:
            return ""
        amount = format_price(self.price)
        return f"{amount} / {self.price_unit}" if self.price_unit else amount
```

Импорт: `from apps.catalog.prices import format_price`. У поля `price` help_text: `"Число («1500», «от 3500») — на сайте с «₽». Или текстом: «договорная»."`

- [ ] **Step 4: Миграция help_text**

Run: `cd src && uv run manage.py makemigrations catalog -n price_help_text`

- [ ] **Step 5: Поправить старые ожидания**

Run: `cd src && grep -rn "руб" tests | grep -v "test_price_display"`. В каждом найденном assert, который проверяет вывод `price_display` на сайте, заменить «руб» на «₽». Учесть неразрывный пробел: `html.replace(" ", " ")` или `&nbsp;` — смотреть, как выводит шаблон. Данные-фикстуры («100 руб» в цене мероприятия — свободный текст) не трогать.

- [ ] **Step 6: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Коммит**

```bash
git add src/apps/catalog/prices.py src/apps/catalog/models.py src/apps/catalog/migrations src/tests
git commit -m "Цены: «₽» только у числа («договорная» без «руб»), 15 000 — с неразрывным пробелом"
```

---

### Task 4: Админка услуг — «сироты», категории в списке, различимые дубли

**Files:**
- Modify: `src/apps/catalog/admin.py` (`ServiceAdmin`, новый `ServicePlacementFilter`)
- Modify: `src/apps/catalog/models.py` (`Service.__str__`)
- Test: `src/tests/test_admin.py`, `src/tests/test_catalog_models.py`

**Interfaces:**
- Consumes: `Service.price_display` (задача 3).
- Produces:
  - фильтр `?placement=none|hidden` в списке услуг;
  - `str(service)` == «Название — 900 ₽ / час».

- [ ] **Step 1: Падающие тесты**

`src/tests/test_catalog_models.py`:

```python
def test_service_str_shows_price_to_tell_duplicates_apart():
    assert str(Service(name="Фрироуп", price="900", price_unit="час")).replace(" ", " ") == "Фрироуп — 900 ₽ / час"
    assert str(Service(name="Фрироуп")) == "Фрироуп"
```

`src/tests/test_admin.py` (импорты: `CategoryService`, `from apps.catalog.admin import ServiceAdmin`):

```python
def test_service_changelist_finds_services_hidden_from_navigation(admin_client):
    shown = Category.objects.create(name="Видна", is_published=True)
    hidden = Category.objects.create(name="Скрыта", is_published=False)
    CategoryService.objects.create(category=shown, service=Service.objects.create(name="Зиплайн"))
    CategoryService.objects.create(category=hidden, service=Service.objects.create(name="Каяк"))
    Service.objects.create(name="Батут")
    url = reverse("admin:catalog_service_changelist")

    no_category = admin_client.get(url, {"placement": "none"}).content.decode()
    assert "Батут" in no_category and "Каяк" not in no_category and "Зиплайн" not in no_category

    not_in_menu = admin_client.get(url, {"placement": "hidden"}).content.decode()
    assert "Батут" in not_in_menu and "Каяк" in not_in_menu and "Зиплайн" not in not_in_menu


def test_service_admin_lists_categories():
    category = Category.objects.create(name="Верёвочный парк")
    service = Service.objects.create(name="Зиплайн")
    CategoryService.objects.create(category=category, service=service)
    service = ServiceAdmin(Service, admin.site).get_queryset(None).get(pk=service.pk)
    assert ServiceAdmin(Service, admin.site).categories(service) == "Верёвочный парк"
    assert ServiceAdmin(Service, admin.site).categories(Service.objects.create(name="Батут")) == "—"
```

Внимание: если `get_queryset(None)` падает (Unfold обращается к request), использовать `RequestFactory().get("/")` с `request.user = admin_user` из фикстуры `admin_user`.

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_admin.py tests/test_catalog_models.py -k "hidden_from_navigation or lists_categories or str_shows_price" -v`
Expected: FAIL.

- [ ] **Step 3: Реализация**

`Service.__str__`:

```python
    def __str__(self):
        # С ценой: в автодополнении админки варианты одной услуги («Фрироуп» на час и на день) различимы.
        return f"{self.name} — {self.price_display}" if self.price_display else self.name
```

`apps/catalog/admin.py`:

```python
class ServicePlacementFilter(admin.SimpleListFilter):
    title = "Видна на сайте"
    parameter_name = "placement"

    def lookups(self, request, model_admin):
        return [
            ("none", "Без категории"),
            ("hidden", "Нет в меню (без опубликованной категории)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "none":
            return queryset.filter(category_links__isnull=True)
        if self.value() == "hidden":
            return queryset.exclude(category_links__category__is_published=True)
        return queryset
```

В `ServiceAdmin`:

```python
    list_display = ["name", "price_display", "categories", "is_published", "has_page"]
    list_filter = [ServicePlacementFilter, "is_published", "has_page", "category_links__category"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("category_links__category")

    @admin.display(description="Категории")
    def categories(self, obj):
        return ", ".join(link.category.name for link in obj.category_links.all()) or "—"
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add src/apps/catalog/admin.py src/apps/catalog/models.py src/tests/test_admin.py src/tests/test_catalog_models.py
git commit -m "Админка услуг: фильтр «Без категории / Нет в меню», колонка категорий, цена в названии для дублей"
```

---

### Task 5: Редиректы при смене адреса страницы

**Files:**
- Modify: `src/apps/core/models.py` (модель `Redirect`, `InfoPage.save`)
- Create: `src/apps/core/redirects.py`
- Modify: `src/apps/core/middleware.py` (`RedirectFallbackMiddleware`)
- Modify: `src/apps/core/slugs.py` (константа `SLUG_HELP`)
- Modify: `src/apps/catalog/models.py` (`Category.save`, `Service.save`, help_text slug)
- Modify: `src/apps/content/models.py` (`Event.save`, help_text slug)
- Modify: `src/apps/core/admin.py` (`RedirectAdmin`)
- Modify: `src/config/settings.py` (MIDDLEWARE, пункт меню UNFOLD)
- Test: `src/tests/test_redirects.py` (новый)

**Interfaces:**
- Produces:
  - модель `Redirect(old_path: str unique, new_path: str, created_at)`;
  - `remember_slug_change(instance) -> None` — вызывать в `save()` до `super().save()`, после заполнения slug;
  - `RedirectFallbackMiddleware`.

- [ ] **Step 1: Падающие тесты** — `src/tests/test_redirects.py`:

```python
"""Смена адреса страницы: старый адрес ведёт на новый (301), без цепочек и петель."""

import pytest
from django.utils import timezone

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core.models import InfoPage, Redirect

pytestmark = pytest.mark.django_db


def _rename(obj, slug):
    obj.slug = slug
    obj.save()
    return obj


def test_renamed_category_redirects(client):
    category = Category.objects.create(name="Школа", slug="shkola-2026", is_published=True)
    _rename(category, "shkola")
    response = client.get("/category/shkola-2026/")
    assert response.status_code == 301
    assert response["Location"] == "/category/shkola/"
    assert client.get("/category/shkola/").status_code == 200


def test_redirect_keeps_query_string(client):
    category = _rename(Category.objects.create(name="Школа", slug="old", is_published=True), "new")
    response = client.get("/category/old/?utm_source=vk")
    assert response["Location"] == "/category/new/?utm_source=vk"


def test_second_rename_does_not_chain(client):
    category = Category.objects.create(name="Школа", slug="a", is_published=True)
    _rename(category, "b")
    _rename(category, "c")
    assert client.get("/category/a/")["Location"] == "/category/c/"
    assert client.get("/category/b/")["Location"] == "/category/c/"


def test_rename_back_removes_redirect(client):
    category = Category.objects.create(name="Школа", slug="a", is_published=True)
    _rename(category, "b")
    _rename(category, "a")
    assert client.get("/category/a/").status_code == 200
    assert client.get("/category/b/")["Location"] == "/category/a/"
    assert not Redirect.objects.filter(old_path="/category/a/").exists()


def test_new_objects_and_unchanged_slugs_create_nothing():
    category = Category.objects.create(name="Школа", is_published=True)
    category.name = "Школа инструкторов"
    category.save()
    assert not Redirect.objects.exists()


@pytest.mark.parametrize(
    "make",
    [
        lambda: Service.objects.create(name="Троллей", slug="trollei-old", has_page=True),
        lambda: Event.objects.create(title="Слёт", slug="slet-old", date=timezone.localdate()),
        lambda: InfoPage.objects.create(title="Правила", slug="pravila-old"),
    ],
)
def test_other_pages_remember_slug_change(make):
    obj = make()
    old_url = obj.get_absolute_url()
    _rename(obj, obj.slug.removesuffix("-old"))
    assert Redirect.objects.get(old_path=old_url).new_path == obj.get_absolute_url()


def test_live_page_wins_over_redirect(client):
    Redirect.objects.create(old_path="/category/zhivaia/", new_path="/category/drugaia/")
    Category.objects.create(name="Живая", slug="zhivaia", is_published=True)
    assert client.get("/category/zhivaia/").status_code == 200
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_redirects.py -v`
Expected: ImportError (`Redirect`).

- [ ] **Step 3: Модель** — в `apps/core/models.py` (в конец файла):

```python
class Redirect(models.Model):
    """301 со старого адреса страницы на новый. Создаётся сам при смене slug (`apps.core.redirects`), можно и вручную."""

    old_path = models.CharField(
        "Старый адрес", max_length=255, unique=True, help_text="Путь от корня сайта: /category/shkola-2026/"
    )
    new_path = models.CharField("Новый адрес", max_length=255, help_text="Путь от корня сайта: /category/shkola/")
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Редирект"
        verbose_name_plural = "Редиректы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.old_path} → {self.new_path}"
```

- [ ] **Step 4: Запоминание смены slug** — `src/apps/core/redirects.py`:

```python
"""Смена адреса страницы (slug): старый адрес продолжает работать — 301 на новый (`RedirectFallbackMiddleware`)."""

from apps.core.models import Redirect


def remember_slug_change(instance) -> None:
    """Вызывать в `save()` модели со slug и `get_absolute_url()` — до записи, когда slug уже заполнен."""
    if instance.pk is None:
        return
    old_slug = type(instance)._default_manager.filter(pk=instance.pk).values_list("slug", flat=True).first()
    if not old_slug or old_slug == instance.slug:
        return
    old_path = type(instance)(slug=old_slug).get_absolute_url()
    new_path = instance.get_absolute_url()
    Redirect.objects.filter(old_path=new_path).delete()  # вернули прежний адрес — редирект с него больше не нужен
    Redirect.objects.filter(new_path=old_path).update(new_path=new_path)  # без цепочек редиректов
    Redirect.objects.update_or_create(old_path=old_path, defaults={"new_path": new_path})
```

В `save()` моделей `Category`, `Service` (`apps/catalog/models.py`), `Event` (`apps/content/models.py`) после блока `if not self.slug: …` и до `super().save(...)`:

```python
        remember_slug_change(self)
```

Импорт в этих модулях: `from apps.core.redirects import remember_slug_change`.

В `InfoPage.save()` (`apps/core/models.py`) — локальный импорт, чтобы не было цикла (`redirects` импортирует `models`):

```python
        from apps.core.redirects import remember_slug_change

        remember_slug_change(self)
```

- [ ] **Step 5: Middleware** — в `apps/core/middleware.py`:

```python
from django.http import HttpResponsePermanentRedirect


class RedirectFallbackMiddleware:
    """404 по адресу из «Редиректов» (страницу переименовали) — 301 на новый адрес с теми же параметрами (utm и т. п.)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        from apps.core.models import Redirect

        target = Redirect.objects.filter(old_path=request.path).values_list("new_path", flat=True).first()
        if not target:
            return response
        query = request.META.get("QUERY_STRING", "")
        return HttpResponsePermanentRedirect(f"{target}?{query}" if query else target)
```

(`HttpResponsePermanentRedirect` уже импортирован в модуле — не дублировать.)

`config/settings.py`, MIDDLEWARE — сразу после `"django.middleware.common.CommonMiddleware",`:

```python
    "apps.core.middleware.RedirectFallbackMiddleware",  # 404 по старому адресу переименованной страницы → 301
```

- [ ] **Step 6: Подсказка у slug**

В `apps/core/slugs.py`:

```python
SLUG_HELP = (
    "Часть адреса страницы. Пусто — из названия. Если поменять, со старого адреса будет автоматический редирект "
    "(раздел «Редиректы»), но лучше не менять адрес страниц, которые уже в поиске."
)
```

У полей `slug` моделей `Category`, `Service`, `InfoPage` — `help_text=SLUG_HELP`. У `Event` — `help_text=f"Пусто — из заголовка и года. {SLUG_HELP.split('. ', 1)[1]}"`. Это строка без «Пусто — из названия»: проверить её вывод в shell.

- [ ] **Step 7: Админка и меню**

`apps/core/admin.py`:

```python
@admin.register(Redirect)
class RedirectAdmin(SiteModelAdmin):
    list_display = ["old_path", "new_path", "created_at"]
    search_fields = ["old_path", "new_path"]
    fields = ["old_path", "new_path"]
```

(импорт `Redirect` из `apps.core.models`, `SiteModelAdmin` уже есть в модуле — проверить).

`config/settings.py`, `UNFOLD["SIDEBAR"]["navigation"]` — в группу «Сайт» последним пунктом:

```python
                    _nav("Редиректы", "alt_route", "admin:core_redirect_changelist"),
```

- [ ] **Step 8: Миграции и тесты**

```bash
cd src
uv run manage.py makemigrations core -n redirect
uv run manage.py makemigrations catalog content -n slug_help_text
uv run pytest -q
```

Expected: PASS, в том числе `test_every_registered_model_list_and_add_open` для «Редиректов».

- [ ] **Step 9: CLAUDE.md** — в раздел `apps/core`:

```markdown
  - `redirects.py` + модель `Redirect` + `middleware.RedirectFallbackMiddleware` — смена slug (категория, услуга, мероприятие, инфо-страница) сама создаёт 301 со старого адреса (без цепочек; вернули прежний — редирект удаляется); отдаётся только на 404, живая страница важнее; правка вручную — «Сайт → Редиректы»;
```

- [ ] **Step 10: Коммит**

```bash
git add src/apps src/config/settings.py src/tests/test_redirects.py CLAUDE.md
git commit -m "Редиректы: смена адреса страницы сама создаёт 301 со старого, раздел «Редиректы» в админке"
```

---

### Task 6: Админка категорий — группы меню в форме, счётчик услуг, предупреждение при удалении

**Files:**
- Modify: `src/apps/catalog/admin.py` (`CategoryAdminForm`, `CategoryAdmin`)
- Modify: `src/apps/catalog/models.py` (`Category.services_only_here`)
- Test: `src/tests/test_admin.py`

**Interfaces:**
- Produces:
  - `Category.services_only_here() -> QuerySet[Service]`;
  - поле формы `menu_groups`.

- [ ] **Step 1: Падающие тесты** — в `src/tests/test_admin.py` (импорт `CategoryGroup`, `CategoryService`):

```python
def _category_post(category, **extra):
    """Данные формы категории без фото и услуг (инлайны пустые)."""
    data = {"name": category.name, "slug": category.slug, "description": "", "order": "0"}
    for prefix in ("photos", "service_links"):
        data |= {
            f"{prefix}-TOTAL_FORMS": "0",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
    return data | extra


def test_category_form_sets_menu_groups(admin_client):
    active, rent = CategoryGroup.objects.create(name="Активный отдых"), CategoryGroup.objects.create(name="Аренда")
    category = Category.objects.create(name="Парк")
    rent.categories.add(category)
    url = reverse("admin:catalog_category_change", args=[category.pk])
    assert list(admin_client.get(url).context["adminform"].form["menu_groups"].initial) == [rent]
    response = admin_client.post(url, _category_post(category, menu_groups=[str(active.pk)]))
    assert response.status_code == 302, response.context["adminform"].form.errors if response.context else ""
    assert list(category.groups.all()) == [active]


def test_category_changelist_shows_groups_and_service_count(admin_client):
    group = CategoryGroup.objects.create(name="Активный отдых")
    category = Category.objects.create(name="Парк")
    group.categories.add(category)
    for name in ("Зиплайн", "Каяк"):
        CategoryService.objects.create(category=category, service=Service.objects.create(name=name))
    html = admin_client.get(reverse("admin:catalog_category_changelist")).content.decode()
    assert "Активный отдых" in html
    assert re.search(r">\s*2\s*<", html)


def test_delete_warns_only_about_services_left_without_category(admin_client):
    category, other = Category.objects.create(name="Парк"), Category.objects.create(name="Сплавы")
    only_here = Service.objects.create(name="Зиплайн")
    shared = Service.objects.create(name="Каяк")
    CategoryService.objects.create(category=category, service=only_here)
    CategoryService.objects.create(category=category, service=shared)
    CategoryService.objects.create(category=other, service=shared)
    html = admin_client.get(reverse("admin:catalog_category_delete", args=[category.pk])).content.decode()
    assert "Без категории останутся" in html
    assert "Зиплайн" in html.split("Без категории останутся", 1)[1].split("<", 1)[0]
    assert "Каяк" not in html.split("Без категории останутся", 1)[1].split("<", 1)[0]
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_admin.py -k "menu_groups or service_count or delete_warns" -v`
Expected: FAIL.

- [ ] **Step 3: Модель** — в `Category`:

```python
    def services_only_here(self):
        """Услуги, у которых эта категория — единственная: после её удаления они пропадут из навигации."""
        return Service.objects.filter(category_links__category=self).exclude(
            category_links__category__in=Category.objects.exclude(pk=self.pk)
        )
```

- [ ] **Step 4: Админка** — `apps/catalog/admin.py`.

Импорты: `from django.contrib import admin, messages`, `from django.db.models import Count`, `from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget`.

```python
class CategoryAdminForm(forms.ModelForm):
    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")
    menu_groups = forms.ModelMultipleChoiceField(
        CategoryGroup.objects.order_by("order", "id"),
        required=False,
        label="Группы меню",
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        help_text="Где категория видна в меню «Услуги» и на главной. Без группы её найдут только по прямой ссылке.",
    )

    class Meta:
        model = Category
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["menu_groups"].initial = list(self.instance.groups.all())
```

В `CategoryAdmin`:

```python
    list_display = ["name", "menu_groups_display", "services_count", "is_published"]
```

- в fieldset «Основное» после `"slug"` добавить `"menu_groups"`;

```python
    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .annotate(services_total=Count("service_links", distinct=True))
            .prefetch_related("groups")
        )

    @admin.display(description="Группы меню")
    def menu_groups_display(self, obj):
        return ", ".join(group.name for group in obj.groups.all()) or "— нет в меню"

    @admin.display(description="Услуг", ordering="services_total")
    def services_count(self, obj):
        return obj.services_total

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.groups.set(form.cleaned_data["menu_groups"])
        append_images(CategoryPhoto, form.cleaned_data.get("bulk_photos") or [], category=form.instance)

    def delete_view(self, request, object_id, extra_context=None):
        category = self.get_object(request, object_id)
        if request.method == "GET" and category:
            names = list(category.services_only_here().values_list("name", flat=True))
            if names:
                messages.warning(
                    request,
                    f"Без категории останутся услуги ({len(names)}): {', '.join(names)}. "
                    "На сайте их не будет в меню — привяжите их к другой категории или снимите с публикации.",
                )
        return super().delete_view(request, object_id, extra_context)
```

(Существующий `save_related` заменить этим — `append_images` в нём уже был.)

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS. Если `test_delete_warns…` не находит текст — убедиться, что Unfold выводит messages на странице удаления (`unfold/templates/admin/base.html` → блок messages). Если не выводит, передать предупреждение через `extra_context={"orphan_warning": …}` и переопределить `templates/admin/catalog/category/delete_confirmation.html` (`{% extends "admin/delete_confirmation.html" %}` + блок с текстом).

- [ ] **Step 6: Коммит**

```bash
git add src/apps/catalog src/tests/test_admin.py
git commit -m "Админка категорий: группы меню прямо в форме, колонки «Группы меню» и «Услуг», предупреждение при удалении"
```

---

### Task 7: Мероприятия — черновики; прошедшие без индексации

**Files:**
- Modify: `src/apps/content/models.py` (`EventQuerySet`, поле `is_published`, help_text `show_after_date`)
- Modify: `src/apps/content/views.py` (`events`, `event_detail`)
- Modify: `src/apps/catalog/views.py:27` (главная)
- Modify: `src/apps/core/sitemaps.py` (`EventSitemap`)
- Modify: `src/apps/content/admin.py` (`EventAdmin`)
- Modify: `src/templates/base.html` (meta robots)
- Test: `src/tests/test_events.py`

**Interfaces:**
- Produces:
  - `Event.is_published` (по умолчанию `True`);
  - `Event.objects.published()`;
  - ключ `seo["noindex"]: bool`, его выводит `base.html`.

- [ ] **Step 1: Падающие тесты** — в `src/tests/test_events.py` заменить `test_hidden_past_event_is_404`:

```python
def test_past_event_without_flag_opens_by_link_but_is_not_indexed(client):
    event = make_event("Прошлый слёт", days=-5)
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert '<meta name="robots" content="noindex">' in response.content.decode()
    assert event.get_absolute_url() not in client.get("/sitemap.xml").content.decode()
    assert "Прошлый слёт" not in client.get("/events/").content.decode()


def test_visible_events_are_indexed(client):
    for event in (make_event(days=3), make_event("Архив", days=-5, show_after_date=True)):
        assert 'name="robots"' not in client.get(event.get_absolute_url()).content.decode()


def test_draft_event_is_hidden_everywhere(client):
    site = SiteSettings.load()
    site.home_show_events = True
    site.save()
    make_event("Опубликованное", days=2)
    draft = make_event("Черновик", days=3, is_published=False)
    assert client.get(draft.get_absolute_url()).status_code == 404
    for url in ("/", "/events/", "/sitemap.xml"):
        html = client.get(url).content.decode()
        assert "Черновик" not in html and draft.slug not in html, url
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_events.py -v`
Expected: FAIL (404 у прошедшего; `is_published` — TypeError).

- [ ] **Step 3: Модель**

```python
class EventQuerySet(PublishedQuerySet):
```

(Импорт `PublishedQuerySet` уже есть в модуле.)

Поля `Event`:

```python
    show_after_date = models.BooleanField(
        "Показывать после даты",
        default=False,
        help_text="Оставить в списке «Прошедшие» и в поиске. Без галочки прошедшее открывается только по прямой ссылке.",
    )
    is_published = models.BooleanField(
        "Опубликовано", default=True, help_text="Снимите, чтобы подготовить мероприятие заранее: на сайте его не будет."
    )
```

- [ ] **Step 4: Публичные выборки** — добавить `.published()`:
  - `apps/catalog/views.py:27` — `Event.objects.published().upcoming()[:HOME_EVENTS]`;
  - `apps/content/views.py` — `Event.objects.published().upcoming(today)`, `Event.objects.published().past_visible(today)`, `related`: `Event.objects.published().upcoming().exclude(pk=event.pk)`;
  - `apps/core/sitemaps.py` — `Event.objects.published().visible()`.

Проверить, что других публичных вызовов нет: `grep -rnE "Event\.objects\.(upcoming|past|visible)" src/apps`. Админский фильтр (`queryset.upcoming`) не трогать — в админке нужны и черновики.

`event_detail`:

```python
def event_detail(request, slug):
    event = get_object_or_404(Event.objects.published(), slug=slug)
    …
    seo = make_seo(…)
    # Прошедшее без «Показывать после даты»: по прямой ссылке открывается, в поиск не попадает.
    seo["noindex"] = event.is_past and not event.show_after_date
```

- [ ] **Step 5: Шаблон** — `templates/base.html`, после строки `<meta name="description" …>`:

```django
  {% if seo.noindex %}<meta name="robots" content="noindex">{% endif %}
```

- [ ] **Step 6: Админка** — `EventAdmin`:

```python
    list_display = ["title", "date", "is_published", "show_after_date"]
    list_editable = ["is_published"]
    list_filter = [EventPeriodFilter, "is_published", "show_after_date"]
```

В fieldset «Основное» строку `"show_after_date"` заменить на `("is_published", "show_after_date")`.

- [ ] **Step 7: Миграция и тесты**

```bash
cd src && uv run manage.py makemigrations content -n event_is_published && uv run pytest -q
```

Expected: PASS.

- [ ] **Step 8: CLAUDE.md** — в описании `apps/content` фразу «страница `/events/<slug>/` и sitemap — только для `visible()`» заменить на:

```markdown
черновики (`is_published=False`) — 404; страница `/events/<slug>/` открывается у всех опубликованных, но прошедшее без «Показывать после даты» — с `noindex` и вне sitemap и списков (`visible()`)
```

- [ ] **Step 9: Коммит**

```bash
git add src/apps src/templates/base.html src/tests/test_events.py CLAUDE.md
git commit -m "Мероприятия: черновики; прошедшие без «Показывать после даты» — по ссылке, но с noindex"
```

---

### Task 8: Подсказки в формах и инструкция на главной админки

**Files:**
- Modify: `src/apps/catalog/models.py` (help_text: `Category.preview`, `CategoryPhoto.image`, `ServicePhoto.image`, `Service.short_description`, `Service.description`)
- Create: `src/templates/admin/index.html`, `src/templates/admin/dashboard_help.html`
- Test: `src/tests/test_admin.py`

- [ ] **Step 1: Падающий тест**

```python
def test_admin_index_has_instructions(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    for heading in ("Как добавить услугу", "Как показать категорию в меню", "Фото", "Адрес страницы"):
        assert heading in html


def test_photo_fields_explain_cropping():
    from apps.catalog.models import Category, CategoryPhoto, Service, ServicePhoto

    assert "3:2" in Category._meta.get_field("preview").help_text
    for model in (CategoryPhoto, ServicePhoto):
        assert "16:9" in model._meta.get_field("image").help_text
    assert "карточке" in Service._meta.get_field("short_description").help_text
```

- [ ] **Step 2: Тест падает**

Run: `cd src && uv run pytest tests/test_admin.py -k "instructions or cropping" -v`
Expected: FAIL.

- [ ] **Step 3: help_text** — в `apps/catalog/models.py` (`photo_field` и `HtmlField` пробрасывают `**kwargs`):

```python
PREVIEW_HELP = "Карточка на главной и шапка страницы категории: кадр обрезается до 3:2, главное — ближе к центру."
SLIDE_HELP = "Слайдер: кадр обрезается до 16:9 (как экран телевизора) — людей снимайте с запасом сверху и снизу."
```

- `preview = photo_field("Превью для главной", "catalog/previews", size=(1080, 720), help_text=PREVIEW_HELP)`
- `image = photo_field("Фото", "catalog/categories", blank=False, help_text=SLIDE_HELP)` — и так же в `ServicePhoto`
- `short_description = HtmlField("Краткое описание", help_text="1–2 предложения. Видно в карточке на странице категории; у услуги без отдельной страницы раскрывается в списке. Если SEO-описание пустое — начало этого текста идёт в поисковики.")`
- `description = HtmlField("Полное описание", help_text="Текст отдельной страницы услуги (нужна галочка «Отдельная страница»).")`

- [ ] **Step 4: Главная админки**

`src/templates/admin/index.html` — копия `unfold/templates/admin/index.html` с инструкцией сверху:

```django
{% extends 'admin/base.html' %}
{% comment %}
  Копия unfold/templates/admin/index.html + инструкция для администратора (admin/dashboard_help.html).
  Сверять с оригиналом при обновлении Unfold.
{% endcomment %}
{% load i18n %}

{% block title %}{% if subtitle %}{{ subtitle }} | {% endif %}{{ title }} | {{ site_title|default:_('Django site admin') }}{% endblock %}

{% block branding %}
    {% include "unfold/helpers/site_branding.html" %}
{% endblock %}

{% block content %}
    {% include "admin/dashboard_help.html" %}
    {% include "unfold/helpers/dashboard_default.html" %}
{% endblock %}
```

`src/templates/admin/dashboard_help.html`:

```django
<section class="mb-8 grid gap-4 md:grid-cols-2" aria-label="Как работать с сайтом">
  <div class="rounded-default border border-base-200 bg-white p-5 dark:border-base-800 dark:bg-base-900">
    <h2 class="mb-2 font-semibold text-font-important-light dark:text-font-important-dark">Как добавить услугу</h2>
    <ol class="list-decimal space-y-1 pl-5">
      <li>«Каталог → Услуги → Добавить»: название, цена числом («1500»), за что («час», «участник»).</li>
      <li>«Краткое описание» — 1–2 предложения для карточки. Полное — только если нужна «Отдельная страница».</li>
      <li>Вкладка «Категории» — без категории услугу на сайте не найти (фильтр «Видна на сайте» в списке услуг).</li>
    </ol>
  </div>
  <div class="rounded-default border border-base-200 bg-white p-5 dark:border-base-800 dark:bg-base-900">
    <h2 class="mb-2 font-semibold text-font-important-light dark:text-font-important-dark">Как показать категорию в меню</h2>
    <p>В форме категории отметьте «Группы меню» и «Опубликовано». Без группы категория открывается только по прямой ссылке.</p>
  </div>
  <div class="rounded-default border border-base-200 bg-white p-5 dark:border-base-800 dark:bg-base-900">
    <h2 class="mb-2 font-semibold text-font-important-light dark:text-font-important-dark">Фото</h2>
    <p>Горизонтальные, от 1600 px по ширине, до 20 МБ и 50 Мп. В слайдере кадр обрезается до 16:9, в карточках — до 3:2 или 4:3: держите главное ближе к центру. Много фото сразу — вкладка «Загрузка фото».</p>
  </div>
  <div class="rounded-default border border-base-200 bg-white p-5 dark:border-base-800 dark:bg-base-900">
    <h2 class="mb-2 font-semibold text-font-important-light dark:text-font-important-dark">Адрес страницы</h2>
    <p>Поле «Адрес страницы» лучше не менять у страниц, которые уже в поиске. Если поменять — старый адрес сам будет вести на новый («Сайт → Редиректы»).</p>
  </div>
</section>
```

Классы `rounded-default`, `border-base-200`, `text-font-important-light` — из темы Unfold. Проверить в браузере (`make run`, `/admin/`), что карточки выглядят как остальные блоки. Если какой-то класс не собран в CSS Unfold, взять классы из `unfold/templates/unfold/helpers/` (например, у `app_list`).

- [ ] **Step 5: Миграция и тесты**

```bash
cd src && uv run manage.py makemigrations catalog -n admin_help_texts && uv run pytest -q
```

- [ ] **Step 6: CLAUDE.md** — в абзац про админки:

```markdown
Главная админки — `templates/admin/index.html` (копия шаблона Unfold + инструкция `admin/dashboard_help.html`), сверять при обновлении Unfold.
```

- [ ] **Step 7: Коммит**

```bash
git add src/apps/catalog src/templates/admin src/tests/test_admin.py CLAUDE.md
git commit -m "Админка: подсказки про обрезку фото и описания, короткая инструкция на главной"
```

---

### Task 9: Русская страница удаления и мелкие строки Unfold

**Files:**
- Modify: `src/locale/ru/LC_MESSAGES/django.po`, `src/locale/ru/LC_MESSAGES/django.mo`
- Modify: `src/apps/catalog/models.py` (строка связи «группа — категория»)
- Test: `src/tests/test_admin.py`

- [ ] **Step 1: Падающий тест**

```python
ENGLISH_LEFTOVERS = [
    "Are you sure",
    "related items will be deleted",
    "This item will be deleted",
    "Click to cancel",
    "Select action",
    "Available shortcuts",
    "Toggle dark/light mode",
    "object (",
]


def test_delete_confirmation_and_forms_are_russian(admin_client):
    group = CategoryGroup.objects.create(name="Активный отдых")
    category = Category.objects.create(name="Парк")
    group.categories.add(category)
    pages = [
        reverse("admin:catalog_category_delete", args=[category.pk]),
        reverse("admin:catalog_category_change", args=[category.pk]),
        reverse("admin:catalog_category_changelist"),
    ]
    for url in pages:
        html = admin_client.get(url).content.decode()
        for phrase in ENGLISH_LEFTOVERS:
            assert phrase not in html, (url, phrase)
```

- [ ] **Step 2: Тест падает**

Run: `cd src && uv run pytest tests/test_admin.py -k russian -v`
Expected: FAIL; в сообщении будет первая найденная английская фраза.

- [ ] **Step 3: Строка связи M2M** — в конец `apps/catalog/models.py`:

```python
# Связь «группа меню — категория» (авто-модель M2M): на странице удаления в админке вместо
# «Связь categorygroup-category: CategoryGroup_categories object (13)».
_GroupLink = CategoryGroup.categories.through
_GroupLink._meta.verbose_name = "место в группе меню"
_GroupLink.__str__ = lambda link: f"«{link.category}» в группе «{link.categorygroup}»"
```

- [ ] **Step 4: Переводы** — дописать в `django.po`.

Unfold пишет `"…"` и `'…'` прямыми кавычками, а в каталоге Django — «ёлочки» `“…”`. Поэтому русский перевод Django не находится. msgid ниже скопированы из `unfold/templates/admin/delete_confirmation.html` и шаблонов Unfold. Если тест ещё находит английский, найти точный текст: `grep -rn "<фраза>" src/.venv/lib/python3.14/site-packages/unfold/` — и добавить msgid.

```po
# unfold/templates/admin/delete_confirmation.html — прямые кавычки вместо “…” у Django
#, python-format
msgid "Are you sure you want to delete the %(object_name)s \"%(escaped_object)s\"? All of the following related items will be deleted:"
msgstr "Удалить %(object_name)s «%(escaped_object)s»? Вместе с ним будут удалены:"

#, python-format
msgid "Deleting the %(object_name)s '%(escaped_object)s' would result in deleting related objects, but your account doesn't have permission to delete the following types of objects:"
msgstr "Удаление %(object_name)s «%(escaped_object)s» затронет связанные объекты, но у вас нет прав удалять объекты этих типов:"

#, python-format
msgid "Deleting the %(object_name)s '%(escaped_object)s' would require deleting the following protected related objects:"
msgstr "Чтобы удалить %(object_name)s «%(escaped_object)s», сначала нужно удалить защищённые связанные объекты:"

# Инлайны, списки, горячие клавиши, тема
msgid "This item will be deleted."
msgstr "Эта запись будет удалена."

msgid "Click to cancel"
msgstr "Нажмите, чтобы отменить"

msgid "Select action"
msgstr "Выберите действие"

msgid "Select action to run"
msgstr "Выберите действие"

msgid "Select value"
msgstr "Выберите значение"

msgid "Available shortcuts"
msgstr "Горячие клавиши"

msgid "Global shortcuts"
msgstr "Общие"

msgid "Changelist shortcuts"
msgstr "В списке"

msgid "Command tool shortcuts"
msgstr "В поиске команд"

msgid "Open shortcuts list"
msgstr "Список горячих клавиш"

msgid "Toggle dark/light mode"
msgstr "Светлая или тёмная тема"

msgid "Light"
msgstr "Светлая"

msgid "Dark"
msgstr "Тёмная"

msgid "System"
msgstr "Как в системе"
```

Для msgid с `\"` проверить: в шаблоне `{% blocktranslate with escaped_object=object %}…"{{ escaped_object }}"…` — после компиляции msgid содержит `"%(escaped_object)s"`. В `.po` кавычки внутри строки экранируются `\"`.

- [ ] **Step 5: Компиляция**

Run: `cd src && uv run manage.py compilemessages -l ru` (нужен gettext: `brew install gettext`)
Expected: `processing file django.po in …/locale/ru/LC_MESSAGES`.

- [ ] **Step 6: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS. Если какая-то фраза осталась, найти её msgid (шаг 4), дописать, повторить шаги 5–6.

- [ ] **Step 7: Коммит**

```bash
git add src/locale src/apps/catalog/models.py src/tests/test_admin.py
git commit -m "Админка по-русски: страница удаления, инлайны, горячие клавиши, тема; понятная строка связи группы и категории"
```

---

### Task 10: Команда `normalize_content` — бренд, ₽, единицы, кавычки, опечатки

**Files:**
- Create: `src/apps/core/content_fixes.py`
- Create: `src/apps/core/management/commands/normalize_content.py`
- Test: `src/tests/test_content_fixes.py` (новый)
- Modify: `CLAUDE.md`, `README.md` (шаг переезда: после финального импорта)

**Interfaces:**
- Consumes: модели `Service`, `Category`, `CategoryGroup`, `Event`, `InfoPage`, `Review`, `GalleryPhoto`, `SiteSettings`.
- Produces:
  - функции `fix_text`, `fix_name`, `fix_price`, `fix_unit`, `fix_caption`, `has_unbalanced_quotes`, `describe_change`;
  - команда `normalize_content [--apply]`.

- [ ] **Step 1: Падающие тесты** — `src/tests/test_content_fixes.py`:

```python
import pytest
from django.core.management import call_command

from apps.catalog.models import Service
from apps.content.models import GalleryPhoto
from apps.core.content_fixes import (
    describe_change,
    fix_caption,
    fix_name,
    fix_price,
    fix_text,
    fix_unit,
    has_unbalanced_quotes,
)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Правила безопасности Т-парка", "Правила безопасности Т-Парка"),
        ("<p>в Т-парке</p>", "<p>в Т-Парке</p>"),
        ("Нижняя веревочная трасса", "Нижняя верёвочная трасса"),
        ("Взнос 100 руб", "Взнос 100 ₽"),
        ("Стоимость 1000 р.", "Стоимость 1000 ₽"),
        ("Стоимость 1000 р", "Стоимость 1000 ₽"),
        ("5 рублей", "5 ₽"),
        ("10 раз, 1826 г.", "10 раз, 1826 г."),
        ("Генератор (1000 w)", "Генератор (1000 Вт)"),
        ("рекрасное место для отдыха", "Прекрасное место для отдыха"),
        ("друзья собирабтся", "друзья собираются"),
    ],
)
def test_fix_text(before, after):
    assert fix_text(before) == after


def test_fix_text_keeps_latin_formats():
    text = "философия тренинг-парка (T-park), лагеря (T-camp) — https://civilization.t-park.camp"
    assert fix_text(text) == text


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Сплав** На метеоритную ферму", "Сплав На метеоритную ферму"),
        ('Программа "Всё включено!"', "Программа «Всё включено!»"),
        (
            'Сплав на каноэ "На родину маршала Жукова, однодневный (летняя программа)',
            "Сплав на каноэ «На родину маршала Жукова», однодневный (летняя программа)",
        ),
        ("Встреча Клуба Т-парк", "Встреча Клуба Т-Парк"),
    ],
)
def test_fix_name(before, after):
    assert fix_name(before) == after


def test_fix_price_unit_and_caption():
    assert fix_price(" 15 000 ") == "15000"
    assert fix_price("договорная") == "договорная"
    assert fix_unit("человек") == "участник"
    assert fix_unit("чел.") == "участник"
    assert fix_unit("в день") == "день"
    assert fix_unit("30 минут") == "30 мин"
    assert fix_unit("1 прыжок") == "1 прыжок"
    assert fix_caption("123") == ""
    assert fix_caption("Зимой на тюбинге") == "Зимой на тюбинге"


def test_unbalanced_quotes_and_change_description():
    assert has_unbalanced_quotes('Сплав "На родину')
    assert not has_unbalanced_quotes("Сплав «На родину»")
    assert "Т-Парк" in describe_change("в Т-парке летом", "в Т-Парке летом")


@pytest.mark.django_db
def test_command_dry_run_changes_nothing(capsys):
    service = Service.objects.create(name="Сплав*", price="15 000", price_unit="человек")
    call_command("normalize_content")
    service.refresh_from_db()
    assert (service.name, service.price, service.price_unit) == ("Сплав*", "15 000", "человек")
    assert "без --apply" in capsys.readouterr().out


@pytest.mark.django_db
def test_command_applies_and_is_idempotent(capsys, make_image):
    service = Service.objects.create(name="Сплав*", price="15 000", price_unit="человек")
    photo = GalleryPhoto.objects.create(image=make_image(), caption="123")
    call_command("normalize_content", "--apply")
    service.refresh_from_db()
    photo.refresh_from_db()
    assert (service.name, service.price, service.price_unit) == ("Сплав", "15000", "участник")
    assert photo.caption == ""
    capsys.readouterr()
    call_command("normalize_content")
    assert ": 0 записей" in capsys.readouterr().out
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_content_fixes.py -v`
Expected: ImportError.

- [ ] **Step 3: Правила** — `src/apps/core/content_fixes.py`:

```python
"""Приведение старого контента к единому виду: бренд «Т-Парк», «₽», единицы цен, кавычки, известные опечатки.

Чистые функции над строкой; команда `normalize_content` применяет их к полям моделей. Латинские T-park, T-camp,
T-club, T-raid — названия форматов в «О нас», их не трогаем. Кавычки меняем только в названиях (в HTML они в атрибутах).
"""

import re
from difflib import SequenceMatcher

TYPOS = {
    "рекрасное место": "Прекрасное место",
    "собирабтся": "собираются",
    "обязателный": "обязательный",
    "Продолжитальность": "Продолжительность",
    "движнием": "движением",
}
NAME_FIXES = {
    'Сплав на каноэ "На родину маршала Жукова, однодневный (летняя программа)': (
        "Сплав на каноэ «На родину маршала Жукова», однодневный (летняя программа)"
    ),
}
UNIT_FIXES = {"человек": "участник", "чел": "участник", "чел.": "участник", "в день": "день"}

_BRAND = re.compile(r"Т-парк")  # кириллические Т и п
_YO = re.compile(r"([Вв])еревочн")
_RUB = re.compile(r"(\d)\s*(?:руб(?:лей|ля|ль)?\.?|р\.?)(?![а-яёА-ЯЁ])")
_WATTS = re.compile(r"(\d)\s*w\b")
_MINUTES = re.compile(r"(\d+)\s*минут[аы]?(?![а-яё])")
_STRAIGHT_QUOTES = re.compile(r'"([^"]*)"')
_DIGIT_SPACES = re.compile(r"(?<=\d)[\s ]+(?=\d)")


def fix_text(value: str) -> str:
    """Любой текст, в том числе HTML: опечатки, бренд, «ё» в «верёвочный», «Вт», «₽»."""
    for wrong, right in TYPOS.items():
        value = value.replace(wrong, right)
    value = _BRAND.sub("Т-Парк", value)
    value = _YO.sub(r"\1ерёвочн", value)
    value = _WATTS.sub(r"\1 Вт", value)
    return _RUB.sub(r"\1 ₽", value)


def fix_name(value: str) -> str:
    """Название (без HTML): то же + без звёздочек старой системы, «ёлочки» вместо прямых кавычек."""
    value = fix_text(NAME_FIXES.get(value, value)).replace("*", "")
    value = _STRAIGHT_QUOTES.sub(r"«\1»", value)
    return re.sub(r"\s{2,}", " ", value).strip()


def fix_price(value: str) -> str:
    return _DIGIT_SPACES.sub("", value.strip())


def fix_unit(value: str) -> str:
    value = value.strip()
    value = UNIT_FIXES.get(value.lower(), value)
    return _MINUTES.sub(r"\1 мин", value)


def fix_caption(value: str) -> str:
    return "" if value.strip().isdigit() else value


def has_unbalanced_quotes(value: str) -> bool:
    return value.count('"') % 2 == 1 or value.count("«") != value.count("»")


def describe_change(old: str, new: str, context: int = 25) -> str:
    """Изменённые места с контекстом: «…было… → …стало…» (для длинного HTML)."""
    parts = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag != "equal":
            parts.append(f"…{old[max(0, i1 - context) : i2 + context]}… → …{new[max(0, j1 - context) : j2 + context]}…")
    return "; ".join(parts[:5])
```

- [ ] **Step 4: Команда** — `src/apps/core/management/commands/normalize_content.py`:

```python
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, CategoryGroup, Service
from apps.content.models import Event, GalleryPhoto, Review
from apps.core.content_fixes import (
    describe_change,
    fix_caption,
    fix_name,
    fix_price,
    fix_text,
    fix_unit,
    has_unbalanced_quotes,
)
from apps.core.models import InfoPage, SiteSettings

SITE_TEXT_FIELDS = ("home_intro", "events_intro", "about_text", "nearby_text", "contacts_text", "founder_text")

FIELDS = {
    Service: {
        "name": fix_name,
        "short_description": fix_text,
        "description": fix_text,
        "price": fix_price,
        "price_unit": fix_unit,
    },
    Category: {"name": fix_name, "description": fix_text},
    CategoryGroup: {"name": fix_name},
    Event: {"title": fix_name, "description": fix_text, "price": fix_text},
    InfoPage: {"title": fix_name, "body": fix_text},
    Review: {"text": fix_text},
    GalleryPhoto: {"caption": fix_caption},
    SiteSettings: dict.fromkeys(SITE_TEXT_FIELDS, fix_text),
}


class Command(BaseCommand):
    help = (
        "Приводит контент к единому виду: «Т-Парк», «₽», единицы цен, кавычки, известные опечатки. "
        "Без --apply только показывает правки. Запускать после финального импорта старой базы."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Сохранить правки в базу")

    def handle(self, *args, apply, **options):
        changed = 0
        with transaction.atomic():
            for model, fields in FIELDS.items():
                label = model._meta.verbose_name
                has_updated_at = any(f.name == "updated_at" for f in model._meta.fields)
                for obj in model.objects.order_by("pk"):
                    updates = {}
                    for field, fix in fields.items():
                        old = getattr(obj, field) or ""
                        new = fix(old)
                        if new != old:
                            updates[field] = new
                            self.stdout.write(f"{label} #{obj.pk} {field}: {describe_change(old, new)}")
                        if fix is fix_name and has_unbalanced_quotes(new):
                            self.stdout.write(
                                self.style.WARNING(f"{label} #{obj.pk} {field}: непарные кавычки, поправьте вручную: {new}")
                            )
                    if not updates:
                        continue
                    changed += 1
                    if apply:
                        if has_updated_at:
                            updates["updated_at"] = timezone.now()  # lastmod в sitemap
                        model.objects.filter(pk=obj.pk).update(**updates)
        verdict = "Сохранено" if apply else "Найдено правок (без --apply ничего не сохранено)"
        self.stdout.write(self.style.SUCCESS(f"{verdict}: {changed} записей"))
```

`.update()` выбран сознательно: он не трогает slug, не запускает пересоздание миниатюр и удаление файлов в `save()`.

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest tests/test_content_fixes.py -v && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: Прогон на реальной копии (без записи)**

```bash
cd src
cp ../current_content/db.sqlite3 /tmp/normalize-check.sqlite3
DATABASE_PATH=/tmp/normalize-check.sqlite3 uv run manage.py migrate -v0
DATABASE_PATH=/tmp/normalize-check.sqlite3 uv run manage.py normalize_content | tee /tmp/normalize-report.txt | tail -5
```

Просмотреть отчёт. Подозрительные правки — например, «р» после числа, означающее не рубли, — показать владельцу до `--apply` на продакшене. Удалить временные файлы.

- [ ] **Step 7: Документация**

В README, в разделе переезда, после шага импорта:

```markdown
5. Привести контент к единому виду: `docker compose exec tpark-web python manage.py normalize_content` (покажет правки), затем то же с `--apply`.
```

В CLAUDE.md, раздел `apps/core`, рядом с `legacy/`:

```markdown
  - `content_fixes.py` + команда `normalize_content [--apply]` — бренд «Т-Парк», «₽», единицы цен, кавычки в названиях, известные опечатки; без `--apply` только отчёт; запускать после финального импорта;
```

- [ ] **Step 8: Коммит**

```bash
git add src/apps/core/content_fixes.py src/apps/core/management/commands/normalize_content.py src/tests/test_content_fixes.py README.md CLAUDE.md
git commit -m "Команда normalize_content: «Т-Парк», «₽», единицы цен, кавычки и опечатки (по умолчанию — только отчёт)"
```

---

## После плана

```bash
cd src && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
make e2e   # из корня: вёрстка не сломалась (цены с ₽ в карточках)
```

Проверить в браузере (`make run`):
- категорию «Верёвочный парк» — цены с «₽»;
- `/admin/` — инструкцию на главной;
- список услуг — фильтр «Видна на сайте»;
- удаление категории — предупреждение на русском;
- форму категории — «Группы меню».
