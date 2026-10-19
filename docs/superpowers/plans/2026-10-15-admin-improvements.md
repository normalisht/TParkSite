# Доработки админки по аудиту 2026-10-15 — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** администратор находит записи поиском в любом регистре и с «ё»/«е», новые записи встают в конец, черновик можно посмотреть на сайте до публикации, фото галереи поднимаются наверх одним действием, формы и списки понятнее, удалённое восстанавливается из корзины, услугу и мероприятие можно дублировать.

**Architecture:** почти всё — в общем слое админки `apps/core/admin_utils.py` (`SiteModelAdmin` и миксины) плюс небольшие модули в `apps/core/`: `search.py` (SQL-функция `tp_fold` для SQLite), `trash.py` (очистка корзины), `preview.py` (черновик для сотрудника). Корзина — абстрактная модель `TrashableModel` (`deleted_at`): перенос в корзину снимает запись с публикации, поэтому сайт прячет её без новых проверок, а админка скрывает её из списков. Шаблоны Unfold, которые приходится менять, копируются в `src/templates/` (как уже сделано с `userlinks.html`).

**Tech Stack:** Django 6.1, django-unfold 0.108, SQLite, pytest + pytest-django, Playwright (e2e).

**Spec:** отдельного документа нет. Источник — аудит админки 2026-10-15 (пункты 4–7 высокого приоритета и средний приоритет админки, в разговоре) и решения владельца ниже.

## Решения

| Вопрос | Решение | Почему |
|---|---|---|
| Восстановление удалённого | Корзина: «Удалить» переносит запись в корзину (`deleted_at`, `is_published=False`), в корзине — «Восстановить» и «Удалить навсегда», через 30 дней удаляется сама | Фото и привязки к категориям остаются, восстановление полное; история версий (simple-history) не вернула бы фото — их файлы удаляются вместе с записью |
| Какие модели в корзине | Услуги, категории, группы категорий, мероприятия, инфо-страницы, плашки, отзывы — у всех есть `is_published` | Снятие с публикации прячет запись на сайте через уже существующие `published()`; у фото галереи и партнёров флага нет — они удаляются как раньше |
| Автоочистка корзины | `purge_expired` при открытии корзины и при каждом переносе в неё, без cron | Не нужен планировщик ни в Docker, ни в systemd-варианте |
| Восстановленная запись | Возвращается черновиком (`is_published=False`) | Администратор проверит и опубликует сам; случайное восстановление не попадёт на сайт |
| Роль «Редактор», `permission` в меню | **Не делаем** (решение владельца) | — |
| Поиск | SQL-функция `tp_fold` (`casefold` + «ё»→«е»), регистрируется при подключении к SQLite; `SiteModelAdmin.get_search_results` сравнивает через неё обе стороны | `LIKE` в SQLite не различает регистр только у латиницы; функция покрывает и списки, и автодополнение |
| Порядок новых записей | Формы верхнего уровня — поле «Порядок» скрыто, `save_model` ставит `next_order`; новые строки inline — начальное значение `next_order` родителя; связь услуги с категорией из формы услуги — `next_order` в выбранной категории | Перетаскивание Unfold нумерует строки с 0 только при перетаскивании, поэтому `order=0` у новой строки нельзя отличить от «поставили первой» — правим начальное значение, а не сохранённое |
| Галерея | Действие «Поставить в начало» + все фото на одной странице списка (`list_per_page = 400`) | Перетаскивание работает только в пределах страницы, а загрузка пачкой кладёт фото в конец |
| Предпросмотр | Неопубликованная (не в корзине) страница открывается сотруднику с правом просмотра модели — с плашкой «Черновик», `noindex` и `Cache-Control: no-cache`; посетителям — 404 | Сессия читается только для неопубликованного: ответы опубликованных страниц не меняются (ETag/304) |
| «Смотреть на сайте» у услуги без страницы | Ведёт на её первую категорию; без категории кнопки нет | Раньше вела на 404 |
| Вкладки формы услуги и категории | Вкладки верхнего уровня: «Основное» / «Фото» / «Категории» (или «Услуги»); SEO — свёрнутый блок под полями; «Загрузить фото пачкой» — над таблицей фото | Убирает вторую строку вкладок и два места для фото |
| Настройки сайта | «Телефоны» — своя вкладка; «Логотип» и «Юридическое» объединены; строка вкладок полей переносится на узком экране; объект называется «Основные» (крошки «Настройки сайта › Основные») | Телефоны были видны на каждой вкладке, часть вкладок на телефоне обрезалась |
| Корявые строки Django/Unfold | Перевод в `locale/ru/LC_MESSAGES/django.po` без подстановки названия раздела; «Удалить Услуга» и «13 Категории» — копии шаблонов Unfold | Подстановка `verbose_name` в именительном падеже по-русски не склоняется |
| Дублирование | Кнопка «Дублировать» в форме услуги и мероприятия; копия — черновик, файлы фото копируются, SEO-поля пустые | Общий файл у двух записей нельзя: удаление одной стёрло бы фото у другой |

## Global Constraints

- Весь пользовательский текст (админка, сайт, справка) — на русском.
- Админки наследуются от `apps.core.admin_utils.SiteModelAdmin`; inline — из `unfold.admin`.
- В публичных шаблонах нет значений, зависящих от запроса (ETag/304); сессию в публичных view читать только там, где без этого нельзя.
- В шаблонах админки — только Tailwind-классы, которые есть в CSS Unfold (нет, например, `list-decimal`, `space-y-1`).
- Комментарии `{# … #}` — только однострочные.
- Меняешь заметное администратору — обнови раздел справки (`templates/admin/help/sections/`), вводную `help_intro` и `help_text`.
- Копии шаблонов Unfold отмечать в `CLAUDE.md` («сверять при обновлении Unfold»).
- После правки `.po`: `uv run manage.py compilemessages -l ru` (нужен gettext), `.mo` коммитится.
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Поиск со спецсимволами и кавычками** — «50%», «_», `"верёвочный парк"` не роняют список и ищут буквально. Тест — задача 1.
2. **Отправленный порядок важнее начального** — если новую строку перетащили первой (`order=0` в POST), она остаётся первой. Тест — задача 2.
3. **Предпросмотр не меняет публичные ответы** — у опубликованной страницы ETag одинаковый для посетителя и сотрудника. Тест — задача 8.
4. **Инфо-страница из настроек в корзине** — ссылка на политику в баннере cookie и плашка безопасности на «О нас» пропадают, сайт не падает. Тест — задача 7.
5. **Дублирование при битом или отсутствующем файле фото** — копия создаётся без этого фото, без ошибки 500. Тест — задача 9.

## Структура файлов

| Файл | Что | Задача |
|---|---|---|
| `src/apps/core/search.py` (новый) | `fold`, SQL-функция `tp_fold`, `search()` | 1 |
| `src/apps/core/apps.py` | регистрация `tp_fold` на `connection_created` | 1 |
| `src/apps/core/models.py` | `next_order`, `TrashableModel`, `SiteSettings.__str__` | 2, 5, 7 |
| `src/apps/core/admin_utils.py` | `get_search_results`, `save_model`, `OrderedInlineMixin`, `move_to_top`, `thumbnail_html`, `SEO_SECTION`, `TrashAdminMixin` | 1–5, 7 |
| `src/apps/core/bulk_upload.py` | `append_images` через `next_order` | 2 |
| `src/apps/catalog/admin.py`, `src/apps/content/admin.py`, `src/apps/core/admin.py` | поля, колонки, фильтры, вкладки, корзина, дублирование | 2–9 |
| `src/apps/core/trash.py` (новый) | `TRASH_DAYS`, `purge_expired` | 7 |
| `src/apps/core/preview.py` (новый) | `get_for_view`, `preview_context` | 8 |
| `src/apps/core/files.py` | `clone_file` | 9 |
| `src/apps/catalog/models.py`, `src/apps/content/models.py` | `TrashableModel` в базах, `duplicate()` | 7, 9 |
| `src/templates/admin/catalog/bulk_photos_field.html` (новый) | поле пачки над таблицей фото | 5 |
| `src/templates/admin/submit_line.html`, `src/templates/unfold/helpers/pagination_default.html` (копии Unfold) | «Удалить»/«В корзину», «Всего: N» | 6, 7 |
| `src/templates/admin/trash/confirm.html`, `list.html` (новые), `src/static/js/admin_trash.js` (новый) | корзина | 7 |
| `src/templates/partials/preview_banner.html` (новый), `src/templates/base.html` | плашка «Черновик» | 8 |
| `src/static/css/admin.css` | перенос строки вкладок полей | 5 |
| `src/locale/ru/LC_MESSAGES/django.po` (+ `.mo`) | формулировки Django/Unfold | 6 |
| `src/templates/admin/help/sections/*.html`, `CLAUDE.md` | справка и документация | во всех |
| `src/tests/test_admin_search.py`, `test_admin_order.py`, `test_admin_lists.py`, `test_admin_forms.py`, `test_trash.py`, `test_preview.py`, `test_duplicate.py` (новые), `tests/e2e/test_admin_chrome.py` | тесты | по задаче |

---

### Task 1: Поиск без учёта регистра и «ё»/«е»

**Files:**
- Create: `src/apps/core/search.py`
- Modify: `src/apps/core/apps.py` (`CoreConfig.ready`)
- Modify: `src/apps/core/admin_utils.py` (`SiteModelAdmin`)
- Test: `src/tests/test_admin_search.py`

**Interfaces:**
- Produces: `apps.core.search.fold(value: str | None) -> str | None`; `apps.core.search.search(queryset, search_fields: Sequence[str], term: str) -> tuple[QuerySet, bool]`; `SiteModelAdmin.get_search_results` (переопределён).

- [ ] **Step 1: Написать падающие тесты**

`src/tests/test_admin_search.py`:

