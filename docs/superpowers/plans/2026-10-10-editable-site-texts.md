# Редактируемые тексты сайта — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 48 коротких текстов витрины (лиды, подсказки, призывы, пустые состояния, заголовки блоков) редактируются в админке «Тексты сайта» с историей версий и возвратом; текущие формулировки переносятся миграцией.

**Architecture:** Новое приложение `apps/texts`: реестр `registry.py` (источник правды: ключ, подпись, текст по умолчанию), модель `SiteText` с `HistoricalRecords()` из `django-simple-history`, тег `{% text "ключ" %}` с ленивой загрузкой всех текстов одним запросом через контекст-процессор, админка на `SimpleHistoryAdmin` + `SiteModelAdmin` с оформлением `unfold.contrib.simple_history`. Data-миграция создаёт записи и начальные версии через `sync_texts`.

**Tech Stack:** Python 3.14, Django 6.1, django-unfold 0.108, django-simple-history ≥ 3.13, pytest + pytest-django, uv.

**Spec:** `docs/superpowers/specs/2026-10-10-editable-site-texts-design.md`

## Global Constraints

- Все команды Python — из `src/` (`cd src`); тесты — `uv run pytest`, линт — `uv run ruff check . && uv run ruff format --check .`; e2e — `uv run --group e2e pytest tests/e2e -m e2e`.
- Весь пользовательский текст (подписи, подсказки, сообщения об ошибках) — на русском.
- Формат текстов — простой текст без HTML; вывод экранируется и проходит через фильтр `nobr` из `apps/core/templatetags/site_tags.py`.
- Админки наследуются от `apps.core.admin_utils.SiteModelAdmin`, не напрямую от `unfold.admin.ModelAdmin`.
- Комментарии в шаблонах `{# … #}` — только однострочные; многострочные — `{% comment %}`.
- `500.html` не трогать: рендерится без контекста и без запросов к БД.
- Поля `SiteSettings` (`home_intro`, `events_intro`, `contacts_text`, `about_motto`, `about_text`, `founder_name`, `founder_lead`, `founder_text`, `nearby_text`) не переносить.
- Длина строки — 120 (ruff); миграции исключены из ruff. Тесты в задачах дописываются в `src/tests/test_texts.py` частями: импорты из каждого шага переносить в начало файла (ruff E402).
- Коммиты — на русском, в конце `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Работа — в отдельной ветке `feat/site-texts`, не в `main`.

## Review Focus

1. **HTML и спецсимволы в тексте** (`<b>`, `&`, кавычки), введённые в админке, выводятся как текст, вёрстку не ломают — тест в задаче 3.
2. **Обязательный текст пуст в БД в обход формы** (shell, импорт) — на сайте выводится текст по умолчанию, заголовок не исчезает — тест в задаче 3.
3. **Таблица текстов пуста** (транзакционные e2e-тесты очищают БД, свежая база до миграции) — страницы выводят тексты по умолчанию — тест в задаче 3.
4. **Начальная версия без автора** — в истории вместо «None» стоит «—» — тест в задаче 4.
5. **Пробелы и переводы строк по краям** при вводе в админке обрезаются, а не сохраняются в текст — тест в задаче 4.

---

## Файлы

| Файл | Ответственность |
|---|---|
| `src/apps/texts/__init__.py`, `apps.py` | Приложение «Тексты сайта» |
| `src/apps/texts/registry.py` | `Page`, `TextDef`, `TEXTS`, `BY_KEY`, `sync_texts` |
| `src/apps/texts/models.py` | `SiteText` + история |
| `src/apps/texts/migrations/0001_initial.py` | Схема (генерируется) |
| `src/apps/texts/migrations/0002_initial_texts.py` | Начальные тексты и версии |
| `src/apps/texts/context_processors.py` | `site_texts` — ленивый словарь `key → text` |
| `src/apps/texts/templatetags/__init__.py`, `site_texts.py` | Тег `{% text %}` |
| `src/apps/texts/admin.py` | Админка «Тексты сайта» |
| `src/apps/texts/hints.py` | Ссылки-подсказки на «Тексты сайта» для админки настроек |
| `src/templates/admin/texts/list_before.html` | Подсказка над списком текстов |
| `src/templates/simple_history/object_history_list.html` | Копия шаблона Unfold: «—» вместо «None» у версии без автора |
| `src/config/settings.py` | Приложения, middleware, контекст-процессор, пункт меню |
| `src/apps/core/admin.py` | Переименование вкладки, подсказки |
| `src/apps/core/legacy/runner.py` | `sync_texts` после импорта |
| `src/templates/**` | 48 литералов → `{% text %}` |
| `src/tests/test_texts.py` | Тесты приложения |
| `docs/decisions.md`, `CLAUDE.md` | Документация |

---

### Task 1: Зависимость, приложение, модель с историей (проверка совместимости с Django 6.1)

Это ворота: если `django-simple-history` не работает на Django 6.1 (миграции, запись версии с автором, возврат версии), **остановиться и сообщить** — переход на запасной вариант (своя модель версий) требует согласования.

**Files:**
- Modify: `src/pyproject.toml`, `src/uv.lock` (через `uv add`)
- Create: `src/apps/texts/__init__.py`, `src/apps/texts/apps.py`, `src/apps/texts/models.py`, `src/apps/texts/registry.py` (минимальный — только `Page`), `src/apps/texts/admin.py` (минимальный), `src/apps/texts/migrations/__init__.py`, `src/apps/texts/migrations/0001_initial.py` (генерируется)
- Modify: `src/config/settings.py`
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Produces: `apps.texts.registry.Page` (`TextChoices`: `home, service, category, events, event, about, contacts, reviews, gallery, error404, common`); модель `apps.texts.models.SiteText(key, page, label, text, order, updated_at)` с `history = HistoricalRecords()`; историческая модель `SiteText.history.model` (в миграциях — `texts.HistoricalSiteText`); админка зарегистрирована, URL `admin:texts_sitetext_change`, `admin:texts_sitetext_history`, `admin:texts_sitetext_simple_history` (args `[pk, history_id]`).

- [ ] **Step 1: Создать ветку и поставить зависимость**

```bash
git switch main && git switch -c feat/site-texts
cd src && uv add "django-simple-history>=3.13"
ls .venv/lib/python3.14/site-packages/simple_history/locale/ru/LC_MESSAGES/
```

Expected: пакет установлен; есть `django.mo` (русская локаль simple-history).

- [ ] **Step 2: Написать падающий тест истории**

`src/tests/test_texts.py`:

```python
import pytest
from django.urls import reverse

from apps.texts.models import SiteText

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_text():
    return SiteText.objects.create(key="test.sample", page="common", label="Проба", text="Было", order=0)


def test_admin_edit_records_version_with_author(admin_client, admin_user, site_text):
    response = admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    assert response.status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Стало"
    latest = site_text.history.first()
    assert latest.history_type == "~" and latest.history_user == admin_user and latest.text == "Стало"


def test_revert_restores_old_version_as_new_one(admin_client, site_text):
    admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    first = site_text.history.earliest("history_date")
    url = reverse("admin:texts_sitetext_simple_history", args=[site_text.pk, first.history_id])
    assert admin_client.get(url).status_code == 200
    assert admin_client.post(url, {"text": first.text}).status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Было"
    assert site_text.history.count() == 3


def test_history_page_opens(admin_client, site_text):
    assert admin_client.get(reverse("admin:texts_sitetext_history", args=[site_text.pk])).status_code == 200
```

- [ ] **Step 3: Запустить — падает**

Run: `uv run pytest tests/test_texts.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.texts'`.

- [ ] **Step 4: Приложение, модель, минимальная админка**

`src/apps/texts/__init__.py` — пустой; `src/apps/texts/migrations/__init__.py` — пустой.

`src/apps/texts/apps.py`:

```python
from django.apps import AppConfig


class TextsConfig(AppConfig):
    name = "apps.texts"
    verbose_name = "Тексты сайта"
```

`src/apps/texts/registry.py` (пока только страницы; реестр текстов — задача 2):

```python
"""Реестр текстов сайта: какие тексты есть, где они на сайте и что выводится по умолчанию.

Источник правды о наборе текстов: модель `SiteText` хранит только текущие значения, а ключи, подписи
и тексты по умолчанию — здесь. Работает и с историческими моделями миграций (`sync_texts`).
"""

from django.db import models


class Page(models.TextChoices):
    HOME = "home", "Главная"
    SERVICE = "service", "Услуга"
    CATEGORY = "category", "Категория"
    EVENTS = "events", "Мероприятия"
    EVENT = "event", "Мероприятие"
    ABOUT = "about", "О нас"
    CONTACTS = "contacts", "Контакты"
    REVIEWS = "reviews", "Отзывы"
    GALLERY = "gallery", "Галерея"
    ERROR404 = "error404", "Страница 404"
    COMMON = "common", "Общее"
```

`src/apps/texts/models.py`:

```python
from django.db import models
from simple_history.models import HistoricalRecords

from apps.texts.registry import Page


class SiteText(models.Model):
    """Текущее значение текста сайта; набор ключей, подписи и тексты по умолчанию — в `registry.py`."""

    key = models.CharField("Ключ", max_length=64, unique=True)
    page = models.CharField("Страница", max_length=16, choices=Page.choices)
    label = models.CharField("Название", max_length=128)
    text = models.TextField("Текст", blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    updated_at = models.DateTimeField("Изменён", auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "текст сайта"
        verbose_name_plural = "тексты сайта"
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.get_page_display()}: {self.label}"
```

`src/apps/texts/admin.py` (минимальная; доводится в задаче 4):

```python
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_utils import SiteModelAdmin
from apps.texts.models import SiteText


@admin.register(SiteText)
class SiteTextAdmin(SimpleHistoryAdmin, SiteModelAdmin):
    fields = ["text"]
```

- [ ] **Step 5: Подключить в настройках**

`src/config/settings.py`:

```python
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.simple_history",
    "django.contrib.admin",
    # … без изменений до django_tailwind_cli …
    "django_tailwind_cli",
    "simple_history",
    "apps.core",
    "apps.catalog",
    "apps.content",
    "apps.texts",
]
```

В `MIDDLEWARE` сразу после `"django.contrib.auth.middleware.AuthenticationMiddleware",`:

```python
    "simple_history.middleware.HistoryRequestMiddleware",  # автор правки в истории текстов
```

- [ ] **Step 6: Сгенерировать миграцию и прогнать тесты**

```bash
uv run manage.py makemigrations texts
uv run pytest tests/test_texts.py -v
```

Expected: создан `apps/texts/migrations/0001_initial.py` с `SiteText` и `HistoricalSiteText`; 3 теста PASS. Если миграция или любой тест падает из-за несовместимости с Django 6.1 (а не из-за опечатки в коде) — **стоп**, сообщить с текстом ошибки.

- [ ] **Step 7: Полный прогон и коммит**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
cd .. && git add src/pyproject.toml src/uv.lock src/apps/texts src/config/settings.py src/tests/test_texts.py
git commit -m "Тексты сайта: приложение apps/texts, модель SiteText с историей (django-simple-history)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Реестр текстов и начальные данные

**Files:**
- Modify: `src/apps/texts/registry.py`
- Create: `src/apps/texts/migrations/0002_initial_texts.py`
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Consumes: `Page`, `SiteText`, `SiteText.history.model` (задача 1).
- Produces: `TextDef(key: str, label: str, default: str, where: str, required: bool = True)` с свойством `page -> str` (префикс ключа); `TEXTS: tuple[TextDef, ...]` (48 штук, порядок — как на страницах); `BY_KEY: dict[str, TextDef]`; `sync_texts(site_text_model, historical_model) -> int` (число созданных записей).

- [ ] **Step 1: Падающие тесты**

Добавить в `src/tests/test_texts.py`:

```python
from apps.texts.registry import BY_KEY, TEXTS, Page, sync_texts


def test_registry_keys_unique_and_pages_known():
    assert len(TEXTS) == len(BY_KEY) == 48
    assert {item.page for item in TEXTS} <= set(Page.values)


def test_migration_created_all_texts_with_initial_version():
    assert dict(SiteText.objects.values_list("key", "text")) == {item.key: item.default for item in TEXTS}
    initial = SiteText.history.filter(history_type="+")
    assert initial.count() == len(TEXTS)
    assert set(initial.values_list("history_change_reason", flat=True)) == {"Начальный текст"}


def test_sync_keeps_edits_restores_labels_and_missing_rows():
    edited = SiteText.objects.get(key="service.booking_hint")
    edited.text, edited.label = "Свой текст", "Старое название"
    edited.save()
    SiteText.objects.filter(key="gallery.empty").delete()
    history = SiteText.history.model

    assert sync_texts(SiteText, history) == 1
    edited.refresh_from_db()
    assert edited.text == "Свой текст" and edited.label == BY_KEY["service.booking_hint"].label
    restored = SiteText.objects.get(key="gallery.empty")
    assert restored.text == BY_KEY["gallery.empty"].default and restored.page == "gallery"
    assert history.filter(id=restored.pk, history_type="+").count() == 1
    assert sync_texts(SiteText, history) == 0
```

- [ ] **Step 2: Запустить — падает**

Run: `uv run pytest tests/test_texts.py -k "registry or migration or sync"`
Expected: FAIL — `ImportError: cannot import name 'BY_KEY'`.

- [ ] **Step 3: Реестр и `sync_texts`**

Дописать в `src/apps/texts/registry.py` (после `Page`; добавить импорты `from typing import NamedTuple` и `from django.utils import timezone`):

```python
class TextDef(NamedTuple):
    key: str  # «<страница>.<имя>»: префикс до точки — значение Page
    label: str  # название в админке
    default: str  # текст по умолчанию — исходная формулировка из шаблона
    where: str  # где на сайте — подсказка в админке
    required: bool = True  # заголовки и тексты, без которых ломается вёрстка; необязательный пустой — блок скрыт

    @property
    def page(self) -> str:
        return self.key.split(".", 1)[0]


TEXTS = (
    # Главная
    TextDef("home.title", "Заголовок первого экрана", "Тренинг-парк Дмитрия Сергеева", "Главная, крупный заголовок вверху"),
    TextDef(
        "home.services_empty",
        "Каталог пуст",
        "Скоро здесь появятся наши услуги.",
        "Главная, вместо каталога, пока нет опубликованных категорий",
        required=False,
    ),
    TextDef("home.events_title", "Заголовок блока мероприятий", "Ближайшие мероприятия", "Главная, лента ближайших мероприятий"),
    TextDef("home.reviews_title", "Заголовок блока отзывов", "Отзывы гостей", "Главная, карусель отзывов"),
    TextDef("home.cta_title", "Призыв связаться: заголовок", "Приезжайте в Т-Парк", "Главная, карточка с кнопками связи внизу"),
    TextDef(
        "home.cta_text",
        "Призыв связаться: текст",
        "Расскажем о программах и подберём формат для вас, семьи или команды.",
        "Главная, под заголовком карточки с кнопками связи",
        required=False,
    ),
    # Услуга
    TextDef(
        "service.booking_hint",
        "Подсказка под кнопками связи",
        "Бронируйте заранее — в тёплый сезон даты разбирают быстро.",
        "Страница услуги, под ценой и кнопками связи",
        required=False,
    ),
    # Категория
    TextDef("category.services_title", "Заголовок списка услуг", "Услуги и цены", "Страница категории, перед карточками услуг"),
    TextDef(
        "category.more_services_title",
        "Заголовок услуг без своей страницы",
        "Ещё услуги",
        "Страница категории, под карточками услуг",
    ),
    TextDef("category.photos_title", "Заголовок фотографий", "Фотографии", "Страница категории, блок фото"),
    TextDef("category.other_title", "Заголовок других категорий", "Другие категории", "Страница категории, внизу"),
    TextDef(
        "category.cta_title",
        "Призыв связаться: заголовок",
        "Забронировать или задать вопрос",
        "Страница категории, карточка с кнопками связи внизу",
    ),
    TextDef(
        "category.cta_text",
        "Призыв связаться: текст",
        "Позвоните или напишите — расскажем подробности, подберём программу и удобную дату.",
        "Страница категории, под заголовком карточки с кнопками связи",
        required=False,
    ),
    # Мероприятия
    TextDef("events.upcoming_title", "Заголовок предстоящих", "Предстоящие", "Мероприятия, список предстоящих"),
    TextDef("events.past_title", "Заголовок прошедших", "Прошедшие", "Мероприятия, список прошедших"),
    TextDef(
        "events.empty_title",
        "Нет мероприятий: заголовок",
        "Скоро анонсируем новые мероприятия",
        "Мероприятия, карточка вместо списка, когда предстоящих нет",
    ),
    TextDef(
        "events.empty_vk_text",
        "Нет мероприятий: про группу ВКонтакте",
        "Анонсы первыми появляются в нашей группе ВКонтакте.",
        "Мероприятия, та же карточка; только если в настройках указана ссылка на ВКонтакте",
        required=False,
    ),
    TextDef(
        "events.empty_text",
        "Нет мероприятий: текст",
        "А программу для своей компании можно заказать в любое время.",
        "Мероприятия, та же карточка, после фразы про ВКонтакте",
        required=False,
    ),
    TextDef("events.cta_title", "Призыв заказать событие: заголовок", "Своё событие в Т-Парке", "Мероприятия, карточка внизу"),
    TextDef(
        "events.cta_text",
        "Призыв заказать событие: текст",
        "Корпоратив, день рождения, выпускной или выезд класса — придумаем программу и всё организуем.",
        "Мероприятия, под заголовком карточки внизу",
        required=False,
    ),
    # Мероприятие
    TextDef(
        "event.upcoming_title",
        "Лента под прошедшим мероприятием",
        "Ближайшие мероприятия",
        "Страница прошедшего мероприятия, заголовок ленты внизу",
    ),
    TextDef(
        "event.other_title",
        "Лента под предстоящим мероприятием",
        "Другие мероприятия",
        "Страница предстоящего мероприятия, заголовок ленты внизу",
    ),
    # О нас
    TextDef(
        "about.formats_title",
        "Заголовок форматов парка",
        "Приключение и тренинг в одном событии",
        "О нас, над карточками форматов",
    ),
    TextDef("about.founder_eyebrow", "Надзаголовок блока основателя", "Основатель", "О нас, зелёная надпись над именем"),
    TextDef("about.nearby_title", "Заголовок «Что рядом»", "Что рядом", "О нас, блок с текстом «Что рядом» из настроек"),
    TextDef(
        "about.safety_title",
        "Плашка безопасности: заголовок",
        "Правила безопасности",
        "О нас, плашка-ссылка на инфо-страницу с правилами",
    ),
    TextDef(
        "about.safety_text",
        "Плашка безопасности: текст",
        "Что важно знать перед приездом в парк",
        "О нас, под заголовком плашки",
        required=False,
    ),
    TextDef("about.partners_title", "Заголовок партнёров", "Партнёры", "О нас, логотипы партнёров"),
    TextDef("about.cta_title", "Призыв связаться: заголовок", "Приезжайте в Т-Парк", "О нас, карточка с кнопками связи внизу"),
    TextDef(
        "about.cta_text",
        "Призыв связаться: текст",
        "Расскажем о программах и подберём формат для вас, семьи или команды.",
        "О нас, под заголовком карточки с кнопками связи",
        required=False,
    ),
    # Контакты
    TextDef(
        "contacts.lead",
        "Подзаголовок страницы",
        "Звоните или пишите — расскажем о программах и поможем выбрать формат.",
        "Контакты, под заголовком страницы",
        required=False,
    ),
    TextDef("contacts.phones_title", "Подпись телефонов", "Телефоны", "Контакты, карточка связи"),
    TextDef("contacts.write_title", "Подпись мессенджеров", "Написать", "Контакты, карточка связи"),
    TextDef("contacts.hours_title", "Подпись часов работы", "Часы работы", "Контакты, карточка связи"),
    TextDef("contacts.find_title", "Заголовок блока с картой", "Как нас найти", "Контакты, блок с адресом и картой"),
    # Отзывы
    TextDef(
        "reviews.lead",
        "Подзаголовок страницы",
        "Что говорят гости Т-Парка",
        "Отзывы, под заголовком страницы; после него — число отзывов",
    ),
    TextDef("reviews.empty", "Нет отзывов", "Отзывов пока нет.", "Отзывы, вместо списка, пока отзывов нет"),
    # Галерея
    TextDef(
        "gallery.lead",
        "Подзаголовок страницы",
        "Фото из жизни парка",
        "Галерея, под заголовком страницы; после него — число фото",
    ),
    TextDef("gallery.empty", "Нет фото", "Фото скоро появятся.", "Галерея, вместо сетки, пока фото нет"),
    # Общее
    TextDef(
        "common.photo_strip_title",
        "Заголовок полосы фото",
        "Как это выглядит",
        "Главная и «О нас», полоса фото со ссылкой на галерею",
    ),
    TextDef(
        "common.find_us_title",
        "Карточка с адресом: заголовок",
        "Как добраться",
        "Главная и «О нас», зелёная карточка с адресом",
    ),
    TextDef(
        "common.review_cta_title",
        "Просьба об отзыве: заголовок",
        "Уже были у нас?",
        "Контакты и Отзывы, карточка со звездой",
    ),
    TextDef(
        "common.review_cta_text",
        "Просьба об отзыве: текст",
        "Расскажите, как всё прошло: отзыв на Яндекс Картах поможет другим гостям выбрать Т-Парк.",
        "Контакты и Отзывы, под заголовком карточки со звездой",
        required=False,
    ),
    TextDef(
        "common.cookie_text",
        "Баннер cookie",
        "Мы используем cookie и Яндекс Метрику, чтобы сайт работал удобнее.",
        "Все страницы, баннер внизу при первом визите; после текста — ссылка на политику конфиденциальности",
    ),
    # Страница 404
    TextDef("error404.title", "Заголовок", "Кажется, вы сошли с тропы", "Страница «не найдено»"),
    TextDef(
        "error404.text",
        "Текст",
        "Такой страницы нет: возможно, она переехала или в ссылке опечатка. Вернём вас на маршрут.",
        "Страница «не найдено», под заголовком",
        required=False,
    ),
    TextDef("error404.links_title", "Подпись над ссылками", "Или загляните сюда", "Страница «не найдено», над ссылками на разделы"),
    TextDef(
        "error404.call_text",
        "Текст перед телефоном",
        "Не нашли, что искали? Позвоните — подскажем:",
        "Страница «не найдено», внизу; после текста — номер телефона",
    ),
)

BY_KEY = {item.key: item for item in TEXTS}


def sync_texts(site_text_model, historical_model) -> int:
    """Приводит записи к реестру: создаёт недостающие (с начальной версией в истории), обновляет у
    существующих название, страницу и порядок. Текст существующих не трогает — правки из админки сохраняются.

    Модели передаются явно: из миграции — исторические (`apps.get_model`), из кода — `SiteText` и
    `SiteText.history.model`. Возвращает число созданных записей.
    """
    existing = {obj.key: obj for obj in site_text_model.objects.all()}
    created = []
    for order, item in enumerate(TEXTS):
        obj = existing.get(item.key)
        if obj is None:
            created.append(
                site_text_model(key=item.key, page=item.page, label=item.label, text=item.default, order=order)
            )
        elif (obj.label, obj.page, obj.order) != (item.label, item.page, order):
            site_text_model.objects.filter(pk=obj.pk).update(label=item.label, page=item.page, order=order)
    if not created:
        return 0
    site_text_model.objects.bulk_create(created)
    now = timezone.now()
    new_rows = site_text_model.objects.filter(key__in=[obj.key for obj in created])
    historical_model.objects.bulk_create(
        historical_model(
            id=obj.pk,
            key=obj.key,
            page=obj.page,
            label=obj.label,
            text=obj.text,
            order=obj.order,
            updated_at=obj.updated_at,
            history_date=now,
            history_type="+",
            history_change_reason="Начальный текст",
        )
        for obj in new_rows
    )
    return len(created)
```

Строки длиннее 120 символов ruff format перенесёт сам — после шага 5 прогнать `uv run ruff format apps/texts`.

- [ ] **Step 4: Data-миграция**

`src/apps/texts/migrations/0002_initial_texts.py`:

```python
from django.db import migrations

from apps.texts.registry import sync_texts


def forwards(apps, schema_editor):
    sync_texts(apps.get_model("texts", "SiteText"), apps.get_model("texts", "HistoricalSiteText"))


class Migration(migrations.Migration):
    dependencies = [("texts", "0001_initial")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
```

- [ ] **Step 5: Прогнать**

```bash
uv run ruff format apps/texts && uv run pytest tests/test_texts.py -v
```

Expected: все тесты PASS (тестовая БД создаётся миграциями — записи от `0002` есть в каждом нетранзакционном тесте). Тесты задачи 1 используют свой ключ `test.sample` и не пересекаются с реестром.

- [ ] **Step 6: Коммит**

```bash
uv run pytest && uv run ruff check .
cd .. && git add src/apps/texts src/tests/test_texts.py
git commit -m "Тексты сайта: реестр из 48 текстов и миграция с текущими формулировками и начальной версией в истории

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Тег `{% text %}` и контекст-процессор

**Files:**
- Create: `src/apps/texts/context_processors.py`, `src/apps/texts/templatetags/__init__.py`, `src/apps/texts/templatetags/site_texts.py`
- Modify: `src/config/settings.py` (`TEMPLATES[0]["OPTIONS"]["context_processors"]`)
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Consumes: `BY_KEY` (задача 2), `nobr` из `apps.core.templatetags.site_tags`.
- Produces: контекстная переменная `site_texts` (ленивый `dict[str, str]`); тег `{% load site_texts %}` → `{% text "ключ" %}` выводит экранированный текст через `nobr`; `{% text "ключ" as имя %}` кладёт в контекст обычную строку (выводить с `|nobr`, нужен `{% load site_tags %}`). Неизвестный или не-литеральный ключ — `TemplateSyntaxError` при компиляции.

- [ ] **Step 1: Падающие тесты**

Добавить в `src/tests/test_texts.py`:

```python
from django.db import connection
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.texts.context_processors import site_texts


def _render(source: str, with_db: bool = True) -> str:
    context = site_texts(RequestFactory().get("/")) if with_db else {}
    return Template("{% load site_texts %}" + source).render(Context(context))


def test_tag_outputs_db_text_with_nobr():
    SiteText.objects.filter(key="home.cta_title").update(text="Ждём в Т-Парке")
    assert _render('{% text "home.cta_title" %}') == 'Ждём в <span class="whitespace-nowrap">Т-Парке</span>'


def test_tag_escapes_html():
    SiteText.objects.filter(key="home.cta_title").update(text='<b>Жирно</b> & "кавычки"')
    assert _render('{% text "home.cta_title" %}') == "&lt;b&gt;Жирно&lt;/b&gt; &amp; &quot;кавычки&quot;"


def test_tag_falls_back_to_default_without_row_or_context():
    SiteText.objects.all().delete()
    default = BY_KEY["home.events_title"].default
    assert _render('{% text "home.events_title" %}') == default
    with CaptureQueriesContext(connection) as queries:
        assert _render('{% text "home.events_title" %}', with_db=False) == default
    assert len(queries) == 0


def test_empty_required_text_falls_back_to_default():
    SiteText.objects.filter(key="home.events_title").update(text="")
    assert _render('{% text "home.events_title" %}') == "Ближайшие мероприятия"


def test_empty_optional_text_hides_block():
    SiteText.objects.filter(key="service.booking_hint").update(text="")
    source = '{% text "service.booking_hint" as hint %}{% if hint %}<p>{{ hint }}</p>{% endif %}'
    assert _render(source) == ""


def test_as_stores_plain_string():
    assert _render('{% text "home.cta_title" as title %}[{{ title }}]') == "[Приезжайте в Т-Парк]"


@pytest.mark.parametrize("source", ['{% text "nope.missing" %}', "{% text home.title %}", '{% text "home.title" as %}'])
def test_bad_tag_fails_at_compile_time(source):
    with pytest.raises(TemplateSyntaxError):
        Template("{% load site_texts %}" + source)


def test_all_texts_loaded_with_one_query():
    with CaptureQueriesContext(connection) as queries:
        _render('{% text "home.title" %}{% text "home.events_title" %}{% text "home.reviews_title" %}')
    assert len([q for q in queries if "texts_sitetext" in q["sql"]]) == 1
```

- [ ] **Step 2: Запустить — падает**

Run: `uv run pytest tests/test_texts.py -k "tag or text or query"`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.texts.context_processors'`.

- [ ] **Step 3: Контекст-процессор**

`src/apps/texts/context_processors.py`:

```python
from django.utils.functional import SimpleLazyObject

from apps.texts.models import SiteText


def site_texts(request):
    """Все тексты сайта одним запросом — только если страница выводит хотя бы один (`{% text %}`)."""
    return {"site_texts": SimpleLazyObject(lambda: dict(SiteText.objects.values_list("key", "text")))}
```

В `src/config/settings.py` в список `context_processors` после `"apps.catalog.context_processors.menu",`:

```python
                "apps.texts.context_processors.site_texts",
```

- [ ] **Step 4: Тег**

`src/apps/texts/templatetags/__init__.py` — пустой.

`src/apps/texts/templatetags/site_texts.py`:

```python
from django import template

from apps.core.templatetags.site_tags import nobr
from apps.texts.registry import BY_KEY

register = template.Library()

USAGE = 'Использование: {% text "ключ" %} или {% text "ключ" as переменная %}'


class TextNode(template.Node):
    def __init__(self, key: str, var_name: str | None):
        self.key, self.var_name = key, var_name

    def render(self, context) -> str:
        item = BY_KEY[self.key]
        texts = context.get("site_texts")  # нет при рендере без контекст-процессоров — тогда текст по умолчанию
        value = texts.get(self.key, item.default) if texts is not None else item.default
        if not value and item.required:
            value = item.default
        if self.var_name:
            context[self.var_name] = value
            return ""
        return nobr(value)


@register.tag("text")
def do_text(parser, token):
    """Текст сайта из «Текстов сайта» (apps/texts/registry.py): ключ проверяется при компиляции шаблона."""
    bits = token.split_contents()
    if len(bits) == 2:
        var_name = None
    elif len(bits) == 4 and bits[2] == "as":
        var_name = bits[3]
    else:
        raise template.TemplateSyntaxError(USAGE)
    raw = bits[1]
    if len(raw) < 2 or raw[0] != raw[-1] or raw[0] not in "\"'":
        raise template.TemplateSyntaxError(f"Ключ текста — строка в кавычках. {USAGE}")
    key = raw[1:-1]
    if key not in BY_KEY:
        raise template.TemplateSyntaxError(f"Неизвестный текст сайта «{key}»: добавьте его в apps/texts/registry.py")
    return TextNode(key, var_name)
```

- [ ] **Step 5: Прогнать**

Run: `uv run pytest tests/test_texts.py -v`
Expected: все PASS.

- [ ] **Step 6: Коммит**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
cd .. && git add src/apps/texts src/config/settings.py src/tests/test_texts.py
git commit -m "Тексты сайта: тег {% text %} и загрузка всех текстов одним запросом

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Админка «Тексты сайта»

**Files:**
- Modify: `src/apps/texts/admin.py`, `src/config/settings.py` (`UNFOLD["SIDEBAR"]`)
- Create: `src/templates/admin/texts/list_before.html`, `src/templates/simple_history/object_history_list.html`
- Maybe modify: `src/locale/ru/LC_MESSAGES/django.po`, `django.mo`
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Consumes: `SiteText`, `BY_KEY`, `Page`.
- Produces: changelist `admin:texts_sitetext_changelist` с фильтром `?page__exact=<Page>` (на него ссылается задача 6).

- [ ] **Step 1: Падающие тесты**

Добавить в `src/tests/test_texts.py`:

```python
def _change_url(key: str) -> str:
    return reverse("admin:texts_sitetext_change", args=[SiteText.objects.get(key=key).pk])


def test_change_form_shows_where_and_default(admin_client):
    html = admin_client.get(_change_url("service.booking_hint")).content.decode()
    assert "Страница услуги, под ценой и кнопками связи" in html
    assert "Бронируйте заранее — в тёплый сезон даты разбирают быстро." in html
    assert "Пусто — блок на сайте скрыт" in html


def test_required_text_cannot_be_emptied(admin_client):
    response = admin_client.post(_change_url("home.events_title"), {"text": "  "})
    assert response.status_code == 200
    assert SiteText.objects.get(key="home.events_title").text == "Ближайшие мероприятия"


def test_optional_text_can_be_emptied_and_is_stripped(admin_client):
    assert admin_client.post(_change_url("service.booking_hint"), {"text": ""}).status_code == 302
    assert SiteText.objects.get(key="service.booking_hint").text == ""
    admin_client.post(_change_url("service.booking_hint"), {"text": "  Звоните заранее.\n"})
    assert SiteText.objects.get(key="service.booking_hint").text == "Звоните заранее."


def test_no_add_or_delete(admin_client):
    model_admin = admin.site._registry[SiteText]
    request = RequestFactory().get("/")
    request.user = User.objects.get(is_superuser=True)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_changelist_filters_by_page_and_links_settings(admin_client):
    html = admin_client.get(reverse("admin:texts_sitetext_changelist") + "?page__exact=gallery").content.decode()
    assert "Фото скоро появятся." in html and "Отзывов пока нет." not in html
    assert reverse("admin:core_sitesettings_changelist") in html


def test_initial_version_shows_dash_instead_of_none(admin_client):
    url = reverse("admin:texts_sitetext_history", args=[SiteText.objects.get(key="gallery.empty").pk])
    html = admin_client.get(url).content.decode()
    assert "Начальный текст" in html
    assert not re.search(r"<td[^>]*>\s*None\s*</td>", html)


def test_history_page_is_russian(admin_client):
    url = reverse("admin:texts_sitetext_history", args=[SiteText.objects.get(key="gallery.empty").pk])
    html = admin_client.get(url).content.decode()
    for english in ("Changed by", "Date/time", "Change reason", "Changes"):
        assert english not in html, english
```

И импорты в начало файла: `import re`, `from django.contrib import admin`, `from django.contrib.auth.models import User`.

- [ ] **Step 2: Запустить — падает**

Run: `uv run pytest tests/test_texts.py -k "change_form or emptied or add_or_delete or changelist or none or russian"`
Expected: FAIL (нет подсказок в форме, есть кнопка добавления, нет фильтра и т. д.).

- [ ] **Step 3: Админка**

Заменить `src/apps/texts/admin.py`:

```python
from django import forms
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_utils import SiteModelAdmin
from apps.texts.models import SiteText
from apps.texts.registry import BY_KEY


class SiteTextForm(forms.ModelForm):
    class Meta:
        model = SiteText
        fields = ["text"]

    def clean_text(self):
        text = self.cleaned_data["text"]  # форма уже обрезала пробелы и переводы строк по краям
        item = BY_KEY.get(self.instance.key)
        if not text and item and item.required:
            raise forms.ValidationError("Этот текст обязателен: без него на сайте останется пустой заголовок.")
        return text


@admin.register(SiteText)
class SiteTextAdmin(SimpleHistoryAdmin, SiteModelAdmin):
    form = SiteTextForm
    list_display = ["label", "page", "short_text", "updated_at"]
    list_filter = ["page"]
    search_fields = ["label", "text", "key"]
    fields = ["label", "page", "where", "text", "default_text", "key"]
    readonly_fields = ["label", "page", "where", "default_text", "key"]
    list_before_template = "admin/texts/list_before.html"

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 80 else obj.text[:79] + "…"

    @admin.display(description="Где на сайте")
    def where(self, obj):
        item = BY_KEY.get(obj.key)
        return item.where if item else "—"

    @admin.display(description="Текст по умолчанию")
    def default_text(self, obj):
        item = BY_KEY.get(obj.key)
        return item.default if item else "—"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        item = BY_KEY.get(obj.key) if obj else None
        text = form.base_fields["text"]
        text.widget.attrs["rows"] = 3
        text.help_text = "Обязательный текст." if item is None or item.required else "Пусто — блок на сайте скрыт."
        return form

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 4: Подсказка над списком**

`src/templates/admin/texts/list_before.html`:

```html
<p class="mb-4 text-sm text-base-500">Короткие фразы и заголовки блоков витрины. Вступления и длинные тексты страниц («О нас», биография, «Что рядом», текст контактов) — в <a href="{% url 'admin:core_sitesettings_changelist' %}" class="text-primary-600 underline">«Настройках сайта»</a>.</p>
```

- [ ] **Step 5: «—» вместо «None» у версии без автора**

```bash
cp .venv/lib/python3.14/site-packages/unfold/contrib/simple_history/templates/simple_history/object_history_list.html templates/simple_history/object_history_list.html
```

В скопированном файле: первой строкой добавить
`{# Копия шаблона unfold.contrib.simple_history (django-unfold 0.108): у начальной версии нет автора — «—» вместо «None». При обновлении Unfold сверить с оригиналом. #}`
и в ветке `{% else %}` колонки автора заменить `{{ record.history_user }}` на `{{ record.history_user|default:"—" }}`.

- [ ] **Step 6: Пункт меню**

В `src/config/settings.py`, группа «Сайт» → `items`, после «Настройки сайта»:

```python
                    _nav("Тексты сайта", "text_fields", "admin:texts_sitetext_changelist"),
```

- [ ] **Step 7: Прогнать и при необходимости дописать перевод**

Run: `uv run pytest tests/test_texts.py -v`

Если падает только `test_history_page_is_russian` — дописать в `src/locale/ru/LC_MESSAGES/django.po` недостающие строки из списка (только те, что тест показал):

```po
msgid "Date/time"
msgstr "Дата и время"

msgid "Changed by"
msgstr "Автор"

msgid "Change reason"
msgstr "Причина изменения"

msgid "Changes"
msgstr "Изменения"
```

затем `uv run manage.py compilemessages -l ru` (нужен gettext; `.mo` коммитится) и повторить прогон.
Expected: все PASS.

- [ ] **Step 8: Проверить вручную в браузере**

```bash
uv run manage.py migrate && uv run manage.py tailwind runserver
```

Открыть `/admin/texts/sitetext/`: список, фильтр «Страница», поиск; открыть «Подсказка под кнопками связи», изменить, сохранить, нажать «История», открыть начальную версию, «Вернуть». Убедиться, что тексты интерфейса истории — по-русски.

- [ ] **Step 9: Коммит**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
cd .. && git add src/apps/texts src/config/settings.py src/templates/admin/texts src/templates/simple_history src/tests/test_texts.py src/locale
git commit -m "Тексты сайта: админка с подсказками, обязательными текстами и историей версий

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Перевод шаблонов на `{% text %}`

**Files:**
- Modify: `src/templates/catalog/home.html`, `catalog/service.html`, `catalog/category.html`, `content/events.html`, `content/event.html`, `content/about.html`, `content/contacts.html`, `content/reviews.html`, `content/gallery.html`, `content/partials/photo_strip.html`, `partials/find_us_card.html`, `partials/review_cta.html`, `partials/cookie_notice.html`, `404.html`
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Consumes: тег `{% text %}` (задача 3), `TEXTS` (задача 2).

Правило загрузки: в шаблоне с `{% extends %}` `{% load %}` ставится второй строкой (если там уже `{% load site_tags %}` или `{% load static site_tags %}` — дописать `site_texts`); где используется `as` + `|nobr`, нужны оба: `{% load site_tags site_texts %}`. В партиале без `{% extends %}` — первой строкой. Если в партиале первая строка — `{% comment %}`-блок, `{% load %}` ставится сразу после `{% endcomment %}`.

- [ ] **Step 1: Падающие тесты**

Добавить в `src/tests/test_texts.py`:

```python
from pathlib import Path

from django.conf import settings

from apps.catalog.models import Service
from apps.core.models import Phone, SiteSettings

TEXT_TAG = re.compile(r"""\{%\s*text\s+["']([\w.]+)["']""")


def test_registry_matches_templates():
    used = set()
    for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
        used |= set(TEXT_TAG.findall(path.read_text(encoding="utf-8")))
    assert used == set(BY_KEY)


def _service_page(client) -> str:
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    service = Service.objects.create(name="Сплав", price="2000", has_page=True)
    return client.get(service.get_absolute_url()).content.decode()


def test_edited_text_shows_on_site_and_empty_hides_block(client):
    assert "Бронируйте заранее" in _service_page(client)
    SiteText.objects.filter(key="service.booking_hint").update(text="Звоните заранее.")
    html = client.get(Service.objects.get().get_absolute_url()).content.decode()
    assert "Звоните заранее." in html and "Бронируйте" not in html
    SiteText.objects.filter(key="service.booking_hint").update(text="")
    html = client.get(Service.objects.get().get_absolute_url()).content.decode()
    assert "Звоните заранее." not in html and 'text-sm text-ink/65"></p>' not in html


def test_pages_render_defaults_when_table_is_empty(client):
    SiteText.objects.all().delete()
    assert "Кажется, вы сошли с тропы" in client.get("/no-such-page/").content.decode()
    assert "Скоро анонсируем новые мероприятия" in client.get("/events/").content.decode()
```

- [ ] **Step 2: Запустить — падает**

Run: `uv run pytest tests/test_texts.py -k "templates or site or empty"`
Expected: FAIL — `test_registry_matches_templates`: `used` пуст; `test_edited_text_shows_on_site…`: новый текст не появился.

- [ ] **Step 3: `catalog/home.html`** (второй строкой — `{% load site_tags site_texts %}`)

| Строка | Было | Стало |
|---|---|---|
| 9 | `<h1 class="page-title md:text-6xl"><span class="whitespace-nowrap">Тренинг-парк</span> Дмитрия Сергеева</h1>` | `<h1 class="page-title md:text-6xl">{% text "home.title" %}</h1>` |
| 39 | `<p class="mx-auto max-w-6xl px-4 py-16 text-ink/65">Скоро здесь появятся наши услуги.</p>` | `{% text "home.services_empty" as services_empty %}{% if services_empty %}<p class="mx-auto max-w-6xl px-4 py-16 text-ink/65">{{ services_empty\|nobr }}</p>{% endif %}` |
| 46 | `…md:text-3xl">Ближайшие мероприятия</h2>` | `…md:text-3xl">{% text "home.events_title" %}</h2>` |
| 58 | `…md:text-3xl">Отзывы гостей</h2>` | `…md:text-3xl">{% text "home.reviews_title" %}</h2>` |
| 91 | `<h2 class="text-2xl font-bold md:text-3xl">Приезжайте в <span class="whitespace-nowrap">Т-Парк</span></h2>` | `<h2 class="text-2xl font-bold md:text-3xl">{% text "home.cta_title" %}</h2>` |
| 92 | `<p class="mt-2 text-ink/75">Расскажем о программах и подберём формат для вас, семьи или команды.</p>` | `{% text "home.cta_text" as cta_text %}{% if cta_text %}<p class="mt-2 text-ink/75">{{ cta_text\|nobr }}</p>{% endif %}` |

(`\|` в таблице — это `|`.)

- [ ] **Step 4: `catalog/service.html`** (второй строкой — `{% load site_tags site_texts %}`)

Строка 24:
`<p class="mt-4 text-sm text-ink/65">Бронируйте заранее — в тёплый сезон даты разбирают быстро.</p>` →
`{% text "service.booking_hint" as booking_hint %}{% if booking_hint %}<p class="mt-4 text-sm text-ink/65">{{ booking_hint|nobr }}</p>{% endif %}`

- [ ] **Step 5: `catalog/category.html`** (второй строкой — `{% load site_texts %}`)

- 24: `>Услуги и цены</h2>` → `>{% text "category.services_title" %}</h2>`
- 31: `>Ещё услуги</h3>` → `>{% text "category.more_services_title" %}</h3>`
- 41: `>Фотографии</h2>` → `>{% text "category.photos_title" %}</h2>`
- 48: `>Другие категории</h2>` → `>{% text "category.other_title" %}</h2>`
- 60: вся строка →
  `{% text "category.cta_title" as cta_title %}{% text "category.cta_text" as cta_text %}<div class="pt-10 md:pt-16">{% include "partials/cta_card.html" with title=cta_title text=cta_text %}</div>`
  (`cta_card.html` сам применяет `|nobr` и скрывает пустой `text`.)

- [ ] **Step 6: `content/events.html`** (строка 2 → `{% load static site_tags site_texts %}`)

- 39: `<p class="text-xl font-bold">Скоро анонсируем новые мероприятия</p>` → `<p class="text-xl font-bold">{% text "events.empty_title" %}</p>`
- 40: вся строка →
  ```django
      {% text "events.empty_vk_text" as empty_vk %}{% text "events.empty_text" as empty_text %}
      {% if site.vk_url and empty_vk or empty_text %}<p class="mt-2 text-ink/75">{% if site.vk_url and empty_vk %}{{ empty_vk|nobr }} {% endif %}{{ empty_text|nobr }}</p>{% endif %}
  ```
- 52: `>Предстоящие</h2>` → `>{% text "events.upcoming_title" %}</h2>`
- 62: `>Прошедшие</h2>` → `>{% text "events.past_title" %}</h2>`
- 76: `{% include "partials/cta_card.html" with title="Своё событие в Т-Парке" text="…" %}` →
  `{% text "events.cta_title" as cta_title %}{% text "events.cta_text" as cta_text %}{% include "partials/cta_card.html" with title=cta_title text=cta_text %}`

- [ ] **Step 7: `content/event.html`** (строка 2 → `{% load site_tags site_texts %}`)

- 61: `{% if event.is_past %}Ближайшие мероприятия{% else %}Другие мероприятия{% endif %}` → `{% if event.is_past %}{% text "event.upcoming_title" %}{% else %}{% text "event.other_title" %}{% endif %}`

- [ ] **Step 8: `content/about.html`** (строка 2 → `{% load site_tags site_texts %}`)

- 21: `>Приключение и тренинг в одном событии</h2>` → `>{% text "about.formats_title" %}</h2>`
- 43: `<h2 class="eyebrow">Основатель</h2>` → `<h2 class="eyebrow">{% text "about.founder_eyebrow" %}</h2>`
- 70: `<h2 class="mb-3 text-2xl font-bold">Что рядом</h2>` → `<h2 class="mb-3 text-2xl font-bold">{% text "about.nearby_title" %}</h2>`
- 75: `<p class="text-xl font-bold">Правила безопасности</p>` → `<p class="text-xl font-bold">{% text "about.safety_title" %}</p>`
- 76: `<p class="mt-1 text-sm text-ink/75">Что важно знать перед приездом в парк</p>` → `{% text "about.safety_text" as safety_text %}{% if safety_text %}<p class="mt-1 text-sm text-ink/75">{{ safety_text|nobr }}</p>{% endif %}`
- 91: `>Партнёры</h2>` → `>{% text "about.partners_title" %}</h2>`
- 105: include `cta_card` → `{% text "about.cta_title" as cta_title %}{% text "about.cta_text" as cta_text %}{% include "partials/cta_card.html" with title=cta_title text=cta_text %}`

- [ ] **Step 9: `content/contacts.html`** (второй строкой — `{% load site_tags site_texts %}`)

- 7: `<p class="page-lead">Звоните или пишите — расскажем о программах и поможем выбрать формат.</p>` → `{% text "contacts.lead" as lead %}{% if lead %}<p class="page-lead">{{ lead|nobr }}</p>{% endif %}`
- 13: `>Телефоны</h2>` → `>{% text "contacts.phones_title" %}</h2>`
- 24: `>Написать</h2>` → `>{% text "contacts.write_title" %}</h2>`
- 36: `>Часы работы</h2>` → `>{% text "contacts.hours_title" %}</h2>`
- 54: `>Как нас найти</h2>` → `>{% text "contacts.find_title" %}</h2>`

- [ ] **Step 10: `content/reviews.html`, `content/gallery.html`** (строка 2 → `{% load site_tags site_texts %}` в обоих)

- reviews 9: `<p class="page-lead">Что говорят гости <span class="whitespace-nowrap">Т-Парка</span>{% if reviews %}` → `<p class="page-lead">{% text "reviews.lead" %}{% if reviews %}` (хвост строки без изменений)
- reviews 26: `>Отзывов пока нет.</p>` → `>{% text "reviews.empty" %}</p>`
- gallery 10: `<p class="page-lead">Фото из жизни парка{% if photos %}` → `<p class="page-lead">{% text "gallery.lead" %}{% if photos %}`
- gallery 42: `>Фото скоро появятся.</p>` → `>{% text "gallery.empty" %}</p>`

- [ ] **Step 11: Партиалы**

- `content/partials/photo_strip.html`: строка 1 → `{% load site_tags site_texts %}`; строка 4 `>Как это выглядит</h2>` → `>{% text "common.photo_strip_title" %}</h2>`
- `partials/find_us_card.html`: новая первая строка `{% load site_texts %}`; `>Как добраться</h2>` → `>{% text "common.find_us_title" %}</h2>`
- `partials/review_cta.html`: новая первая строка `{% load site_tags site_texts %}`;
  `<p class="text-xl font-bold">Уже были у нас?</p>` → `<p class="text-xl font-bold">{% text "common.review_cta_title" %}</p>`;
  `<p class="mt-1 text-ink/75">Расскажите, как всё прошло: … выбрать <span class="whitespace-nowrap">Т-Парк</span>.</p>` → `{% text "common.review_cta_text" as review_text %}{% if review_text %}<p class="mt-1 text-ink/75">{{ review_text|nobr }}</p>{% endif %}`
- `partials/cookie_notice.html`: после `{% endcomment %}` — строка `{% load site_texts %}`; строка 16 `      Мы используем cookie и Яндекс Метрику, чтобы сайт работал удобнее.` → `      {% text "common.cookie_text" %}`

- [ ] **Step 12: `404.html`** (второй строкой — `{% load site_tags site_texts %}`)

- 10: `>Кажется, вы сошли с тропы</h1>` → `>{% text "error404.title" %}</h1>`
- 11: `<p class="mx-auto mt-3 max-w-xl text-lg text-ink/75">Такой страницы нет: …</p>` → `{% text "error404.text" as error_text %}{% if error_text %}<p class="mx-auto mt-3 max-w-xl text-lg text-ink/75">{{ error_text|nobr }}</p>{% endif %}`
- 13: `>Или загляните сюда</p>` → `>{% text "error404.links_title" %}</p>`
- 15: `Не нашли, что искали? Позвоните — подскажем: <a` → `{% text "error404.call_text" %} <a`

- [ ] **Step 13: Прогнать всё**

```bash
uv run pytest
uv run manage.py tailwind build && uv run --group e2e pytest tests/e2e -m e2e
```

Expected: всё PASS — в том числе `test_server_error_page_renders_without_context` (`500.html` не тронута и рендерится без контекста) и существующие проверки фраз в `tests/test_pages.py`, `tests/test_pages_home.py`, `tests/test_events.py` (например, `'Приезжайте в <span class="whitespace-nowrap">Т-Парк</span>' in html` — `nobr` даёт ту же разметку). Если какой-то старый тест падает — сравнить разметку до и после: перенос не должен менять HTML, кроме удалённых литералов.

- [ ] **Step 14: Проверить глазами**

На запущенном `runserver` открыть `/`, `/about/`, `/events/`, `/contacts/`, `/reviews/`, `/gallery/`, страницу категории, услуги и мероприятия, `/no-such-page/` — тексты на месте, «Т-Парк» не переносится. Поменять в админке «Подсказка под кнопками связи» — изменение видно на странице услуги.

- [ ] **Step 15: Коммит**

```bash
uv run ruff check . && cd .. && git add src/templates src/tests/test_texts.py
git commit -m "Тексты сайта: 48 текстов витрины выводятся из «Текстов сайта»

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Подсказки и переименование вкладки в «Настройках сайта»

**Files:**
- Create: `src/apps/texts/hints.py`
- Modify: `src/apps/core/admin.py:90-110` (`SiteSettingsAdmin.fieldsets`)
- Test: `src/tests/test_texts.py`

**Interfaces:**
- Consumes: `Page`; URL `admin:texts_sitetext_changelist` с `?page__exact=` (задача 4).
- Produces: `texts_hint(*pages: Page) -> str` (ленивая HTML-строка для `description` вкладки).

- [ ] **Step 1: Падающий тест**

```python
def test_settings_tabs_link_to_texts(admin_client):
    html = admin_client.get(reverse("admin:core_sitesettings_change", args=[1])).content.decode()
    texts_url = reverse("admin:texts_sitetext_changelist")
    for page in ("home", "events", "contacts", "about"):
        assert f"{texts_url}?page__exact={page}" in html, page
    assert "Мероприятия и контакты" in html
    assert "Форматы и цифры основателя" in html
```

- [ ] **Step 2: Запустить — падает**

Run: `uv run pytest tests/test_texts.py::test_settings_tabs_link_to_texts`
Expected: FAIL — ссылок нет.

- [ ] **Step 3: `src/apps/texts/hints.py`**

```python
from django.urls import reverse
from django.utils.functional import lazy
from django.utils.html import format_html, format_html_join

from apps.texts.registry import Page


def _texts_hint(*pages: Page) -> str:
    url = reverse("admin:texts_sitetext_changelist")
    links = format_html_join(
        ", ",
        '<a href="{}?page__exact={}" class="text-primary-600 underline">{}</a>',
        ((url, page.value, page.label) for page in pages),
    )
    return format_html("Заголовки блоков и короткие фразы страницы — в «Текстах сайта»: {}.", links)


# Описание вкладки настроек: рендерится при показе формы (URL-ы к этому моменту уже загружены).
texts_hint = lazy(_texts_hint, str)
```

- [ ] **Step 4: `src/apps/core/admin.py`**

Импорты: `from django.utils.text import format_lazy` и `from apps.texts.hints import texts_hint`, `from apps.texts.registry import Page`.

В `SiteSettingsAdmin.fieldsets`:

```python
        ("Главная", {"classes": ["tab"], "description": texts_hint(Page.HOME), "fields": ["home_intro", "home_show_events"]}),
        (
            "Мероприятия и контакты",
            {
                "classes": ["tab"],
                "description": texts_hint(Page.EVENTS, Page.CONTACTS),
                "fields": ["events_intro", "contacts_text"],
            },
        ),
```

и у вкладки «О нас» `description`:

```python
                "description": format_lazy(
                    "{} {}",
                    "Форматы и цифры основателя — на вкладках «Форматы (О нас)» и «Основатель в цифрах (О нас)».",
                    texts_hint(Page.ABOUT),
                ),
```

- [ ] **Step 5: Прогнать**

Run: `uv run pytest tests/test_texts.py tests/test_admin.py -v`
Expected: PASS. Открыть `/admin/core/sitesettings/1/change/` — на трёх вкладках подсказка со ссылками, ссылки открывают список текстов с фильтром.

- [ ] **Step 6: Коммит**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check .
cd .. && git add src/apps/texts/hints.py src/apps/core/admin.py src/tests/test_texts.py
git commit -m "Настройки сайта: вкладка «Мероприятия и контакты» и ссылки на «Тексты сайта»

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Импорт старой базы, документация, финальная проверка

**Files:**
- Modify: `src/apps/core/legacy/runner.py:78`
- Modify: `docs/decisions.md`, `CLAUDE.md`
- Test: `src/tests/legacy/test_import_site.py`

**Interfaces:**
- Consumes: `sync_texts`, `SiteText`.

- [ ] **Step 1: Падающий тест**

Добавить в `src/tests/legacy/test_import_site.py` (модуль транзакционный — `django_db(transaction=True)`, таблицы перед тестом очищены; фикстура `legacy` из `tests/legacy/conftest.py`, импорт — `legacy.run()`):

```python
from apps.texts.models import SiteText
from apps.texts.registry import TEXTS


def test_import_creates_missing_site_texts(legacy):
    SiteText.objects.all().delete()
    legacy.run()
    assert SiteText.objects.count() == len(TEXTS)
    assert SiteText.history.filter(history_type="+").count() == len(TEXTS)
```

Run: `uv run pytest tests/legacy/test_import_site.py -k site_texts`
Expected: FAIL — `0 != 48`.

- [ ] **Step 2: `src/apps/core/legacy/runner.py`**

Импорты: `from apps.texts.models import SiteText`, `from apps.texts.registry import sync_texts`. После `fill_seo_content(SiteSettings, Category)`:

```python
                sync_texts(SiteText, SiteText.history.model)
```

Run: `uv run pytest tests/legacy -v` → PASS.

- [ ] **Step 3: `docs/decisions.md`** — новая строка в конце таблицы решений:

```markdown
| 38 | **Тексты сайта** (`apps/texts`): короткие фразы и заголовки блоков витрины — модель `SiteText`, набор ключей и тексты по умолчанию — в реестре `registry.py`, вывод — тег `{% text %}`; история и возврат версий — `django-simple-history` + `unfold.contrib.simple_history`. Длинные HTML-тексты страниц остаются в `SiteSettings` | Правка формулировок без программиста; реестр не даёт опечаткам в ключах дойти до сайта (ошибка при компиляции шаблона); пустая таблица не ломает страницы |
```

- [ ] **Step 4: `CLAUDE.md`** — в раздел Architecture после пункта `apps/content` добавить:

```markdown
- `apps/texts` — «Тексты сайта»: короткие фразы и заголовки блоков витрины (длинные HTML-тексты страниц — в `SiteSettings`). Набор — реестр `registry.py` (`TEXTS`: ключ `<страница>.<имя>`, название, текст по умолчанию, где на сайте, обязательность), значения — `SiteText`, вывод — `{% load site_texts %}{% text "ключ" %}` (экранирование + `nobr`) или `{% text "ключ" as имя %}` → `{{ имя|nobr }}`; все тексты — одним запросом (контекст-процессор `site_texts`), без записи — текст по умолчанию. Новый текст: строка в реестре + тег в шаблоне + data-миграция с `sync_texts` (тест `test_registry_matches_templates` сверяет реестр с шаблонами). История и «Вернуть» — `django-simple-history`; `templates/simple_history/object_history_list.html` — копия шаблона Unfold («—» вместо «None»), сверять при обновлении Unfold.
```

- [ ] **Step 5: Финальная проверка**

```bash
uv run manage.py makemigrations --check --dry-run
uv run pytest
uv run manage.py tailwind build && uv run --group e2e pytest tests/e2e -m e2e
uv run ruff check . && uv run ruff format --check .
cd .. && uv run --project src pre-commit run --all-files
```

Expected: миграций не требуется; все тесты PASS; линт чистый.

- [ ] **Step 6: Коммит**

```bash
git add src/apps/core/legacy/runner.py src/tests/legacy/test_import_site.py docs/decisions.md CLAUDE.md
git commit -m "Тексты сайта: создание при импорте старой базы, документация

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