```python
import pytest
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.search import fold

pytestmark = pytest.mark.django_db


def test_fold():
    assert fold("ЁЛКА и Ёж") == "елка и еж"
    assert fold(None) is None


def _names(admin_client, url_name, q):
    response = admin_client.get(reverse(url_name), {"q": q})
    assert response.status_code == 200
    return [str(obj) for obj in response.context["cl"].result_list]


def test_service_search_ignores_case_and_yo(admin_client):
    Service.objects.create(name="Батут большой")
    Service.objects.create(name="Верёвочная трасса")
    Service.objects.create(name="Сапборд")
    assert _names(admin_client, "admin:catalog_service_changelist", "батут") == ["Батут большой"]
    assert _names(admin_client, "admin:catalog_service_changelist", "ВЕРЕВОЧН") == ["Верёвочная трасса"]


def test_search_requires_every_word(admin_client):
    Service.objects.create(name="Батут большой")
    assert _names(admin_client, "admin:catalog_service_changelist", "батут большой") == ["Батут большой"]
    assert _names(admin_client, "admin:catalog_service_changelist", "батут сап") == []


SALE = "Скидка 50% на верёвочный парк"


@pytest.mark.parametrize(("q", "expected"), [("50%", [SALE]), ("_", []), ('"Верёвочный Парк"', [SALE]), ("%", [SALE])])
def test_search_special_characters_are_literal(admin_client, q, expected):
    Service.objects.create(name=SALE)
    Service.objects.create(name="Сапборд")
    assert _names(admin_client, "admin:catalog_service_changelist", q) == expected


def test_autocomplete_ignores_case(admin_client):
    Category.objects.create(name="Верёвочный парк")
    response = admin_client.get(
        reverse("admin:autocomplete"),
        {"term": "веревоч", "app_label": "catalog", "model_name": "categoryservice", "field_name": "category"},
    )
    assert [item["text"] for item in response.json()["results"]] == ["Верёвочный парк"]
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `cd src && uv run pytest tests/test_admin_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.core.search'`.

- [ ] **Step 3: Модуль поиска**

`src/apps/core/search.py`:

```python
"""Поиск в админке без учёта регистра и разницы «ё»/«е».

В SQLite `LIKE` не различает регистр только у латиницы: «батут» не находил «Батут». Поэтому обе стороны сравнения
приводятся к одному виду функцией `fold` — в базе через SQL-функцию `tp_fold`, которую `register` добавляет
каждому новому подключению к SQLite (`CoreConfig.ready`)."""

from collections.abc import Sequence
from functools import reduce
from operator import or_

from django.db.models import CharField, F, Func, Q, QuerySet
from django.utils.text import smart_split, unescape_string_literal

SQL_FUNCTION = "tp_fold"


def fold(value):
    if value is None:
        return None
    return str(value).casefold().replace("ё", "е")


def register(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_function(SQL_FUNCTION, 1, fold, deterministic=True)


class Fold(Func):
    function = SQL_FUNCTION
    output_field = CharField()


def search(queryset: QuerySet, search_fields: Sequence[str], term: str) -> tuple[QuerySet, bool]:
    """Записи, где каждое слово `term` есть хотя бы в одном из `search_fields` (как в Django: фраза в кавычках —
    одно слово). Возвращает queryset и признак возможных дублей (поиск по связанным записям)."""
    names = {f"_fold_{i}": field.lstrip("^=@") for i, field in enumerate(search_fields)}
    queryset = queryset.annotate(**{alias: Fold(F(name)) for alias, name in names.items()})
    for bit in smart_split(term):
        if bit.startswith(('"', "'")) and bit[0] == bit[-1]:
            bit = unescape_string_literal(bit)
        word = fold(bit)
        queryset = queryset.filter(reduce(or_, (Q(**{f"{alias}__contains": word}) for alias in names)))
    return queryset, any("__" in name for name in names.values())
```

- [ ] **Step 4: Регистрация функции и `get_search_results`**

`src/apps/core/apps.py`, в `CoreConfig.ready` — после существующих импортов и `connect`:

```python
        from django.db.backends.signals import connection_created

        from apps.core import search

        connection_created.connect(search.register, dispatch_uid="tp-fold")
```

`src/apps/core/admin_utils.py` — импорт `from django.db import connections` и `from apps.core import search` вверху, метод в `SiteModelAdmin`:

```python
    def get_search_results(self, request, queryset, search_term):
        # Без учёта регистра и «ё»/«е» (apps/core/search.py); кроме SQLite — как в Django.
        search_fields = self.get_search_fields(request)
        if not (search_fields and search_term) or connections[queryset.db].vendor != "sqlite":
            return super().get_search_results(request, queryset, search_term)
        return search.search(queryset, search_fields, search_term)
```

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest tests/test_admin_search.py tests/test_admin.py -v`
Expected: PASS («%» и «_» Django экранирует в `__contains` сам — ищутся буквально).

- [ ] **Step 6: Справка и CLAUDE.md**

В `src/templates/admin/help/sections/basics.html`, где описан поиск в списках (найди `grep -n "оиск" src/templates/admin/help/sections/basics.html`; если поиска там нет — добавь абзац в конец раздела): «Поиск не различает заглавные и строчные буквы и «ё»/«е»: «веревочн» найдёт «Верёвочный парк». Несколько слов — найдутся записи, где есть все.»

В `CLAUDE.md`, в абзац про `SiteModelAdmin` добавь: «поиск — без учёта регистра и «ё»/«е» (`apps/core/search.py`: SQL-функция `tp_fold` на каждом подключении к SQLite; `LIKE` SQLite не различает регистр только у латиницы)».

- [ ] **Step 7: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Админка: поиск без учёта регистра и ё/е

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Новые записи — в конец; поле «Порядок» убрано из форм

**Files:**
- Modify: `src/apps/core/models.py` (`next_order`)
- Modify: `src/apps/core/bulk_upload.py` (`append_images`)
- Modify: `src/apps/core/admin_utils.py` (`SiteModelAdmin.save_model`, `OrderedInlineMixin`)
- Modify: `src/apps/catalog/admin.py`, `src/apps/content/admin.py`, `src/apps/core/admin.py`
- Test: `src/tests/test_admin_order.py`

**Interfaces:**
- Produces: `apps.core.models.next_order(model, **scope) -> int`; `apps.core.admin_utils.OrderedInlineMixin` (миксин inline, ставится перед `TabularInline`).

- [ ] **Step 1: Падающие тесты**

`src/tests/test_admin_order.py`:

```python
import pytest
from django.contrib import admin
from django.urls import reverse

from apps.catalog.admin import CategoryPhotoInline, CategoryServiceInline, ServiceCategoryInline
from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service
from apps.content.models import Partner
from apps.core.models import next_order

pytestmark = pytest.mark.django_db


def test_next_order():
    assert next_order(CategoryGroup) == 1
    CategoryGroup.objects.create(name="А", order=7)
    assert next_order(CategoryGroup) == 8


def test_service_added_from_its_form_goes_last_in_category(rf, admin_user):
    category = Category.objects.create(name="К")
    for i, name in enumerate(["А", "Б"], start=1):
        CategoryService.objects.create(category=category, service=Service.objects.create(name=name), order=i)
    service = Service.objects.create(name="Новая")
    request = rf.get("/")
    request.user = admin_user
    FormSet = ServiceCategoryInline(Service, admin.site).get_formset(request, service)
    data = {
        "category_links-TOTAL_FORMS": "1",
        "category_links-INITIAL_FORMS": "0",
        "category_links-0-category": str(category.pk),
    }
    formset = FormSet(data, instance=service, prefix="category_links")
    assert formset.is_valid(), formset.errors
    formset.save()
    assert CategoryService.objects.get(service=service).order == 3


def test_new_inline_rows_start_after_last(rf, admin_user, make_image):
    category = Category.objects.create(name="К")
    CategoryPhoto.objects.create(category=category, image=make_image(), order=5)
    CategoryService.objects.create(category=category, service=Service.objects.create(name="А"), order=2)
    request = rf.get("/")
    request.user = admin_user
    photos = CategoryPhotoInline(Category, admin.site).get_formset(request, category)
    links = CategoryServiceInline(Category, admin.site).get_formset(request, category)
    assert photos.form.base_fields["order"].initial == 6
    assert links.form.base_fields["order"].initial == 3


def test_posted_order_wins(rf, admin_user):
    """Новую строку перетащили первой — order=0 из формы сохраняется."""
    category = Category.objects.create(name="К")
    CategoryService.objects.create(category=category, service=Service.objects.create(name="А"), order=1)
    new = Service.objects.create(name="Б")
    request = rf.get("/")
    request.user = admin_user
    FormSet = CategoryServiceInline(Category, admin.site).get_formset(request, category)
    link = CategoryService.objects.get()
    data = {
        "service_links-TOTAL_FORMS": "2",
        "service_links-INITIAL_FORMS": "1",
        "service_links-0-id": str(link.pk),
        "service_links-0-category": str(category.pk),
        "service_links-0-service": str(link.service_id),
        "service_links-0-order": "1",
        "service_links-1-category": str(category.pk),
        "service_links-1-service": str(new.pk),
        "service_links-1-order": "0",
    }
    formset = FormSet(data, instance=category, prefix="service_links")
    assert formset.is_valid(), formset.errors
    formset.save()
    assert CategoryService.objects.get(service=new).order == 0


def test_partner_added_in_admin_goes_last(admin_client, make_image):
    Partner.objects.create(name="Старый", logo=make_image(), order=4)
    response = admin_client.post(
        reverse("admin:content_partner_add"), {"name": "Новый", "link": "", "logo": make_image("new.jpg")}
    )
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert Partner.objects.get(name="Новый").order == 5


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:catalog_categorygroup_add",
        "admin:catalog_category_add",
        "admin:content_partner_add",
        "admin:content_galleryphoto_add",
        "admin:core_announcement_add",
        "admin:core_infopage_add",
    ],
)
def test_order_field_hidden_in_forms(admin_client, url_name):
    form = admin_client.get(reverse(url_name)).context["adminform"].form
    assert "order" not in form.fields
```

Prefix `service_links`/`category_links` — `related_name` у `CategoryService` (`category.service_links`, `service.category_links`). Если `Partner` требует других полей — посмотри `Partner` в `src/apps/content/models.py` и добавь их в POST.

- [ ] **Step 2: Запустить — должны упасть**

Run: `cd src && uv run pytest tests/test_admin_order.py -v`
Expected: FAIL — `ImportError: cannot import name 'next_order'`.

- [ ] **Step 3: `next_order` и `append_images`**

`src/apps/core/models.py` — импорт `from django.db.models import Max` и функция после `OrderedModel`:

```python
def next_order(model, **scope) -> int:
    """Порядок для новой записи — после последней (в пределах `scope`, например `category=…`)."""
    return (model._default_manager.filter(**scope).aggregate(m=Max("order"))["m"] or 0) + 1
```

`src/apps/core/bulk_upload.py`, `append_images`:

```python
def append_images(model, files, **parent) -> list:
    """Создаёт записи `model(image=file, order=…, **parent)` после текущего максимума order."""
    start = next_order(model, **parent)
    return [model.objects.create(image=file, order=start + i, **parent) for i, file in enumerate(files)]
```

(импорт `from apps.core.models import next_order`; убрать ставший ненужным импорт `Max`, если он больше не используется.)

- [ ] **Step 4: Миксин inline и `save_model`**

`src/apps/core/admin_utils.py`:

```python
from apps.core.models import next_order


class OrderedInlineMixin:
    """Новая строка inline встаёт в конец: начальное значение порядка — после последней записи родителя.
    Без этого у новой строки order=0, и после сохранения она оказывается первой: перетаскивание Unfold
    переписывает порядок строк, только если их двигали."""

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        scope = {formset.fk.name: obj} if obj is not None and obj.pk else None
        formset.form.base_fields["order"].initial = next_order(self.model, **scope) if scope else 1
        return formset
```

В `SiteModelAdmin`:

```python
    def save_model(self, request, obj, form, change):
        # Поля «Порядок» в формах нет — порядок задают перетаскиванием в списке, новая запись встаёт в конец.
        if not change and "order" not in form.fields and any(f.name == "order" for f in obj._meta.fields):
            obj.order = next_order(type(obj))
        super().save_model(request, obj, form, change)
```

(Если импорт `apps.core.models` из `admin_utils` даёт циклический импорт — импортируй `next_order` внутри методов.)

- [ ] **Step 5: Применить в админках**

`src/apps/catalog/admin.py`:

```python
from unfold.admin import TabularInline
from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import SEO_FIELDSET, OrderedInlineMixin, SiteModelAdmin, image_preview
from apps.core.models import next_order
from unfold.forms import PaginationInlineFormSet  # базовый formset inline у Unfold (unfold/forms.py)


class CategoryPhotoInline(OrderedInlineMixin, TabularInline):
    ...  # остальное без изменений


class CategoryServiceInline(OrderedInlineMixin, TabularInline):
    ...  # остальное без изменений


class AppendToCategoryFormSet(PaginationInlineFormSet):
    """Услуга, добавленная в категорию из формы услуги, встаёт в конец категории (а не в начало с order=0)."""

    def save_new(self, form, commit=True):
        form.instance.order = next_order(CategoryService, category=form.instance.category)
        return super().save_new(form, commit)


class ServiceCategoryInline(TabularInline):
    model = CategoryService
    formset = AppendToCategoryFormSet
    ...  # остальное без изменений
```

`ServicePhotoInline` наследует `CategoryPhotoInline` — миксин достаётся ему сам.

Убрать `"order"` из полей форм:
- `CategoryGroupAdmin.fields` → `["name", "categories", "is_published"]`;
- `CategoryAdmin.fieldsets`, «Основное» → без `"order"`;
- `src/apps/content/admin.py`: `PartnerAdmin.fields` → `["name", "link", "logo"]`, `GalleryPhotoAdmin.fields` → `["image", "caption"]`;
- `src/apps/core/admin.py`: `AnnouncementAdmin.fields` → `["text", "link", "is_published", ("starts_on", "ends_on")]`, `InfoPageAdmin.fieldsets`, «Основное» → без `"order"`.

`PhoneInline`, `ParkFormatInline`, `FounderFactInline` (`src/apps/core/admin.py`) — добавить `OrderedInlineMixin` первым базовым классом (у `Phone`, `ParkFormat`, `FounderFact` есть поле `order` и FK на настройки — миксин работает и для них).

- [ ] **Step 6: Тесты проходят, старые тесты поправить**

Run: `cd src && uv run pytest -q`
Expected: новые тесты PASS. Если старые тесты отправляли `order` в формы, где его больше нет, — убрать это поле из их POST (поле формы теперь игнорируется, порядок ставит `save_model`).

- [ ] **Step 7: Справка**

В `src/templates/admin/help/sections/basics.html` (или там, где описан порядок перетаскиванием — `grep -rn "перетаск" src/templates/admin/help/sections/`) добавить: «Новая запись встаёт в конец списка. Поменять место — перетащить её в списке.» Найти и убрать упоминания поля «Порядок» в формах: `grep -rn "«Порядок»\|поле порядка" src/templates/admin/help src/apps`.

- [ ] **Step 8: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Админка: новые записи встают в конец, поле «Порядок» убрано из форм

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Галерея — «Поставить в начало» и все фото на одной странице

**Files:**
- Modify: `src/apps/core/admin_utils.py` (`move_to_top`, `thumbnail_html`, `image_preview`)
- Modify: `src/apps/content/admin.py` (`GalleryPhotoAdmin`)
- Test: `src/tests/test_admin_order.py`

**Interfaces:**
- Produces: `apps.core.admin_utils.move_to_top(model, selected: QuerySet) -> int`; `apps.core.admin_utils.thumbnail_html(obj, spec_name: str, size: int = 64) -> str` (задача 4 использует его для колонок).

- [ ] **Step 1: Падающие тесты** — дописать в `src/tests/test_admin_order.py`:

```python
from apps.content.models import GalleryPhoto


def test_move_gallery_photos_to_top(admin_client, make_image):
    photos = [GalleryPhoto.objects.create(image=make_image(f"{i}.jpg"), order=i) for i in range(1, 6)]
    response = admin_client.post(
        reverse("admin:content_galleryphoto_changelist"),
        {"action": "move_to_top", "_selected_action": [photos[4].pk, photos[2].pk]},
    )
    assert response.status_code == 302
    order = list(GalleryPhoto.objects.order_by("order", "id").values_list("pk", flat=True))
    assert order == [photos[2].pk, photos[4].pk, photos[0].pk, photos[1].pk, photos[3].pk]


def test_gallery_list_fits_one_page():
    from apps.content.admin import GalleryPhotoAdmin

    assert GalleryPhotoAdmin.list_per_page >= 400
```

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_admin_order.py -k "gallery" -v`
Expected: FAIL (действия `move_to_top` нет; `list_per_page` = 100).

- [ ] **Step 3: Хелперы в `admin_utils.py`**

```python
def move_to_top(model, selected) -> int:
    """Ставит выбранные записи в начало списка (между собой — в прежнем порядке), остальные — следом."""
    picked = list(selected.order_by("order", "id").only("pk", "order"))
    picked_ids = {obj.pk for obj in picked}
    rest = [obj for obj in model._default_manager.order_by("order", "id").only("pk", "order") if obj.pk not in picked_ids]
    rows = [*picked, *rest]
    for position, obj in enumerate(rows, start=1):
        obj.order = position
    model._default_manager.bulk_update(rows, ["order"])
    return len(picked)


def thumbnail_html(obj, spec_name: str, size: int = 64) -> str:
    url = safe_spec_url(obj, spec_name)
    if not url:
        return "—"
    return format_html(
        '<img src="{}" alt="" loading="lazy" style="height:{}px;width:auto;border-radius:6px;object-fit:cover">',
        url,
        size,
    )


def image_preview(spec_name: str, size: int = 64):
    @admin.display(description="Фото")
    def preview(_model_admin, obj):
        return thumbnail_html(obj, spec_name, size)

    return preview
```

(`thumbnail_html` заменяет тело прежнего `image_preview`; `loading="lazy"` — на одной странице теперь до 400 превью.)

- [ ] **Step 4: `GalleryPhotoAdmin`**

```python
from apps.core.admin_utils import SEO_FIELDSET, SiteModelAdmin, image_preview, move_to_top


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(OrderedPhotoAdmin):
    help_intro = (
        "Фото для страницы «Галерея» и полосы «Как это выглядит» на главной, «О нас» и «Отзывах». "
        "Порядок — перетаскиванием; новые фото встают в конец — отметьте их и выберите «Поставить в начало»."
    )
    ...
    list_per_page = 400  # все фото на одной странице: перетаскивание работает только в пределах страницы
    actions = ["move_to_top"]

    @admin.action(description="Поставить в начало", permissions=["change"])
    def move_to_top(self, request, queryset):
        moved = move_to_top(GalleryPhoto, queryset)
        messages.success(request, f"Поставлено в начало: {moved}.")
```

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest tests/test_admin_order.py tests/test_admin_help.py -v`
Expected: PASS.

- [ ] **Step 6: Справка** — в `src/templates/admin/help/sections/gallery.html`, после описания загрузки пачкой: «Загруженные фото встают в конец. Чтобы показать их первыми — отметьте галочками в списке, выберите действие «Поставить в начало» и нажмите «Выполнить». Все фото галереи — на одной странице списка, их можно перетаскивать.»

- [ ] **Step 7: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Галерея в админке: «Поставить в начало», все фото на одной странице

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Списки — превью, «Чего не хватает», статус мероприятий, поиск отзывов

**Files:**
- Modify: `src/apps/catalog/admin.py` (`ServiceAdmin`, `CategoryAdmin`)
- Modify: `src/apps/content/admin.py` (`EventAdmin`, `ReviewAdmin`)
- Test: `src/tests/test_admin_lists.py`

**Interfaces:**
- Consumes: `thumbnail_html` (задача 3).
- Produces: `apps.catalog.admin.ServiceGapsFilter` (`parameter_name = "gaps"`, значения `photo`, `price`, `short`); `EventAdmin.status`.

- [ ] **Step 1: Падающие тесты**

`src/tests/test_admin_lists.py`:

```python
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Service, ServicePhoto
from apps.content.models import Event, Review

pytestmark = pytest.mark.django_db


def _names(admin_client, url_name, **params):
    response = admin_client.get(reverse(url_name), params)
    assert response.status_code == 200
    return {str(obj) for obj in response.context["cl"].result_list}


def test_service_gaps_filter(admin_client, make_image):
    with_photo = Service.objects.create(name="С фото", price="100", short_description="<p>Есть</p>")
    ServicePhoto.objects.create(service=with_photo, image=make_image())
    Service.objects.create(name="Без всего")
    url = "admin:catalog_service_changelist"
    assert _names(admin_client, url, gaps="photo") == {"Без всего"}
    assert _names(admin_client, url, gaps="price") == {"Без всего"}
    assert _names(admin_client, url, gaps="short") == {"Без всего"}


def test_service_list_queries_do_not_grow(admin_client, make_image):
    def count():
        with CaptureQueriesContext(connection) as ctx:
            admin_client.get(reverse("admin:catalog_service_changelist"))
        return len(ctx)

    Service.objects.create(name="А")
    before = count()
    for i in range(5):
        ServicePhoto.objects.create(service=Service.objects.create(name=f"Б{i}"), image=make_image(f"{i}.jpg"))
    assert count() == before


def test_event_status_column(admin_client):
    today = date.today()
    Event.objects.create(title="Скоро", date=today + timedelta(days=5))
    Event.objects.create(title="Было", date=today - timedelta(days=5))
    Event.objects.create(title="Черновик", date=today + timedelta(days=5), is_published=False)
    page = admin_client.get(reverse("admin:content_event_changelist")).content.decode()
    for text in ("Предстоящее", "Прошедшее, скрыто", "Черновик"):
        assert text in page
    from apps.content.admin import EventAdmin

    assert EventAdmin.date_hierarchy is None


def test_review_search_and_toggle(admin_client):
    Review.objects.create(text="<p>Отличный сплав</p>", date=date.today())
    Review.objects.create(text="<p>Верёвочный парк</p>", date=date.today())
    response = admin_client.get(reverse("admin:content_review_changelist"), {"q": "сплав"})
    assert len(response.context["cl"].result_list) == 1
    from apps.content.admin import ReviewAdmin

    assert "is_published" in ReviewAdmin.list_editable
```

Если в тестовой среде `today` для мероприятий подменён (проверь `tests/conftest.py` и `Event.is_past`), бери дату оттуда же. Обязательные поля `Event`/`Review` — сверь с моделями.

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_admin_lists.py -v`
Expected: FAIL.

- [ ] **Step 3: Услуги и категории** — `src/apps/catalog/admin.py`:

```python
from apps.core.admin_utils import thumbnail_html


class ServiceGapsFilter(admin.SimpleListFilter):
    title = "Чего не хватает"
    parameter_name = "gaps"

    def lookups(self, request, model_admin):
        return [("photo", "Нет фото"), ("price", "Нет цены"), ("short", "Нет краткого описания")]

    def queryset(self, request, queryset):
        if self.value() == "photo":
            return queryset.filter(photos__isnull=True)
        if self.value() == "price":
            return queryset.filter(price="")
        if self.value() == "short":
            return queryset.filter(short_description="")
        return queryset
```

В `ServiceAdmin`:

```python
    list_display = ["photo", "name", "price_display", "categories", "is_published", "has_page"]
    list_display_links = ["photo", "name"]
    list_filter = [ServicePlacementFilter, ServiceGapsFilter, "is_published", "has_page", "category_links__category"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("category_links__category", "photos")

    @admin.display(description="Фото")
    def photo(self, obj):
        photos = obj.photos.all()  # prefetch_related в get_queryset
        return thumbnail_html(photos[0], "thumb") if photos else "—"
```

В `CategoryAdmin`: `list_display = ["photo", "name", "menu_groups_display", "services_count", "is_published"]`, `list_display_links = ["photo", "name"]`, в `get_queryset` — `.prefetch_related("groups", "photos")`, и:

```python
    @admin.display(description="Фото")
    def photo(self, obj):
        if obj.preview:
            return thumbnail_html(obj, "preview_card")
        photos = obj.photos.all()
        return thumbnail_html(photos[0], "thumb") if photos else "—"
```

(Поле модели называется `preview`, поэтому метод — `photo`. Спеки `thumb` у `CategoryPhoto`/`ServicePhoto` и `preview_card` у `Category` уже есть.)

- [ ] **Step 4: Мероприятия и отзывы** — `src/apps/content/admin.py`:

```python
from apps.core.admin_utils import thumbnail_html


class EventAdmin(SiteModelAdmin):
    ...
    list_display = ["photo", "title", "date", "status", "is_published", "show_after_date"]
    list_display_links = ["photo", "title"]
    # date_hierarchy убран: годы 2022/2023/2027 сверху списка не помогали найти мероприятие

    @admin.display(description="Фото")
    def photo(self, obj):
        return thumbnail_html(obj, "card_small")

    @admin.display(description="Статус")
    def status(self, obj):
        if not obj.is_published:
            return "Черновик"
        if not obj.is_past:
            return "Предстоящее"
        return "Прошедшее, в архиве" if obj.show_after_date else "Прошедшее, скрыто"
```

`ReviewAdmin`: `search_fields = ["text"]`, `list_editable = ["is_published"]`.

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest tests/test_admin_lists.py tests/test_admin.py tests/test_query_counts.py -v`
Expected: PASS.

- [ ] **Step 6: Справка** — в `src/templates/admin/help/sections/catalog.html`: «Фильтр «Чего не хватает» справа от списка услуг находит услуги без фото, цены или краткого описания.» В `events.html`: «Колонка «Статус»: черновик, предстоящее, прошедшее (в архиве — если отмечено «Показывать после даты», иначе скрыто).» В `reviews.html`: «Поиск — по тексту отзыва; галочку «Опубликовано» можно снять прямо в списке и нажать «Сохранить».»

- [ ] **Step 7: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Списки админки: превью, фильтр «Чего не хватает», статус мероприятий, поиск отзывов

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Вкладки форм — услуга и категория в одну строку, телефоны и вкладки настроек

**Files:**
- Modify: `src/apps/core/admin_utils.py` (`SEO_SECTION`)
- Modify: `src/apps/catalog/admin.py` (`CategoryAdmin`, `ServiceAdmin`, `CategoryPhotoInline`)
- Create: `src/templates/admin/catalog/bulk_photos_field.html`
- Modify: `src/apps/core/admin.py` (`SiteSettingsAdmin`, `PhoneInline`)
- Modify: `src/apps/core/models.py` (`SiteSettings.__str__`)
- Modify: `src/static/css/admin.css`
- Test: `src/tests/test_admin_forms.py`, `src/tests/e2e/test_admin_chrome.py`

**Interfaces:**
- Produces: `apps.core.admin_utils.SEO_SECTION` (свёрнутый блок SEO для форм с вкладками-inline).

- [ ] **Step 1: Падающие тесты**

`src/tests/test_admin_forms.py`:

```python
import pytest
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("url_name", "model"), [("admin:catalog_service_change", Service), ("admin:catalog_category_change", Category)]
)
def test_one_row_of_tabs_and_bulk_upload_in_photos_tab(admin_client, url_name, model):
    obj = model.objects.create(name="Тест")
    page = admin_client.get(reverse(url_name, args=[obj.pk])).content.decode()
    assert "activeFieldsetTab" not in page  # нет второй строки вкладок
    photos_group = page.index('id="photos-group"')
    assert page.index('name="bulk_photos"') > photos_group  # поле пачки — во вкладке фото


def test_bulk_upload_still_saves(admin_client, make_image):
    service = Service.objects.create(name="Тест")
    url = reverse("admin:catalog_service_change", args=[service.pk])
    form = admin_client.get(url).context["adminform"].form
    data = {name: form[name].value() or "" for name in form.fields if name != "bulk_photos"}
    for prefix in ("photos", "category_links"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"})
    data["bulk_photos"] = [make_image("a.jpg"), make_image("b.jpg")]
    response = admin_client.post(url, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert service.photos.count() == 2


def test_phones_have_own_tab(admin_client):
    SiteSettings.load()
    page = admin_client.get(reverse("admin:core_sitesettings_change", args=[1])).content.decode()
    assert "activeTab == 'phones'" in page


def test_site_settings_name():
    assert str(SiteSettings()) == "Основные"
```

Если для POST формы услуги нужны другие поля (`has_page`, SEO) — `form[name].value()` подставит текущие значения; булевы `False` отправлять не нужно (как в браузере).

В `src/tests/e2e/test_admin_chrome.py` дописать:

```python
# Вкладки полей (fieldsets_tabs Unfold), правый край которых за пределами экрана.
CLIPPED_TABS = """
() => [...document.querySelectorAll('[x-data*="activeFieldsetTab"] > div > nav > a')]
  .filter(a => a.getBoundingClientRect().right > window.innerWidth + 1)
  .map(a => a.textContent.trim())
"""


def test_settings_tabs_fit_phone(admin_page, live_server):
    page = admin_page
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(f"{live_server.url}/admin/core/sitesettings/")
    page.locator('[x-data*="activeFieldsetTab"]').first.wait_for()
    assert page.evaluate(CLIPPED_TABS) == []
```

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_admin_forms.py -v`
Expected: FAIL.

- [ ] **Step 3: `SEO_SECTION`** — `src/apps/core/admin_utils.py`, под `SEO_FIELDSET`:

```python
# То же в формах с вкладками-inline (услуга, категория): свёрнутый блок под основными полями,
# а не вторая строка вкладок внутри «Основного».
SEO_SECTION = (
    "SEO",
    {"classes": ["collapse"], "description": seo_help("object"), "fields": ["seo_title", "seo_description"]},
)
```

- [ ] **Step 4: Услуга и категория**

`src/templates/admin/catalog/bulk_photos_field.html`:

```django
{% with field=adminform.form.bulk_photos %}
{% if field %}
<div class="flex flex-col gap-2 px-3 pt-3 pb-4">
  <label class="font-semibold" for="{{ field.id_for_label }}">{{ field.label }}</label>
  {{ field }}
  {% if field.help_text %}<p class="text-sm text-base-500">{{ field.help_text }}</p>{% endif %}
  {% if field.errors %}<div class="text-sm text-red-600">{{ field.errors }}</div>{% endif %}
</div>
{% endif %}
{% endwith %}
```

`src/apps/catalog/admin.py`:

```python
class CategoryPhotoInline(OrderedInlineMixin, TabularInline):
    ...
    # Поле «Загрузить фото пачкой» (форма записи, BulkPhotosForm) — над таблицей фото, в той же вкладке.
    template_before = "admin/catalog/bulk_photos_field.html"
    verbose_name_plural = "Фото"
```

`CategoryAdmin.fieldsets` (поле `bulk_photos` в fieldsets не перечисляется — объявленное поле формы остаётся в ней и выводится шаблоном выше):

```python
    fieldsets = (
        (None, {"fields": ["name", "slug", "menu_groups", "description", "preview", "is_published"]}),
        SEO_SECTION,
    )
```

`ServiceAdmin.fieldsets`:

```python
    fieldsets = (
        (
            None,
            {
                "fields": [
                    "name",
                    "slug",
                    ("price", "price_unit"),
                    "short_description",
                    "description",
                    ("is_published", "has_page"),
                ]
            },
        ),
        SEO_SECTION,
    )
```

Импорт `SEO_FIELDSET` в `catalog/admin.py` заменить на `SEO_SECTION`, если больше не используется. Проверь в браузере (`make run`, форма услуги): вкладки «Основное / Фото / Категории», поле пачки — во вкладке «Фото», перетаскивание файлов в него работает (`admin_dropzone.js`), счётчики SEO-полей работают в развёрнутом блоке.

- [ ] **Step 5: Настройки сайта** — `src/apps/core/admin.py`:

```python
class PhoneInline(OrderedInlineMixin, TabularInline):
    ...
    tab = True  # своя вкладка: без неё таблица телефонов видна под любой вкладкой полей
```

В `SiteSettingsAdmin.fieldsets` — убрать отдельные «Логотип» и «Юридическое», добавить после «Контактов»:

```python
        ("Логотип и политика", {"classes": ["tab"], "fields": ["header_logo", "privacy_page"]}),
```

`src/apps/core/models.py`, `SiteSettings.__str__` → `return "Основные"` (крошки «Сайт › Настройки сайта › Основные» вместо двух «Настройки сайта»).

`src/static/css/admin.css` — дописать:

```css
/* Вкладки полей формы (unfold/helpers/fieldsets_tabs.html) на узком экране — в несколько строк,
   иначе правые обрезаны (13 вкладок настроек на телефоне). Сверять селектор при обновлении Unfold. */
[x-data*="activeFieldsetTab"] > div > nav {
  flex-wrap: wrap;
}
```

- [ ] **Step 6: Тесты проходят**

Run: `cd src && uv run pytest tests/test_admin_forms.py tests/test_admin.py tests/test_admin_help.py -v && uv run pytest tests/e2e/test_admin_chrome.py -v`
Expected: PASS (e2e — после `uv run manage.py tailwind build`, см. `make e2e`).

- [ ] **Step 7: Справка и CLAUDE.md**

`grep -rn "Загрузка фото\|вкладк" src/templates/admin/help src/apps/*/admin.py src/apps/core/bulk_upload.py` — заменить «вкладка «Загрузка фото»» на «вкладка «Фото», поле «Загрузить фото пачкой» над таблицей», «вкладка SEO» у услуг и категорий — на «блок «SEO» под основными полями (раскрывается по клику)». В `settings.html`: телефоны — на вкладке «Телефоны» вверху формы; «Логотип и политика» вместо двух вкладок.

`CLAUDE.md`: в абзац «Рамка админки» добавить: «перенос строки вкладок полей на узком экране — `static/css/admin.css` (селектор по `activeFieldsetTab`, сверять при обновлении Unfold); у форм услуги и категории вкладки только верхнего уровня (inline), SEO — свёрнутый `SEO_SECTION`, поле пачки — `template_before` у inline фото».

- [ ] **Step 8: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Формы админки: одна строка вкладок у услуги и категории, телефоны на своей вкладке

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Формулировки Django и Unfold по-русски

**Files:**
- Modify: `src/locale/ru/LC_MESSAGES/django.po` (+ `django.mo`)
- Create: `src/templates/admin/submit_line.html` (копия `unfold/templates/admin/submit_line.html`)
- Create: `src/templates/unfold/helpers/pagination_default.html` (копия из Unfold)
- Test: `src/tests/test_admin_forms.py`

**Interfaces:**
- Produces: `templates/admin/submit_line.html` — задача 7 меняет в нём подпись кнопки удаления.

- [ ] **Step 1: Падающие тесты** — дописать в `src/tests/test_admin_forms.py`:

```python
from datetime import date

from django.contrib.messages import get_messages


def test_change_form_wording(admin_client):
    service = Service.objects.create(name="Батут")
    page = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    for awkward in ("Удалить Услуга", "Добавить еще один", "Сохранить и добавить другой объект", "Choose file to upload"):
        assert awkward not in page


def test_saved_message_wording(admin_client):
    response = admin_client.post(
        reverse("admin:content_review_add"), {"text": "<p>Отлично</p>", "date": date.today().strftime("%d.%m.%Y"), "is_published": "on", "link": ""}
    )
    assert response.status_code == 302
    texts = [str(m) for m in get_messages(response.wsgi_request)]
    assert any(t.endswith("— добавлено.") for t in texts), texts


def test_changelist_total_wording(admin_client):
    Category.objects.create(name="А")
    Category.objects.create(name="Б")
    page = admin_client.get(reverse("admin:catalog_category_changelist")).content.decode()
    assert "Всего: 2" in page
```

(Формат даты в POST — как ожидает виджет даты Unfold в русской локали; если не проходит — посмотри `response.context["adminform"].form.errors` и возьми формат оттуда.)

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_admin_forms.py -k "wording or total" -v`
Expected: FAIL.

- [ ] **Step 3: Переводы** — дописать в `src/locale/ru/LC_MESSAGES/django.po` (без флага `python-format`: строки без подстановок, а `%` со словарём их не трогает):

```po
msgid "Add another %(verbose_name)s"
msgstr "Добавить ещё"

msgid "Add another %(model)s"
msgstr "Добавить"

msgid "Add %(name)s"
msgstr "Добавить"

msgid "Save and add another"
msgstr "Сохранить и добавить ещё"

msgid "The {name} “{obj}” was added successfully."
msgstr "«{obj}» — добавлено."

msgid "The {name} “{obj}” was changed successfully."
msgstr "«{obj}» — сохранено."

msgid "The {name} “{obj}” was added successfully. You may edit it again below."
msgstr "«{obj}» — добавлено. Можно продолжить редактирование."

msgid "The {name} “{obj}” was changed successfully. You may edit it again below."
msgstr "«{obj}» — сохранено. Можно продолжить редактирование."

msgid "The {name} “{obj}” was added successfully. You may add another {name} below."
msgstr "«{obj}» — добавлено. Ниже можно добавить ещё."

msgid "The {name} “{obj}” was changed successfully. You may add another {name} below."
msgstr "«{obj}» — сохранено. Ниже можно добавить ещё."

msgid "The %(name)s “%(obj)s” was deleted successfully."
msgstr "«%(obj)s» — удалено."

msgid "Choose file to upload"
msgstr "Выберите файл или перетащите сюда"
```

Точные `msgid` сверить с `src/.venv/lib/python3.14/site-packages/django/contrib/admin/locale/ru/LC_MESSAGES/django.po` (кавычки «“”» — именно такие) и с шаблонами Unfold (`grep -rn "Choose file to upload\|Add another" src/.venv/lib/python3.14/site-packages/unfold/templates`). Если `msgid` уже есть в нашем `.po` — поправить существующий, не дублировать.

Run: `cd src && uv run manage.py compilemessages -l ru`

- [ ] **Step 4: Шаблоны Unfold**

```bash
cd src
cp .venv/lib/python3.14/site-packages/unfold/templates/admin/submit_line.html templates/admin/submit_line.html
mkdir -p templates/unfold/helpers
cp .venv/lib/python3.14/site-packages/unfold/templates/unfold/helpers/pagination_default.html templates/unfold/helpers/pagination_default.html
```

В `templates/admin/submit_line.html` строку `{% trans "Delete" %} {{ opts.verbose_name }}` заменить на `{% trans "Delete" %}`, а над первой строкой файла добавить `{# Копия unfold/templates/admin/submit_line.html: «Удалить» без названия раздела. Сверять при обновлении Unfold. #}` (после `{% load %}`, если он первый).

В `templates/unfold/helpers/pagination_default.html` блок с `{{ cl.result_count }}` и `verbose_name`/`verbose_name_plural` заменить на `Всего: {{ cl.result_count }}` и добавить такой же однострочный комментарий-пометку.

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest tests/test_admin_forms.py tests/test_admin.py -v`
Expected: PASS.

- [ ] **Step 6: CLAUDE.md** — в абзац про локаль Unfold добавить: «там же — нейтральные формулировки стандартных строк Django («Добавить ещё», ««…» — сохранено.»): подстановка `verbose_name` не склоняется. Копии шаблонов Unfold `admin/submit_line.html` («Удалить» без названия раздела) и `unfold/helpers/pagination_default.html` («Всего: N») — сверять при обновлении Unfold».

- [ ] **Step 7: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Админка: формулировки Django и Unfold без несклоняемых названий разделов

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Корзина

**Files:**
- Modify: `src/apps/core/models.py` (`TrashableModel`; базы `InfoPage`, `Announcement`)
- Modify: `src/apps/catalog/models.py` (базы `Service`, `Category`, `CategoryGroup`)
- Modify: `src/apps/content/models.py` (базы `Event`, `Review`)
- Create: миграции `catalog`, `content`, `core` (`makemigrations`)
- Create: `src/apps/core/trash.py`
- Modify: `src/apps/core/admin_utils.py` (`TrashAdminMixin`)
- Modify: `src/apps/catalog/admin.py`, `src/apps/content/admin.py`, `src/apps/core/admin.py`
- Create: `src/templates/admin/trash/confirm.html`, `src/templates/admin/trash/list.html`, `src/static/js/admin_trash.js`
- Modify: `src/templates/admin/submit_line.html` (из задачи 6)
- Test: `src/tests/test_trash.py`

**Interfaces:**
- Produces: `apps.core.models.TrashableModel` (поле `deleted_at`, методы `move_to_trash()`, `restore()`, свойство `in_trash`); `apps.core.trash.TRASH_DAYS = 30`, `apps.core.trash.purge_expired(model, now=None) -> int`; `apps.core.admin_utils.TrashAdminMixin` (атрибут `trash_enabled = True`, Unfold-действие списка `trash`, URL-имя `admin:<app>_<model>_trash`). Задача 8 фильтрует `deleted_at__isnull=True`.

- [ ] **Step 1: Падающие тесты**

`src/tests/test_trash.py`:

```python
from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import TrashAdminMixin
from apps.core.models import InfoPage, SiteSettings

pytestmark = pytest.mark.django_db


@pytest.fixture
def service(make_image):
    category = Category.objects.create(name="Парк", is_published=True)
    service = Service.objects.create(name="Батут", has_page=True)
    CategoryService.objects.create(category=category, service=service, order=1)
    ServicePhoto.objects.create(service=service, image=make_image())
    return service


def test_delete_moves_to_trash(admin_client, client, service):
    url = reverse("admin:catalog_service_delete", args=[service.pk])
    assert "корзин" in admin_client.get(url).content.decode()
    response = admin_client.post(url, {"post": "yes"})
    assert response.status_code == 302
    service.refresh_from_db()
    assert service.in_trash and not service.is_published
    photo = service.photos.get()
    assert photo.image.storage.exists(photo.image.name)  # фото и файл на месте
    assert service.category_links.exists()
    listed = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list
    assert service not in listed
    assert admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).status_code == 302
    assert client.get(service.get_absolute_url()).status_code == 404


def test_restore_returns_draft(admin_client, service):
    service.move_to_trash()
    response = admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "restore": "1"})
    assert response.status_code == 302
    service.refresh_from_db()
    assert not service.in_trash and not service.is_published
    assert service in admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list


def test_purge_deletes_forever(admin_client, service, django_capture_on_commit_callbacks):
    service.move_to_trash()
    photo = service.photos.get()
    storage, name = photo.image.storage, photo.image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "purge": "1"})
    assert not Service.objects.filter(pk=service.pk).exists()
    assert not storage.exists(name)


def test_expired_items_purged_on_open(admin_client, service):
    service.move_to_trash()
    Service.objects.filter(pk=service.pk).update(deleted_at=timezone.now() - timedelta(days=31))
    assert admin_client.get(reverse("admin:catalog_service_trash")).status_code == 200
    assert not Service.objects.filter(pk=service.pk).exists()


def test_bulk_action_moves_to_trash(admin_client, service):
    url = reverse("admin:catalog_service_changelist")
    actions = dict(admin_client.get(url).context["action_form"].fields["action"].choices)
    assert "delete_selected" not in actions and "move_selected_to_trash" in actions
    admin_client.post(url, {"action": "move_selected_to_trash", "_selected_action": [service.pk]})
    service.refresh_from_db()
    assert service.in_trash


def test_trashed_hidden_from_autocomplete_and_inlines(admin_client, service):
    category = Category.objects.get()
    category.move_to_trash()
    response = admin_client.get(
        reverse("admin:autocomplete"),
        {"term": "Парк", "app_label": "catalog", "model_name": "categoryservice", "field_name": "category"},
    )
    assert response.json()["results"] == []
    page = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    assert "Парк" not in page


def test_trashed_privacy_page_disappears_from_site(client):
    page = InfoPage.objects.create(title="Политика", body="<p>Текст</p>", is_published=True)
    site = SiteSettings.load()
    site.privacy_page = page
    site.save()
    page.move_to_trash()
    response = client.get("/")
    assert response.status_code == 200
    assert page.get_absolute_url() not in response.content.decode()


def test_every_trash_admin_has_trash_button():
    for model, model_admin in admin.site._registry.items():
        if isinstance(model_admin, TrashAdminMixin):
            assert "trash" in model_admin.actions_list, model
```

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_trash.py -v`
Expected: FAIL — `ImportError: cannot import name 'TrashAdminMixin'`.

- [ ] **Step 3: Модель** — `src/apps/core/models.py`, после `OrderedModel` (`timezone` — `from django.utils import timezone`):

```python
class TrashableModel(models.Model):
    """Запись, которую «Удалить» в админке переносит в корзину (apps/core/trash.py), а не стирает.

    В корзине запись снята с публикации — сайт её не показывает через обычные `published()`, — и скрыта из
    списков админки (`TrashAdminMixin`). Фото, привязки и адрес страницы сохраняются."""

    deleted_at = models.DateTimeField("В корзине с", null=True, blank=True, editable=False, db_index=True)

    class Meta:
        abstract = True

    @property
    def in_trash(self) -> bool:
        return self.deleted_at is not None

    def move_to_trash(self) -> None:
        self.deleted_at = timezone.now()
        self.is_published = False
        self.save()

    def restore(self) -> None:
        # Возвращается черновиком: администратор проверит и опубликует сам.
        self.deleted_at = None
        self.save()
```

Добавить `TrashableModel` первым базовым классом: `Service(TrashableModel, SeoModel)`, `Category(TrashableModel, SeoModel, OrderedModel)`, `CategoryGroup(TrashableModel, OrderedModel)`, `Event(TrashableModel, SeoModel)`, `Review(TrashableModel, models.Model)` → `Review(TrashableModel)`, `InfoPage(TrashableModel, SeoModel, OrderedModel)`, `Announcement(TrashableModel, OrderedModel)`. Явные `class Meta(OrderedModel.Meta)` у моделей не трогать.

Run: `cd src && uv run manage.py makemigrations catalog content core && uv run manage.py migrate`

- [ ] **Step 4: Очистка** — `src/apps/core/trash.py`:

```python
"""Корзина: «Удалить» в админке у основных записей переносит их сюда (`TrashableModel.move_to_trash`).

Через `TRASH_DAYS` дней запись удаляется навсегда — `purge_expired` вызывается при открытии корзины и при каждом
переносе в неё, отдельный планировщик не нужен."""

from datetime import timedelta

from django.utils import timezone

TRASH_DAYS = 30


def purge_expired(model, now=None) -> int:
    limit = (now or timezone.now()) - timedelta(days=TRASH_DAYS)
    # QuerySet.delete шлёт post_delete по каждой записи — файлы фото удаляются после коммита (apps/core/files.py).
    _total, per_model = model._default_manager.filter(deleted_at__lt=limit).delete()
    return per_model.get(model._meta.label, 0)
```

- [ ] **Step 5: Миксин админки** — `src/apps/core/admin_utils.py`:

```python
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from unfold.decorators import action

from apps.core.trash import TRASH_DAYS, purge_expired


class TrashAdminMixin:
    """«Удалить» переносит запись в корзину (`TrashableModel`). Над списком — кнопка «Корзина»
    (добавьте "trash" в `actions_list`): там «Восстановить» и «Удалить навсегда»."""

    trash_enabled = True  # подпись «В корзину» вместо «Удалить» (templates/admin/submit_line.html)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted_at__isnull=True)

    def _changelist_url(self):
        opts = self.model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        if self.has_delete_permission(request):
            actions["move_selected_to_trash"] = self.get_action("move_selected_to_trash")
        return actions

    @admin.action(description="Переместить в корзину")
    def move_selected_to_trash(self, request, queryset):
        moved = 0
        for obj in queryset:
            obj.move_to_trash()
            self.log_change(request, obj, "Перемещено в корзину")
            moved += 1
        purge_expired(self.model)
        self.message_user(
            request, f"В корзину перемещено: {moved}. Восстановить — кнопка «Корзина» над списком.", messages.SUCCESS
        )

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied
        if request.method == "POST":
            obj.move_to_trash()
            self.log_change(request, obj, "Перемещено в корзину")
            purge_expired(self.model)
            self.message_user(
                request,
                f"«{obj}» — в корзине. Восстановить можно {TRASH_DAYS} дней: кнопка «Корзина» над списком.",
                messages.SUCCESS,
            )
            return redirect(self._changelist_url())
        context = {
            **self.admin_site.each_context(request),
            "title": "Переместить в корзину?",
            "object": obj,
            "opts": self.model._meta,
            "trash_days": TRASH_DAYS,
            "changelist_url": self._changelist_url(),
            **(extra_context or {}),
        }
        return TemplateResponse(request, "admin/trash/confirm.html", context)

    @action(description="Корзина", url_path="trash", permissions=["delete"], icon="delete")
    def trash(self, request):
        trashed = self.model._default_manager.filter(deleted_at__isnull=False).order_by("-deleted_at")
        if request.method == "POST":
            obj = get_object_or_404(trashed, pk=request.POST.get("pk"))
            if "restore" in request.POST:
                if not self.has_change_permission(request, obj):
                    raise PermissionDenied
                obj.restore()
                self.log_change(request, obj, "Восстановлено из корзины")
                self.message_user(
                    request, f"«{obj}» восстановлено черновиком — проверьте и опубликуйте.", messages.SUCCESS
                )
            elif "purge" in request.POST:
                name = str(obj)
                self.log_deletions(request, trashed.filter(pk=obj.pk))
                obj.delete()
                self.message_user(request, f"«{name}» удалено навсегда.", messages.SUCCESS)
            return redirect(request.path)
        purge_expired(self.model)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Корзина: {self.model._meta.verbose_name_plural}",
            "opts": self.model._meta,
            "items": [(obj, obj.deleted_at + timedelta(days=TRASH_DAYS)) for obj in trashed],
            "trash_days": TRASH_DAYS,
            "changelist_url": self._changelist_url(),
        }
        return render(request, "admin/trash/list.html", context)
```

Если `log_deletions` в Django 6.1 называется иначе — смотри `django/contrib/admin/options.py` (`def log_delet`). `icon="delete"` — Material Symbols, как в `_nav`.

- [ ] **Step 6: Подключить к админкам**

Миксин — первым базовым классом, `"trash"` — в `actions_list`:
- `src/apps/catalog/admin.py`: `CategoryGroupAdmin(TrashAdminMixin, SiteModelAdmin)`, `CategoryAdmin(TrashAdminMixin, BulkPhotosAdminMixin, SiteModelAdmin)`, `ServiceAdmin(TrashAdminMixin, BulkPhotosAdminMixin, SiteModelAdmin)`; у каждой `actions_list = ["trash"]`. `CategoryAdmin.delete_view` (предупреждение об услугах без категории) остаётся — он вызывает `super().delete_view`.
- `src/apps/content/admin.py`: `EventAdmin`, `ReviewAdmin` — так же.
- `src/apps/core/admin.py`: `AnnouncementAdmin`, `InfoPageAdmin` — так же.

Inline не должны показывать связи с записями в корзине:

```python
class CategoryServiceInline(OrderedInlineMixin, TabularInline):
    ...
    def get_queryset(self, request):
        return super().get_queryset(request).filter(service__deleted_at__isnull=True)


class ServiceCategoryInline(TabularInline):
    ...
    def get_queryset(self, request):
        return super().get_queryset(request).filter(category__deleted_at__isnull=True)
```

`templates/admin/submit_line.html` (копия из задачи 6): `{% trans "Delete" %}` у кнопки удаления заменить на `{% if adminform.model_admin.trash_enabled %}В корзину{% else %}{% trans "Delete" %}{% endif %}`.

- [ ] **Step 7: Шаблоны и JS**

`src/templates/admin/trash/confirm.html`:

```django
{% extends "admin/base_site.html" %}

{% block content %}
<form method="post" class="flex max-w-xl flex-col gap-4">
  {% csrf_token %}
  <input type="hidden" name="post" value="yes">
  <p>«<strong>{{ object }}</strong>» уйдёт с сайта и из списка. Его фото и связи сохранятся: {{ trash_days }} дней запись можно вернуть кнопкой «Корзина» над списком, потом она удалится навсегда.</p>
  <div class="flex flex-wrap gap-2">
    <button type="submit" class="bg-primary-600 rounded-md px-4 py-2 font-semibold text-white">В корзину</button>
    <a href="{{ changelist_url }}" class="rounded-md border border-base-200 px-4 py-2">Отмена</a>
  </div>
</form>
{% endblock %}
```

`src/templates/admin/trash/list.html`:

```django
{% extends "admin/base_site.html" %}
{% load static %}

{% block extrahead %}{{ block.super }}<script src="{% static 'js/admin_trash.js' %}" defer></script>{% endblock %}

{% block content %}
<div class="flex max-w-3xl flex-col gap-4">
  <p>Записи, удалённые кнопкой «Удалить». На сайте их нет. Через {{ trash_days }} дней после удаления они стираются навсегда вместе с фото. <a href="{{ changelist_url }}" class="underline">Вернуться к списку</a></p>
  {% if items %}
  <table class="w-full">
    <thead>
      <tr class="text-left"><th class="py-2 pr-4">Запись</th><th class="py-2 pr-4">Удалится навсегда</th><th class="py-2"></th></tr>
    </thead>
    <tbody>
      {% for obj, expires in items %}
      <tr class="border-t border-base-200">
        <td class="py-2 pr-4 font-semibold">{{ obj }}</td>
        <td class="py-2 pr-4">{{ expires|date:"j E" }}</td>
        <td class="py-2">
          <form method="post" class="flex flex-wrap gap-2">
            {% csrf_token %}
            <input type="hidden" name="pk" value="{{ obj.pk }}">
            <button type="submit" name="restore" value="1" class="bg-primary-600 rounded-md px-3 py-1 font-semibold text-white">Восстановить</button>
            <button type="submit" name="purge" value="1" class="rounded-md border border-base-200 px-3 py-1 text-red-600">Удалить навсегда</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="text-base-500">Корзина пуста.</p>
  {% endif %}
</div>
{% endblock %}
```

`src/static/js/admin_trash.js`:

```js
// Корзина админки: «Удалить навсегда» — только после подтверждения (без inline-обработчиков: CSP).
document.addEventListener("submit", (event) => {
  if (event.submitter?.name === "purge" && !window.confirm("Удалить навсегда? Восстановить будет нельзя.")) {
    event.preventDefault();
  }
});
```

Проверь, что классы из шаблонов есть в CSS Unfold (как в `templates/admin/bulk_upload.html`); `text-base-500`, `border-base-200` используются Unfold повсеместно.

- [ ] **Step 8: Тесты проходят**

Run: `cd src && uv run pytest tests/test_trash.py tests/test_admin.py tests/test_admin_help.py -v && uv run pytest -q`
Expected: PASS. Если упали старые тесты, удалявшие записи через админку и проверявшие, что их нет в базе, — теперь запись в корзине: проверять `in_trash`, либо удалять через `obj.delete()`.

- [ ] **Step 9: Справка и CLAUDE.md**

В `src/templates/admin/help/sections/basics.html` — абзац «Корзина»: «Кнопка «В корзину» в форме и действие «Переместить в корзину» в списке не стирают запись: она уходит с сайта и из списка, а фото и привязки сохраняются. Кнопка «Корзина» над списком открывает удалённое: «Восстановить» вернёт запись черновиком (опубликуйте её снова), «Удалить навсегда» сотрёт её с фото. Через 30 дней запись удаляется сама. Так работают услуги, категории, группы, мероприятия, отзывы, плашки и инфо-страницы; фото галереи и партнёры удаляются сразу.» Поправить справку там, где сказано, что удаление необратимо (`grep -rn "навсегда\|необратим\|удалить" src/templates/admin/help/sections/`).

`CLAUDE.md`, раздел `apps/core`: «корзина — `TrashableModel` (`deleted_at`) у услуг, категорий, групп, мероприятий, отзывов, плашек и инфо-страниц: «Удалить» в админке (`TrashAdminMixin`) снимает с публикации и прячет из списков, «Корзина» над списком — восстановить или удалить навсегда, через `TRASH_DAYS` — `purge_expired` (`apps/core/trash.py`) при открытии корзины и переносе в неё. Публичные view отдельной проверки не делают: запись в корзине не опубликована».

- [ ] **Step 10: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Корзина в админке: удалённое можно восстановить 30 дней

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Предпросмотр черновиков

**Files:**
- Create: `src/apps/core/preview.py`
- Modify: `src/apps/catalog/views.py` (`category_detail`, `service_detail`), `src/apps/content/views.py` (`event_detail`), `src/apps/core/views.py` (`info_page`)
- Create: `src/templates/partials/preview_banner.html`
- Modify: `src/templates/base.html`
- Modify: `src/apps/catalog/admin.py` (`ServiceAdmin.view_on_site`)
- Test: `src/tests/test_preview.py`

**Interfaces:**
- Consumes: `deleted_at` (задача 7).
- Produces: `apps.core.preview.get_for_view(request, queryset, **lookup) -> tuple[obj, bool]`; `apps.core.preview.preview_context(obj, preview: bool) -> dict` (ключи `preview`, `preview_admin_url`); `apps.core.preview.finish(response, preview: bool) -> response`.

- [ ] **Step 1: Падающие тесты**

`src/tests/test_preview.py`:

```python
from datetime import date, timedelta

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.catalog.admin import ServiceAdmin
from apps.catalog.models import Category, CategoryService, Service
from apps.content.models import Event
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def draft_category():
    return Category.objects.create(name="Черновая", is_published=False)


def test_visitor_gets_404(client, draft_category):
    assert client.get(draft_category.get_absolute_url()).status_code == 404


def test_staff_sees_draft_with_banner(admin_client, draft_category):
    response = admin_client.get(draft_category.get_absolute_url())
    assert response.status_code == 200
    page = response.content.decode()
    assert "Черновик" in page and 'name="robots"' in page
    assert reverse("admin:catalog_category_change", args=[draft_category.pk]) in page
    assert "no-cache" in response["Cache-Control"]


def test_staff_without_view_permission_gets_404(client, django_user_model, draft_category):
    user = django_user_model.objects.create_user("editor", password="x", is_staff=True)
    client.force_login(user)
    assert client.get(draft_category.get_absolute_url()).status_code == 404
    user.user_permissions.add(Permission.objects.get(codename="view_category"))
    assert client.get(draft_category.get_absolute_url()).status_code == 200


def test_trashed_not_previewed(admin_client, draft_category):
    draft_category.move_to_trash()
    assert admin_client.get(draft_category.get_absolute_url()).status_code == 404


def test_published_page_same_for_visitor_and_staff(client, admin_client):
    category = Category.objects.create(name="Открытая", is_published=True)
    anon = client.get(category.get_absolute_url())
    staff = admin_client.get(category.get_absolute_url())
    assert "Черновик" not in staff.content.decode()
    assert anon["ETag"] == staff["ETag"]


def test_draft_service_event_info_previewed(admin_client):
    service = Service.objects.create(name="Услуга", has_page=True, is_published=False)
    event = Event.objects.create(title="Событие", date=date.today() + timedelta(days=3), is_published=False)
    info = InfoPage.objects.create(title="Инфо", body="<p>Текст</p>", is_published=False)
    for obj in (service, event, info):
        response = admin_client.get(obj.get_absolute_url())
        assert response.status_code == 200, obj
        assert "Черновик" in response.content.decode()


def test_service_without_page_view_on_site(draft_category):
    service = Service.objects.create(name="Без страницы", has_page=False)
    model_admin = ServiceAdmin(Service, admin.site)
    assert model_admin.view_on_site(service) is None
    CategoryService.objects.create(category=draft_category, service=service, order=1)
    assert model_admin.view_on_site(service) == draft_category.get_absolute_url()
```

Проверь, как шаблон выводит `noindex` (`grep -rn "noindex" src/templates/base.html`), и подставь в `test_staff_sees_draft_with_banner` фактический атрибут.

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_preview.py -v`
Expected: FAIL (черновик сотруднику — 404).

- [ ] **Step 3: Модуль** — `src/apps/core/preview.py`:

```python
"""Предпросмотр черновиков: сотрудник по ссылке «Смотреть на сайте» видит неопубликованную страницу с плашкой
«Черновик»; посетители по-прежнему получают 404.

Пользователь (а значит, сессия) проверяется только для неопубликованной записи: ответы опубликованных страниц
не зависят от того, кто смотрит, — ETag/304 не ломаются."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import add_never_cache_headers


def get_for_view(request, queryset, **lookup):
    """(запись, черновик ли). `queryset` — без фильтра публикации (например, `Service.objects.filter(has_page=True)`);
    запись в корзине — 404 всем."""
    obj = get_object_or_404(queryset.filter(deleted_at__isnull=True), **lookup)
    if obj.is_published:
        return obj, False
    opts = obj._meta
    user = request.user
    if user.is_staff and user.has_perm(f"{opts.app_label}.view_{opts.model_name}"):
        return obj, True
    raise Http404


def preview_context(obj, preview: bool) -> dict:
    if not preview:
        return {"preview": False}
    opts = obj._meta
    return {"preview": True, "preview_admin_url": reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])}


def finish(response, preview: bool):
    if preview:
        add_never_cache_headers(response)  # черновик не должен осесть ни в каком кеше
    return response
```

- [ ] **Step 4: View** — общая схема для каждого (пример — категория):

```python
from apps.core.preview import finish, get_for_view, preview_context


def category_detail(request, slug):
    category, preview = get_for_view(request, Category.objects.all(), slug=slug)
    ...
    seo = make_seo(...)  # как было
    if preview:
        seo["noindex"] = True
    response = render(request, "catalog/category.html", {..., "seo": seo, **preview_context(category, preview)})
    return finish(response, preview)
```

- `service_detail`: `get_for_view(request, Service.objects.filter(has_page=True), slug=slug)`;
- `event_detail`: `get_for_view(request, Event.objects.all(), slug=slug)`; уже есть `seo["noindex"] = …` — сделать `seo["noindex"] = preview or (event.is_past and not event.show_after_date)`;
- `info_page`: `get_for_view(request, InfoPage.objects.all(), slug=slug)`.

- [ ] **Step 5: Плашка** — `src/templates/partials/preview_banner.html`:

```django
{% if preview %}
<div class="bg-navy text-white" role="status">
  <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-sm">
    <strong>Черновик</strong>
    <span>Посетители эту страницу не видят — опубликуйте её в админке.</span>
    {% if preview_admin_url %}<a href="{{ preview_admin_url }}" class="underline">Открыть в админке</a>{% endif %}
  </div>
</div>
{% endif %}
```

В `src/templates/base.html` подключить `{% include "partials/preview_banner.html" %}` сразу перед `{% include "partials/site_banner.html" %}` (под шапкой, по той же причине, что и плашка: над шапкой ломается мобильное меню). Ширину контейнера (`max-w-6xl px-4`) сверить с `partials/site_banner.html` и взять ту же.

- [ ] **Step 6: «Смотреть на сайте» у услуги** — `ServiceAdmin`:

```python
    def view_on_site(self, obj):
        # У услуги без отдельной страницы адреса нет — ведём на её категорию; без категории кнопки нет.
        if obj.has_page:
            return obj.get_absolute_url()
        link = (
            obj.category_links.filter(category__deleted_at__isnull=True)
            .select_related("category")
            .order_by("category__order", "category__id")
            .first()
        )
        return link.category.get_absolute_url() if link else None
```

- [ ] **Step 7: Тесты проходят**

Run: `cd src && uv run pytest tests/test_preview.py tests/test_pages.py tests/test_seo.py tests/test_events.py -v && uv run pytest -q`
Expected: PASS.

- [ ] **Step 8: Справка и CLAUDE.md**

`src/templates/admin/help/sections/not-visible.html` (раздел «почему не видно на сайте») — абзац: «Черновик можно посмотреть до публикации: кнопка «Смотреть на сайте» в форме откроет страницу с тёмной плашкой «Черновик». Посетители и поисковики её не видят. У услуги без отдельной страницы кнопка ведёт на её категорию.»

`CLAUDE.md`, абзац «Неопубликованное — 404»: дописать «посетителям; сотруднику с правом просмотра — страница с плашкой «Черновик» (`apps/core/preview.py`: `get_for_view` читает сессию только для неопубликованной записи — ETag опубликованных не меняется; `noindex` и `no-cache`)».

- [ ] **Step 9: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Предпросмотр черновиков для сотрудников; «Смотреть на сайте» у услуги без страницы

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: «Дублировать» услугу и мероприятие

**Files:**
- Modify: `src/apps/core/files.py` (`clone_file`)
- Modify: `src/apps/catalog/models.py` (`Service.duplicate`), `src/apps/content/models.py` (`Event.duplicate`)
- Modify: `src/apps/catalog/admin.py`, `src/apps/content/admin.py` (`actions_detail`)
- Test: `src/tests/test_duplicate.py`

**Interfaces:**
- Consumes: `next_order` (задача 2).
- Produces: `apps.core.files.clone_file(field_file) -> ContentFile | None`; `Service.duplicate() -> Service`; `Event.duplicate() -> Event`.

- [ ] **Step 1: Падающие тесты**

`src/tests/test_duplicate.py`:

```python
from datetime import date

import pytest
from django.urls import reverse

from apps.catalog.models import Category, CategoryService, Service, ServicePhoto
from apps.content.models import Event

pytestmark = pytest.mark.django_db


@pytest.fixture
def service(make_image):
    category = Category.objects.create(name="Парк")
    CategoryService.objects.create(category=category, service=Service.objects.create(name="Другая"), order=4)
    service = Service.objects.create(
        name="Фрироуп", price="1500", price_unit="час", short_description="<p>Час</p>", has_page=True,
        seo_title="SEO", seo_description="Описание",
    )
    CategoryService.objects.create(category=category, service=service, order=1)
    ServicePhoto.objects.create(service=service, image=make_image("a.jpg"), order=1)
    return service


def test_service_duplicate(service, django_capture_on_commit_callbacks):
    copy = service.duplicate()
    assert copy.pk != service.pk and copy.slug != service.slug
    assert copy.name == "Фрироуп (копия)"
    assert (copy.price, copy.price_unit, copy.short_description, copy.has_page) == ("1500", "час", "<p>Час</p>", True)
    assert not copy.is_published
    assert (copy.seo_title, copy.seo_description) == ("", "")
    assert CategoryService.objects.get(service=copy).order == 5  # в конец категории
    original_photo, copied_photo = service.photos.get(), copy.photos.get()
    assert copied_photo.image.name != original_photo.image.name
    with django_capture_on_commit_callbacks(execute=True):
        copy.delete()
    assert original_photo.image.storage.exists(original_photo.image.name)


def test_duplicate_skips_missing_file(service):
    photo = service.photos.get()
    photo.image.storage.delete(photo.image.name)
    copy = service.duplicate()
    assert copy.photos.count() == 0


def test_event_duplicate(make_image):
    event = Event.objects.create(title="Клубная встреча", date=date(2026, 11, 1), image=make_image(), price="500")
    copy = event.duplicate()
    assert copy.title == event.title and copy.date == event.date and copy.price == "500"
    assert not copy.is_published and copy.slug != event.slug
    assert copy.image.name != event.image.name


def test_duplicate_button_redirects_to_copy(admin_client, service):
    response = admin_client.get(reverse("admin:catalog_service_duplicate", args=[service.pk]))
    copy = Service.objects.exclude(pk=service.pk).get(name__endswith="(копия)")
    assert response.status_code == 302
    assert response.url == reverse("admin:catalog_service_change", args=[copy.pk])
```

- [ ] **Step 2: Запустить — падают**

Run: `cd src && uv run pytest tests/test_duplicate.py -v`
Expected: FAIL — `AttributeError: 'Service' object has no attribute 'duplicate'`.

- [ ] **Step 3: `clone_file`** — `src/apps/core/files.py` (`from django.core.files.base import ContentFile`):

```python
def clone_file(field_file) -> ContentFile | None:
    """Копия файла для новой записи: общий файл у двух записей нельзя — удаление одной стёрло бы его у другой.
    Новое имя даст `upload_to` поля. Файла нет на диске — None."""
    if not field_file:
        return None
    try:
        with field_file.storage.open(field_file.name, "rb") as source:
            return ContentFile(source.read(), name=os.path.basename(field_file.name))
    except OSError:  # в т. ч. FileNotFoundError
        return None
```

- [ ] **Step 4: Методы моделей**

`src/apps/catalog/models.py`, в `Service` (`transaction` уже импортирован; импорты `from apps.core.files import clone_file`, `next_order` из `apps.core.models`, `unique_slug` — уже есть):

```python
    def duplicate(self) -> "Service":
        """Черновик-копия: те же тексты и цена, копии фото, те же категории (в конце каждой). SEO-поля пустые —
        одинаковые заголовки у двух страниц мешают поиску."""
        with transaction.atomic():
            copy = Service.objects.create(
                name=f"{self.name[:120]} (копия)",
                slug=unique_slug(Service(), self.name),
                short_description=self.short_description,
                description=self.description,
                price=self.price,
                price_unit=self.price_unit,
                has_page=self.has_page,
                is_published=False,
            )
            for photo in self.photos.all():
                image = clone_file(photo.image)
                if image:
                    ServicePhoto.objects.create(service=copy, image=image, order=photo.order)
            for link in self.category_links.select_related("category"):
                CategoryService.objects.create(
                    category=link.category, service=copy, order=next_order(CategoryService, category=link.category)
                )
        return copy
```

`ServicePhoto` и `CategoryService` объявлены ниже `Service` в том же модуле — это нормально, к моменту вызова они определены.

`src/apps/content/models.py`, в `Event`:

```python
    def duplicate(self) -> "Event":
        """Черновик-копия для повторяющихся мероприятий: дату и описание администратор поправит."""
        return Event.objects.create(
            title=self.title,
            date=self.date,
            end_date=self.end_date,
            start_time=self.start_time,
            venue=self.venue,
            price=self.price,
            description=self.description,
            link=self.link,
            image=clone_file(self.image) or "",
            show_after_date=self.show_after_date,
            is_published=False,
        )
```

Сверь список полей `Event` с моделью: каждое редактируемое поле, кроме `slug`, SEO и `is_published`, должно копироваться.

- [ ] **Step 5: Кнопка в формах** — `ServiceAdmin` (`from unfold.decorators import action`, `get_object_or_404`, `redirect`, `reverse`, `messages`):

```python
    actions_detail = ["duplicate"]

    # Право — строкой: для кнопок формы Unfold вызывает has_<право>_permission(request, object_id),
    # а у стандартного has_add_permission второго аргумента нет.
    @action(description="Дублировать", url_path="duplicate", permissions=["catalog.add_service"], icon="content_copy")
    def duplicate(self, request, object_id):
        original = get_object_or_404(self.get_queryset(request), pk=object_id)
        copy = original.duplicate()
        self.log_addition(request, copy, f"Копия «{original}»")
        messages.success(request, f"Создана копия «{original}» — черновик. Поменяйте название и цену и опубликуйте.")
        return redirect(reverse("admin:catalog_service_change", args=[copy.pk]))
```

`EventAdmin` — так же, с `permissions=["content.add_event"]`, сообщение «Создана копия «…» — черновик. Поменяйте дату и опубликуйте.», redirect на `admin:content_event_change`.

- [ ] **Step 6: Тесты проходят**

Run: `cd src && uv run pytest tests/test_duplicate.py tests/test_admin.py -v && uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Справка** — `catalog.html`: «Кнопка «Дублировать» вверху формы услуги создаёт черновик-копию с теми же фото и категориями — удобно для вариантов одной услуги (на час и на день). Поменяйте название и цену и опубликуйте.» `events.html`: «Повторяющееся мероприятие — кнопка «Дублировать»: копия-черновик, поменяйте дату и опубликуйте.»

- [ ] **Step 8: Проверки и коммит**

```bash
cd src && uv run ruff check . && uv run ruff format . && uv run pytest -q
git add -A && git commit -m "Админка: «Дублировать» услугу и мероприятие

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## После всех задач

- [ ] `cd src && uv run pytest -q && make e2e` (из корня) — всё зелёное.
- [ ] Ручная проверка в браузере (`make run`, ширины 1440 и 390): форма услуги (вкладки, пачка фото, SEO), настройки (вкладка «Телефоны», вкладки полей переносятся), список услуг (превью, фильтры, поиск «батут»), корзина (удалить → восстановить → удалить навсегда), «Смотреть на сайте» у черновика, «Дублировать», «Поставить в начало» в галерее.
- [ ] Миграции: `uv run manage.py makemigrations --check --dry-run` — изменений нет.
