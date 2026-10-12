# Справка в админке — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Страница «Справка» в админке Unfold, вводные над списками со ссылкой на нужный раздел, ссылка «Справка по разделу» в формах, «Быстрый старт» на главной админки и недостающие подсказки у полей.

**Architecture:** Справка — статические шаблоны в git: каркас `templates/admin/help/index.html` и по шаблону на раздел, список разделов — `HELP_SECTIONS` в `apps/core/admin_help.py` (из него строятся оглавление, якоря и проверки). Вводные и ссылки в формах — атрибуты `help_intro`/`help_anchor` у `SiteModelAdmin` и общие `list_before_template`/`change_form_before_template`. Подсказки у полей — `help_text` в моделях (миграции без изменения схемы).

**Tech Stack:** Python 3.14, Django 6.1, django-unfold 0.108, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-12-admin-help-design.md`

## Global Constraints

- Читатель — один человек, не технарь: простой язык, по задачам; «адрес страницы», а не «slug»; «страница не откроется», а не «404».
- Названия кнопок, разделов и полей — в «ёлочках», точно как в админке.
- Без скриншотов и картинок; схемы — текстом/разметкой.
- Ссылки на разделы админки в шаблонах — только `{% url %}`, не захардкоженные пути.
- Вёрстка справки: классы Tailwind, собранные в CSS Unfold, плюс `static/css/admin_help.css` для типографики текста разделов (в CSS Unfold нет `space-y-*`, `list-disc`, `scroll-mt-*`, `border-l-4`, `max-w-prose`). Цвета — переменные Unfold `var(--color-primary-600)`, `var(--color-base-200)`; тёмная тема — селектор `.dark`.
- Комментарии `{# … #}` — только однострочные, длинные — `{% comment %}`.
- Каждое утверждение справки — по коду и шаблонам; факты ниже проверены (`file:line` — в отчёте исследования, перенесены в тексты разделов).
- Python-команды — из `src/`: `cd src && uv run pytest …`.
- Тесты в задачах показаны вместе с нужными импортами; импорты переносить в начало `tests/test_admin_help.py` (ruff, правило isort), а не оставлять посреди файла.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Сотрудник без прав суперпользователя** открывает справку — ссылки на недоступные разделы не должны ронять страницу (только `{% url %}`, без проверок прав в шаблоне): покрыто тестом `test_help_open_for_plain_staff` в задаче 1.
2. **Форма добавления/изменения у админок с нестандартными шаблонами** (пользователи — `auth/user/add_form.html`, тексты — simple-history) должна показывать «Справка по разделу» и не падать: тест `test_every_admin_form_links_to_help` в задаче 5 проходит по всем зарегистрированным админкам.
3. **Тёмная тема и ширина телефона** — текст справки читаем, таблица не вылезает за экран: таблица в обёртке `overflow-x: auto` (задача 1, CSS) + ручная проверка в задаче 8.
4. **Неточные старые подсказки** («Все отзывы» только на странице отзывов; услуга «только внутри категории»; правила безопасности только на «О нас»; полоса фото только на главной и «О нас») — справка и подсказки не должны противоречить друг другу: исправление и тест `test_fixed_hints_match_site` в задаче 7.
5. **Вводная «Текстов сайта» со ссылкой на настройки** после переезда на общий механизм: существующий тест `tests/test_texts.py:164-166` должен остаться зелёным (задача 5).

---

## Файловая структура

| Файл | Что делает |
|---|---|
| `src/apps/core/admin_help.py` (новый) | `HelpSection`, `HELP_SECTIONS`, `HELP_ANCHORS`, view `help_view` |
| `src/config/urls.py` | `path("admin/help/", …, name="admin_help")` до `admin/` |
| `src/config/settings.py` | пункт «Справка» в `UNFOLD["SIDEBAR"]["navigation"]` |
| `src/templates/admin/help/index.html` (новый) | каркас: оглавление + разделы по `HELP_SECTIONS` |
| `src/templates/admin/help/sections/<anchor>.html` (13 новых) | тексты разделов |
| `src/static/css/admin_help.css` (новый) | типографика справки |
| `src/templates/admin/help/list_intro.html`, `form_link.html` (новые) | вводная над списком, ссылка в форме |
| `src/apps/core/admin_utils.py` | `help_intro`, `help_anchor`, шаблоны в `SiteModelAdmin` |
| `src/apps/{catalog,content,core,texts}/admin.py` | `help_intro`/`help_anchor` у каждой админки |
| `src/apps/texts/hints.py` | `texts_intro` (вводная «Текстов сайта» со ссылкой) |
| `src/templates/admin/texts/list_before.html` | удаляется |
| `src/templates/admin/dashboard_help.html` | «Быстрый старт» |
| `src/apps/{catalog,content,core}/models.py` + миграции | `help_text` |
| `src/apps/texts/registry.py` | исправленное «где на сайте» у `common.photo_strip_title` |
| `src/tests/test_admin_help.py` (новый) | тесты справки |
| `CLAUDE.md`, `docs/decisions.md` | правило поддержки, решение |

---

### Task 1: Каркас справки, пункт меню, разделы «Как устроен сайт» и «Почему этого не видно на сайте»

**Files:**
- Create: `src/apps/core/admin_help.py`
- Create: `src/templates/admin/help/index.html`
- Create: `src/templates/admin/help/sections/structure.html`
- Create: `src/templates/admin/help/sections/not-visible.html`
- Create: `src/static/css/admin_help.css`
- Modify: `src/config/urls.py`
- Modify: `src/config/settings.py` (`UNFOLD["SIDEBAR"]["navigation"]`, ~строка 267)
- Test: `src/tests/test_admin_help.py`

**Interfaces:**
- Produces: `apps.core.admin_help.HelpSection(anchor: str, title: str)` с свойством `.template -> str` (`"admin/help/sections/<anchor>.html"`); `HELP_SECTIONS: tuple[HelpSection, ...]`; `HELP_ANCHORS: frozenset[str]`; `help_view(request) -> TemplateResponse`; URL name `admin_help` → `/admin/help/`. Разделы `<section id="<anchor>">` в HTML. Задачи 2–4 дописывают элементы в `HELP_SECTIONS` и шаблоны в `sections/`.

- [ ] **Step 1: Write the failing tests**

`src/tests/test_admin_help.py`:

```python
import re

import pytest
from django.urls import reverse

from apps.core.admin_help import HELP_ANCHORS, HELP_SECTIONS

pytestmark = pytest.mark.django_db


def _help_html(client) -> str:
    response = client.get(reverse("admin_help"))
    assert response.status_code == 200
    return response.content.decode()


def test_help_requires_staff(client, django_user_model):
    url = reverse("admin_help")
    login = reverse("admin:login")
    assert client.get(url).url.startswith(login)
    django_user_model.objects.create_user("guest", password="p")
    client.login(username="guest", password="p")
    assert client.get(url).url.startswith(login)


def test_help_open_for_plain_staff(client, django_user_model):
    django_user_model.objects.create_user("staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    assert "Как устроен сайт" in _help_html(client)


def test_sidebar_links_to_help(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    assert f'href="{reverse("admin_help")}"' in html


def test_toc_points_to_existing_sections(admin_client):
    html = _help_html(admin_client)
    ids = set(re.findall(r'<section id="([\w-]+)"', html))
    assert ids == HELP_ANCHORS
    toc = re.findall(r'href="#([\w-]+)"', html)
    assert set(toc) - {"toc"} == HELP_ANCHORS
    assert [s.anchor for s in HELP_SECTIONS] == list(dict.fromkeys(a for a in toc if a != "toc"))


def test_help_admin_links_open(admin_client):
    html = _help_html(admin_client)
    links = sorted(set(re.findall(r'href="(/admin/[^"#]*)', html)) - {reverse("admin_help")})
    assert links
    for link in links:
        response = admin_client.get(link.replace("&amp;", "&"), follow=True)
        assert response.status_code == 200, link
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && uv run pytest tests/test_admin_help.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.core.admin_help'`.

- [ ] **Step 3: Write `apps/core/admin_help.py`**

```python
"""Справка в админке (/admin/help/): список разделов — источник для оглавления, якорей и вводных над списками.

Раздел — шаблон `templates/admin/help/sections/<anchor>.html`; `help_anchor` у админок ссылается на `anchor`.
"""

from typing import NamedTuple

from django.contrib import admin
from django.template.response import TemplateResponse


class HelpSection(NamedTuple):
    anchor: str
    title: str

    @property
    def template(self) -> str:
        return f"admin/help/sections/{self.anchor}.html"


HELP_SECTIONS = (
    HelpSection("structure", "Как устроен сайт"),
    HelpSection("not-visible", "Почему этого не видно на сайте"),
)
HELP_ANCHORS = frozenset(section.anchor for section in HELP_SECTIONS)


def help_view(request):
    context = {**admin.site.each_context(request), "title": "Справка", "sections": HELP_SECTIONS}
    return TemplateResponse(request, "admin/help/index.html", context)
```

- [ ] **Step 4: URL и пункт меню**

`src/config/urls.py` — импорт и путь **до** `path("admin/", admin.site.urls)` (иначе перехватит catch-all админки):

```python
from apps.core.admin_help import help_view
...
urlpatterns = [
    path("admin/help/", admin.site.admin_view(help_view), name="admin_help"),
    path("admin/", admin.site.urls),
```

`src/config/settings.py`, первым элементом `"navigation"` (группа без заголовка — Unfold его не требует):

```python
        "navigation": [
            {"items": [_nav("Справка", "help", "admin_help")]},
            {
                "title": "Каталог",
```

- [ ] **Step 5: Каркас `templates/admin/help/index.html`**

```django
{% extends "admin/base_site.html" %}
{% load static %}

{% block extrastyle %}{{ block.super }}<link rel="stylesheet" href="{% static 'css/admin_help.css' %}">{% endblock %}

{% block content %}
<div class="admin-help">
  <p>Как работать с сайтом Т-Парка: где что править и почему что-то может не появиться на сайте. Ищите по странице — Ctrl+F (на Mac — ⌘+F).</p>
  <nav id="toc" aria-label="Оглавление" class="admin-help-toc">
    <ol>
      {% for section in sections %}<li><a href="#{{ section.anchor }}">{{ section.title }}</a></li>{% endfor %}
    </ol>
  </nav>
  {% for section in sections %}
  <section id="{{ section.anchor }}">
    <h2>{{ section.title }}</h2>
    {% include section.template %}
    <p class="admin-help-top"><a href="#toc">↑ К оглавлению</a></p>
  </section>
  {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 6: Стили `static/css/admin_help.css`**

```css
/* Справка админки (templates/admin/help/): типографика разделов — в CSS Unfold нет нужных классов. */
.admin-help { max-width: 48rem; line-height: 1.6; }
.admin-help section { scroll-margin-top: 1rem; padding-top: 0.5rem; }
.admin-help h2 { margin: 2rem 0 0.75rem; font-size: 1.25rem; font-weight: 600; color: var(--color-font-important-light); }
.admin-help h3 { margin: 1.25rem 0 0.5rem; font-weight: 600; color: var(--color-font-important-light); }
.dark .admin-help h2, .dark .admin-help h3 { color: var(--color-font-important-dark); }
.admin-help p { margin-bottom: 0.75rem; }
.admin-help ol, .admin-help ul { margin: 0 0 0.75rem; padding-left: 1.25rem; }
.admin-help ol { list-style: decimal; }
.admin-help ul { list-style: disc; }
.admin-help li + li { margin-top: 0.25rem; }
.admin-help a { color: var(--color-primary-600); text-decoration: underline; }
.dark .admin-help a { color: var(--color-primary-500); }
.admin-help-toc { margin: 1rem 0 1.5rem; padding: 1rem 1.25rem; border: 1px solid var(--color-base-200); border-radius: 6px; }
.dark .admin-help-toc { border-color: var(--color-base-800); }
.admin-help-top { font-size: 0.875rem; }
.admin-help-table { overflow-x: auto; margin-bottom: 0.75rem; }
.admin-help table { width: 100%; border-collapse: collapse; }
.admin-help th, .admin-help td { padding: 0.375rem 0.75rem 0.375rem 0; text-align: left; vertical-align: top; border-bottom: 1px solid var(--color-base-200); }
.dark .admin-help th, .dark .admin-help td { border-color: var(--color-base-800); }
.admin-help-note { padding: 0.75rem 1rem; border-radius: 6px; background: var(--color-base-50); }
.dark .admin-help-note { background: var(--color-base-800); }
```

Проверить имена переменных: `grep -o "\-\-color-font-important-light[^;]*" src/.venv/lib/python3.14/site-packages/unfold/static/unfold/css/styles.css | head -1` — если переменной нет, заменить на `var(--color-base-900)` (светлая) и `var(--color-base-100)` (тёмная).

- [ ] **Step 7: Раздел `sections/structure.html`**

```django
<p>Сайт собирается из нескольких разделов админки. Главная цепочка — каталог услуг:</p>
<p class="admin-help-note"><b>Группа меню</b> → <b>Категория</b> → <b>Услуга</b><br>
Группа — раздел меню «Услуги» в шапке и блок на главной. Категория — страница с услугами (например, «Сплавы»). Услуга — строка или карточка на странице категории; у услуги может быть своя страница.</p>
<p>Одна категория может входить в несколько групп, одна услуга — в несколько категорий.</p>

<h3>Что где править</h3>
<div class="admin-help-table"><table>
  <thead><tr><th>На сайте</th><th>Где в админке</th></tr></thead>
  <tbody>
    <tr><td>Меню «Услуги» в шапке, категории на главной</td><td><a href="{% url 'admin:catalog_categorygroup_changelist' %}">«Группы категорий»</a> и <a href="{% url 'admin:catalog_category_changelist' %}">«Категории»</a></td></tr>
    <tr><td>Страница категории: текст, фото, список услуг</td><td><a href="{% url 'admin:catalog_category_changelist' %}">«Категории»</a> (вкладки «Основное», «Фото», «Услуги»)</td></tr>
    <tr><td>Услуга: цена, описание, своя страница</td><td><a href="{% url 'admin:catalog_service_changelist' %}">«Услуги»</a></td></tr>
    <tr><td>Вступление и цитата на главной, блок мероприятий на главной</td><td><a href="{% url 'admin:core_sitesettings_changelist' %}">«Настройки сайта»</a>, вкладки «Главная» и «О нас»</td></tr>
    <tr><td>Мероприятия</td><td><a href="{% url 'admin:content_event_changelist' %}">«Мероприятия»</a>; вступление — «Настройки сайта», вкладка «Мероприятия и контакты»</td></tr>
    <tr><td>Страница «О нас», основатель, форматы, «Что рядом»</td><td>«Настройки сайта», вкладки «О нас», «Форматы (О нас)», «Основатель в цифрах (О нас)»</td></tr>
    <tr><td>Партнёры на «О нас»</td><td><a href="{% url 'admin:content_partner_changelist' %}">«Партнёры»</a></td></tr>
    <tr><td>Отзывы и карусель отзывов на главной</td><td><a href="{% url 'admin:content_review_changelist' %}">«Отзывы»</a></td></tr>
    <tr><td>Галерея и полоса «Как это выглядит»</td><td><a href="{% url 'admin:content_galleryphoto_changelist' %}">«Галерея»</a></td></tr>
    <tr><td>Адрес, телефоны, соцсети, карта, часы работы</td><td>«Настройки сайта», вкладки «Контакты» и «Разметка организации»</td></tr>
    <tr><td>Подвал: адрес, телефоны, политика конфиденциальности, правила безопасности</td><td>«Настройки сайта» (вкладки «Контакты», «Юридическое», «О нас») и <a href="{% url 'admin:core_infopage_changelist' %}">«Инфо-страницы»</a></td></tr>
    <tr><td>Заголовки блоков, короткие фразы и подсказки на всех страницах</td><td><a href="{% url 'admin:texts_sitetext_changelist' %}">«Тексты сайта»</a></td></tr>
    <tr><td>Заголовок и описание страницы в поиске Яндекса и Google</td><td>вкладка «SEO» в форме страницы; для главной и других постоянных страниц — «Настройки сайта», вкладка «SEO»</td></tr>
  </tbody>
</table></div>
```

- [ ] **Step 8: Раздел `sections/not-visible.html`**

```django
<p>Чаще всего дело в галочке «Опубликовано» или в том, что запись ни к чему не привязана. Пройдите по списку для своего случая.</p>

<h3>Категория</h3>
<ol>
  <li>У категории стоит «Опубликовано». Новая категория создаётся черновиком — без галочки её страница не откроется.</li>
  <li>Категория отмечена хотя бы в одной группе (поле «Группы меню» в форме категории). Без группы её нет в меню и на главной, страница открывается только по прямой ссылке.</li>
  <li>Сама группа опубликована (<a href="{% url 'admin:catalog_categorygroup_changelist' %}">«Группы категорий»</a>).</li>
</ol>

<h3>Услуга</h3>
<ol>
  <li>У услуги стоит «Опубликовано».</li>
  <li>Услуга добавлена хотя бы в одну опубликованную категорию (вкладка «Категории» в форме услуги). Найти такие услуги поможет фильтр <a href="{% url 'admin:catalog_service_changelist' %}?placement=hidden">«Видна на сайте → Нет в меню»</a>.</li>
  <li>Своя страница у услуги есть, только если отмечена «Отдельная страница». Без неё услуга показывается строкой в списке на странице категории.</li>
</ol>

<h3>Мероприятие</h3>
<ol>
  <li>Стоит «Опубликовано».</li>
  <li>Мероприятие ещё не прошло. На следующий день после последнего дня («Дата окончания», а если её нет — «Дата») оно становится прошедшим.</li>
  <li>Прошедшее остаётся в блоке «Прошедшие» только с галочкой «Показывать после даты». Без неё оно открывается лишь по прямой ссылке.</li>
  <li>На главной мероприятия видны, только если в «Настройках сайта» (вкладка «Главная») включён блок ближайших мероприятий; там показываются до трёх ближайших.</li>
</ol>

<h3>Фото</h3>
<ol>
  <li>Если сразу после загрузки фото выглядит тяжёлым или вместо уменьшенной копии видно оригинал — подождите минуту: уменьшенные копии создаются в фоне.</li>
  <li>Полоса «Как это выглядит» и блок «Ещё в категории» на странице услуги показывают не все фото и услуги, а подборку, которая меняется раз в сутки. Фото не пропало — завтра будет другой набор.</li>
  <li>Галерея на сайте показывает сначала 24 фото, остальные подгружаются при прокрутке.</li>
</ol>

<h3>Текст</h3>
<ol>
  <li>Необязательный текст в <a href="{% url 'admin:texts_sitetext_changelist' %}">«Текстах сайта»</a> оставлен пустым — тогда весь блок на сайте скрыт (у таких текстов подсказка «Пусто — блок на сайте скрыт.»).</li>
  <li>Инфо-страница опубликована и выбрана в «Настройках сайта» (вкладки «Юридическое» и «О нас») — иначе ссылки на неё в подвале нет.</li>
</ol>

<p>Если всё отмечено, а страница не открывается, — возможно, у неё сменился адрес. Старый адрес сам ведёт на новый (раздел <a href="{% url 'admin:core_redirect_changelist' %}">«Редиректы»</a>).</p>
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd src && uv run pytest tests/test_admin_help.py tests/test_admin.py tests/test_static.py -v`
Expected: PASS (все).

- [ ] **Step 10: Commit**

```bash
git add src/apps/core/admin_help.py src/config/urls.py src/config/settings.py src/templates/admin/help src/static/css/admin_help.css src/tests/test_admin_help.py
git commit -m "Справка в админке: страница, пункт меню, разделы о структуре и видимости

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Разделы «Общие приёмы», «Фото», «Каталог»

**Files:**
- Modify: `src/apps/core/admin_help.py` (`HELP_SECTIONS`)
- Create: `src/templates/admin/help/sections/basics.html`, `photos.html`, `catalog.html`
- Test: `src/tests/test_admin_help.py`

**Interfaces:**
- Consumes: `HelpSection`, `HELP_SECTIONS` из задачи 1.
- Produces: якоря `basics`, `photos`, `catalog`.

- [ ] **Step 1: Write the failing test**

Добавить в `src/tests/test_admin_help.py`:

```python
def test_help_covers_basics_photos_catalog(admin_client):
    html = _help_html(admin_client)
    for anchor in ("basics", "photos", "catalog"):
        assert f'<section id="{anchor}">' in html
    for phrase in ("перетаскиванием", "20 МБ", "16:9", "Отдельная страница", "«Ещё в категории»"):
        assert phrase in html, phrase
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest tests/test_admin_help.py::test_help_covers_basics_photos_catalog -v`
Expected: FAIL — `assert '<section id="basics">' in html`.

- [ ] **Step 3: Добавить разделы в `HELP_SECTIONS`**

```python
HELP_SECTIONS = (
    HelpSection("structure", "Как устроен сайт"),
    HelpSection("not-visible", "Почему этого не видно на сайте"),
    HelpSection("basics", "Общие приёмы"),
    HelpSection("photos", "Фото"),
    HelpSection("catalog", "Каталог: группы, категории, услуги"),
)
```

- [ ] **Step 4: `sections/basics.html`**

```django
<h3>Публикация и черновики</h3>
<p>Галочка «Опубликовано» решает, видна ли запись на сайте. Снятая галочка — черновик: страница не откроется, запись пропадёт из списков, но в админке всё сохранится. Так удобно готовить категорию или мероприятие заранее. В списках галочку можно переключать прямо в таблице — затем нажмите «Сохранить» внизу списка.</p>
<p>У фото галереи, партнёров и текстов сайта галочки нет: чтобы убрать фото или партнёра с сайта, запись удаляют.</p>

<h3>Порядок</h3>
<p>Порядок групп, категорий, фото, партнёров, телефонов и строк на вкладках задаётся перетаскиванием — тяните строку за значок слева и сохраните. Отзывы и мероприятия сортируются по дате сами.</p>

<h3>Редактор текста</h3>
<p>Длинные тексты (описания, «О нас», инфо-страницы) правятся в редакторе с кнопками: заголовки, жирный, списки, ссылки. Текст, вставленный из Word или с другого сайта, очищается от лишнего оформления при сохранении.</p>

<h3>Адрес страницы</h3>
<p>Поле «Адрес страницы» — часть ссылки, например <code>/category/splavy/</code>. Если оставить его пустым, адрес составится из названия латиницей. Адрес можно поменять, но страницы, которые уже есть в поиске, лучше не трогать. Если поменять, старый адрес сам будет вести на новый: перенаправление появится в разделе <a href="{% url 'admin:core_redirect_changelist' %}">«Редиректы»</a>. Вернёте прежний адрес — лишнее перенаправление удалится.</p>
<p>Перенаправление срабатывает, только если по старому адресу страницы нет. Вручную его добавляют редко — например, чтобы старая ссылка из соцсети вела на новую страницу. Адреса пишутся от корня сайта: <code>/info/pravila/</code>.</p>

<h3>Несохранённые изменения</h3>
<p>Если уйти со страницы, не сохранив форму или список, браузер спросит «Покинуть страницу?». Это защита от случайной потери правок: нажмите «Отмена» и сохраните.</p>
```

Перед записью проверить путь категории: `grep -n "path(" src/apps/catalog/urls.py` — если префикс не `category/`, исправить пример.

- [ ] **Step 5: `sections/photos.html`**

```django
<h3>Какие фото загружать</h3>
<ul>
  <li>Форматы — jpg, png или webp (фото с iPhone в формате HEIC сначала сохраните как jpg).</li>
  <li>До 20 МБ и до 50 мегапикселей. Больше — уменьшите фото перед загрузкой.</li>
  <li>Горизонтальные, от 1600 px по ширине. Большие фото сайт уменьшит сам, маленькие не растягивает.</li>
</ul>

<h3>Как обрезается кадр</h3>
<p>В разных местах сайта фото показываются в разных рамках, лишнее по краям обрезается. Держите главное ближе к центру.</p>
<div class="admin-help-table"><table>
  <thead><tr><th>Где</th><th>Рамка</th></tr></thead>
  <tbody>
    <tr><td>Слайдер на странице категории и услуги</td><td>16:9 (как экран телевизора) — снимайте людей с запасом сверху и снизу</td></tr>
    <tr><td>«Превью для главной» у категории</td><td>карточка на главной 4:3 (широкая — 16:9), шапка категории 16:9 на телефоне и 3:2 на компьютере</td></tr>
    <tr><td>Карточка услуги</td><td>квадрат на телефоне, 4:3 на компьютере (берётся первое фото услуги)</td></tr>
    <tr><td>Мероприятие</td><td>4:3</td></tr>
    <tr><td>Галерея и полоса «Как это выглядит»</td><td>квадрат; по клику в галерее фото открывается целиком</td></tr>
    <tr><td>Фото в шапке «О нас» (оно же на главной)</td><td>4:3</td></tr>
    <tr><td>Фото основателя</td><td>4:5, вертикальное</td></tr>
    <tr><td>Фото в отзыве</td><td>маленький кружок</td></tr>
    <tr><td>Логотипы партнёров</td><td>без обрезки, целиком</td></tr>
  </tbody>
</table></div>
<p>При просмотре на весь экран фото показывается целиком, без обрезки.</p>

<h3>Много фото сразу</h3>
<ul>
  <li>Категория и услуга — вкладка «Загрузка фото» в форме: выберите несколько файлов и сохраните, фото добавятся в конец.</li>
  <li>Галерея — кнопка <a href="{% url 'admin:content_galleryphoto_bulk_upload' %}">«Загрузить фото пачкой»</a> над списком.</li>
  <li>В любое поле загрузки можно просто перетащить файл из папки.</li>
</ul>

<h3>Почему новое фото появляется не сразу</h3>
<p>После сохранения сайт в фоне готовит уменьшенные копии фото для телефонов и компьютеров. Обычно это секунды, после смены многих фото — до пары минут. Пока копии нет, посетитель видит оригинал: он тяжелее, но фото не пропадает.</p>

<h3>Подборки меняются раз в сутки</h3>
<p>Полоса «Как это выглядит» (6 фото из галереи на главной, «О нас» и «Отзывах») и блок «Ещё в категории» на странице услуги каждый день показывают новый набор. В течение дня набор одинаковый. Порядок внутри подборки — как в админке.</p>
```

- [ ] **Step 6: `sections/catalog.html`**

```django
<h3>Группы меню</h3>
<p><a href="{% url 'admin:catalog_categorygroup_changelist' %}">«Группы категорий»</a> — разделы выпадающего меню «Услуги» в шапке и блоки категорий на главной. В форме группы отметьте её категории. Группа без опубликованных категорий на сайте не показывается.</p>

<h3>Категории</h3>
<ol>
  <li><a href="{% url 'admin:catalog_category_add' %}">«Каталог → Категории → Добавить»</a>: название, описание (текст под заголовком страницы), «Превью для главной».</li>
  <li>Поле «Группы меню» — где категория видна в меню и на главной.</li>
  <li>Вкладка «Фото» — слайдер на странице категории, вкладка «Услуги» — какие услуги и в каком порядке показывать.</li>
  <li>Новая категория — черновик. Поставьте «Опубликовано», когда добавите услуги и фото.</li>
</ol>
<p>Внизу страницы категории сайт сам показывает до четырёх других категорий из тех же групп. В подвал попадают первые 8 категорий меню.</p>
<p>Перед удалением категории админка предупредит, какие услуги останутся без категории: привяжите их к другой категории или снимите с публикации.</p>

<h3>Услуги</h3>
<ol>
  <li><a href="{% url 'admin:catalog_service_add' %}">«Каталог → Услуги → Добавить»</a>: название, цена, «За что».</li>
  <li>«Цена» — числом («1500», «от 3500»): сайт сам добавит «₽» и разделит тысячи. Или текстом — «договорная», «бесплатно»: выводится как есть. «За что» показывается через косую черту: «1500 ₽ / час».</li>
  <li>«Краткое описание» — 1–2 предложения для карточки и раскрывающейся строки на странице категории. «Полное описание» видно только на странице услуги.</li>
  <li>«Отдельная страница» — у услуги появится своя страница, а в категории — карточка с фото вместо строки. Без галочки страницы нет.</li>
  <li>Вкладка «Категории» — без категории услугу на сайте не найти. Вкладка «Фото» — слайдер страницы услуги, первое фото идёт в карточку.</li>
</ol>
<p>На странице услуги внизу — блок «Ещё в категории»: до трёх других услуг с отдельной страницей из той же категории, набор меняется раз в сутки.</p>
<p>Фильтр <a href="{% url 'admin:catalog_service_changelist' %}?placement=none">«Видна на сайте»</a> в списке услуг находит услуги без категории и услуги, у которых нет опубликованной категории.</p>
```

- [ ] **Step 7: Run tests**

Run: `cd src && uv run pytest tests/test_admin_help.py -v`
Expected: PASS (включая `test_help_admin_links_open` — ссылки новых разделов открываются).

- [ ] **Step 8: Commit**

```bash
git add src/apps/core/admin_help.py src/templates/admin/help/sections src/tests/test_admin_help.py
git commit -m "Справка: общие приёмы, фото, каталог

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Разделы «Мероприятия», «Отзывы», «Галерея и партнёры»

**Files:**
- Modify: `src/apps/core/admin_help.py`
- Create: `src/templates/admin/help/sections/events.html`, `reviews.html`, `gallery.html`
- Test: `src/tests/test_admin_help.py`

**Interfaces:**
- Consumes: `HELP_SECTIONS` из задач 1–2.
- Produces: якоря `events`, `reviews`, `gallery`.

- [ ] **Step 1: Write the failing test**

```python
def test_help_covers_events_reviews_gallery(admin_client):
    html = _help_html(admin_client)
    for anchor in ("events", "reviews", "gallery"):
        assert f'<section id="{anchor}">' in html
    for phrase in ("«Показывать после даты»", "«Подтянуть»", "«Гость Т-Парка»", "«О нас»"):
        assert phrase in html, phrase
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest tests/test_admin_help.py::test_help_covers_events_reviews_gallery -v`
Expected: FAIL — нет `<section id="events">`.

- [ ] **Step 3: Добавить в `HELP_SECTIONS` после `catalog`**

```python
    HelpSection("events", "Мероприятия"),
    HelpSection("reviews", "Отзывы"),
    HelpSection("gallery", "Галерея и партнёры"),
```

- [ ] **Step 4: `sections/events.html`**

```django
<ol>
  <li><a href="{% url 'admin:content_event_add' %}">«Контент → Мероприятия → Добавить»</a>: заголовок, дата, время начала, описание, фото.</li>
  <li>Многодневное — заполните «Дата окончания». Для однодневного её не нужно.</li>
  <li>«Место проведения» — пусто, если в Т-Парке (на сайте подставится адрес парка). «Стоимость» — коротко: «1000 ₽ с участника», «Бесплатно».</li>
  <li>Снимите «Опубликовано», чтобы подготовить мероприятие заранее.</li>
</ol>

<h3>Предстоящие и прошедшие</h3>
<p>Мероприятие предстоящее, пока не закончился его последний день. На следующий день оно становится прошедшим: пропадает из списков, а на его странице появляется надпись «Мероприятие уже прошло.» и исчезают кнопки связи.</p>
<p>Галочка «Показывать после даты» оставляет прошедшее в блоке «Прошедшие» на странице «Мероприятия» и в поиске — для фотоотчётов и знаковых событий. Без неё прошедшее открывается только по прямой ссылке.</p>
<p>В админке фильтр «Период» показывает отдельно предстоящие и прошедшие.</p>

<h3>Что видно на сайте</h3>
<ul>
  <li>Страница «Мероприятия»: ближайшее — большой карточкой, дальше — остальные предстоящие, ниже — прошедшие с «Показывать после даты».</li>
  <li>Главная: до трёх ближайших, если в «Настройках сайта» на вкладке «Главная» включён блок мероприятий.</li>
  <li>Метка на карточке: «Сегодня», «Завтра», «Через N дней» (до 30 дней), «Идёт сейчас» для многодневных.</li>
  <li>Если предстоящих нет, на странице «Мероприятия» — текст из «Текстов сайта» и кнопка группы ВКонтакте.</li>
</ul>
<p>Адрес страницы мероприятия составляется из заголовка и года.</p>
```

- [ ] **Step 5: `sections/reviews.html`**

```django
<h3>Как добавить отзыв с Яндекса</h3>
<ol>
  <li>На Яндекс Картах откройте отзыв и скопируйте ссылку на него — она начинается с <code>https://reviews.yandex.ru/</code>.</li>
  <li><a href="{% url 'admin:content_review_add' %}">«Контент → Отзывы → Добавить»</a>, вставьте ссылку в «Ссылку на отзыв» и нажмите «Подтянуть» — текст и дата заполнятся сами.</li>
  <li>Проверьте текст и сохраните.</li>
</ol>
<p>Если Яндекс не ответил или ссылка не та, под полем появится причина красным — тогда скопируйте текст и дату вручную. Отзыв из ВКонтакте, 2ГИС или Google добавляется так же, только вручную.</p>

<h3>Что видно на сайте</h3>
<ul>
  <li>Отзывы идут от новых к старым по «Дате отзыва», без даты — в конце. Перетаскиванием порядок не меняется.</li>
  <li>Имени у отзыва нет: все подписаны «Гость Т-Парка». Под отзывом — источник («Яндекс Карты», «ВКонтакте»…), он определяется по ссылке и ведёт на оригинал.</li>
  <li>«Фото» — маленький кружок рядом с подписью; без фото — значок человека.</li>
  <li>Цвета карточек чередуются сами: зелёный, оранжевый, вересковый, песочный.</li>
  <li>На главной — карусель из 8 последних отзывов, на странице «Отзывы» — все опубликованные и их число.</li>
</ul>
<p>Кнопки «Оставить отзыв» и «Все отзывы на Яндекс Картах» ведут по ссылке из «Настроек сайта» (вкладка «Контакты», «Ссылка на отзывы»). Пусто — кнопок нет.</p>
```

Перед записью проверить подпись поля: `grep -n "reviews_url" -A3 src/apps/core/models.py` — в тексте должен стоять точный `verbose_name` поля вместо «Ссылка на отзывы», если он другой.

- [ ] **Step 6: `sections/gallery.html`**

```django
<h3>Галерея</h3>
<p><a href="{% url 'admin:content_galleryphoto_changelist' %}">«Контент → Галерея»</a> — фото для страницы «Галерея» и полосы «Как это выглядит» (по 6 фото на главной, «О нас» и «Отзывах», набор меняется раз в сутки).</p>
<ul>
  <li>Много фото сразу — кнопка «Загрузить фото пачкой» над списком; новые фото добавятся в конец.</li>
  <li>Порядок — перетаскиванием. На странице «Галерея» сначала видно 24 фото, остальные подгружаются при прокрутке.</li>
  <li>«Подпись» видна при просмотре фото на весь экран и описывает фото для поисковиков и незрячих посетителей. Пусто — «Т-Парк, Калужская область — фото N».</li>
  <li>Чтобы убрать фото с сайта, удалите его: галочки «Опубликовано» у галереи нет.</li>
</ul>

<h3>Партнёры</h3>
<p><a href="{% url 'admin:content_partner_changelist' %}">«Контент → Партнёры»</a> — логотипы в блоке «Партнёры» на странице «О нас».</p>
<ul>
  <li>Логотип показывается целиком, в своих пропорциях, без обрезки. Лучше PNG с прозрачным или белым фоном.</li>
  <li>«Название» описывает логотип для поисковиков; если логотипа нет, на сайте будет плитка с названием.</li>
  <li>«Ссылка» — сайт или соцсеть партнёра, откроется в новой вкладке. Пусто — логотип без ссылки.</li>
  <li>Порядок — перетаскиванием. Убрать партнёра — удалить запись.</li>
</ul>
```

- [ ] **Step 7: Run tests**

Run: `cd src && uv run pytest tests/test_admin_help.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/apps/core/admin_help.py src/templates/admin/help/sections src/tests/test_admin_help.py
git commit -m "Справка: мероприятия, отзывы, галерея и партнёры

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Разделы «Настройки сайта», «Тексты сайта», «Инфо-страницы», «Поиск и SEO», «Доступ»

**Files:**
- Modify: `src/apps/core/admin_help.py`
- Create: `src/templates/admin/help/sections/settings.html`, `texts.html`, `info-pages.html`, `seo.html`, `access.html`
- Test: `src/tests/test_admin_help.py`

**Interfaces:**
- Consumes: `HELP_SECTIONS` из задач 1–3.
- Produces: полный набор из 13 якорей (используется задачей 5).

- [ ] **Step 1: Write the failing test**

```python
EXPECTED_SECTIONS = [
    "structure", "not-visible", "basics", "photos", "catalog", "events", "reviews", "gallery",
    "settings", "texts", "info-pages", "seo", "access",
]


def test_help_sections_complete(admin_client):
    assert [s.anchor for s in HELP_SECTIONS] == EXPECTED_SECTIONS
    html = _help_html(admin_client)
    for phrase in ("WhatsApp", "«Восстановить»", "[укажите", "Вебмастер", "30 минут"):
        assert phrase in html, phrase
```

(`ruff format` разложит список по строкам — это нормально.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest tests/test_admin_help.py::test_help_sections_complete -v`
Expected: FAIL — списки разделов различаются.

- [ ] **Step 3: Добавить в `HELP_SECTIONS` после `gallery`**

```python
    HelpSection("settings", "Настройки сайта"),
    HelpSection("texts", "Тексты сайта"),
    HelpSection("info-pages", "Инфо-страницы"),
    HelpSection("seo", "Поиск и SEO"),
    HelpSection("access", "Доступ и вход"),
```

- [ ] **Step 4: `sections/settings.html`**

```django
<p><a href="{% url 'admin:core_sitesettings_changelist' %}">«Сайт → Настройки сайта»</a> — одна форма с вкладками для всего, что встречается на многих страницах.</p>
<ul>
  <li><b>Контакты</b> — адрес (главная, подвал, «Контакты», «О нас», место мероприятий без своего адреса), Яндекс Карта на странице контактов (вставьте код из «Поделиться → Встроить карту» целиком), ВКонтакте, MAX, ссылка на отзывы. Пустая ссылка — кнопки нет.</li>
  <li><b>Логотип</b> — логотип в шапке. Пусто — стандартный.</li>
  <li><b>Главная</b> — вступление (оно же — описание сайта для поисковиков по умолчанию) и блок ближайших мероприятий.</li>
  <li><b>Мероприятия и контакты</b> — вступление страницы «Мероприятия» и текст на странице «Контакты».</li>
  <li><b>О нас</b> — цитата в шапке (она же на главной), фото в шапке, текст, основатель, «Что рядом», страница правил безопасности. Форматы парка и цифры основателя — на вкладках «Форматы (О нас)» и «Основатель в цифрах (О нас)».</li>
  <li><b>Юридическое</b> — страница политики конфиденциальности для ссылки в подвале.</li>
  <li><b>SEO</b>, <b>Разметка организации</b>, <b>Вебмастер и Метрика</b> — для поисковиков, см. <a href="#seo">«Поиск и SEO»</a>. Из «Разметки организации» на сайте видны часы работы (главная, «Контакты», подвал), координаты (кнопки «Маршрут» и «Координаты для навигатора») и ссылка на Т-Парк в Яндекс Картах.</li>
</ul>
<p>На каждой вкладке есть ссылка на «Тексты сайта» нужной страницы — там заголовки блоков и короткие фразы.</p>

<h3>Телефоны и мессенджеры</h3>
<ul>
  <li>Номер — 10 цифр без +7 и 8, без пробелов и скобок: <code>9029856594</code>. На сайте он будет выглядеть как «+7 (902) 985-65-94».</li>
  <li>Первый номер — главный: на него ведёт кнопка «Связаться» в шапке и на страницах. Все номера — на «Контактах» и в подвале. Порядок — перетаскиванием.</li>
  <li>WhatsApp и Telegram — отметьте у номера, на который ведут эти кнопки. Каждую галочку можно поставить только у одного номера. Со страниц услуги, категории и мероприятия WhatsApp откроется с готовым сообщением «Здравствуйте! Интересует «…»».</li>
</ul>

<h3>Часы работы</h3>
<p>Поле «Часы работы» на вкладке «Разметка организации» пишется в особом формате: <code>Mo-Su 09:00-21:00</code> (дни недели по-английски: Mo, Tu, We, Th, Fr, Sa, Su). Сайт сам переведёт их на русский. Если формат не распознан, часы не покажутся нигде — проверьте страницу «Контакты» после правки.</p>
```

- [ ] **Step 5: `sections/texts.html`**

```django
<p><a href="{% url 'admin:texts_sitetext_changelist' %}">«Сайт → Тексты сайта»</a> — заголовки блоков и короткие фразы всех страниц: подсказки, призывы связаться, тексты пустых блоков. Длинные тексты страниц («О нас», биография, вступления) — в <a href="#settings">«Настройках сайта»</a>.</p>
<ul>
  <li>Найти текст — фильтр по странице справа или поиск по словам. В форме видно, где он на сайте, и текст по умолчанию.</li>
  <li>Обязательный текст (заголовок) нельзя оставить пустым. Необязательный («Пусто — блок на сайте скрыт.») можно очистить — блок пропадёт с сайта.</li>
  <li>Добавлять и удалять тексты нельзя — только править.</li>
</ul>

<h3>История и возврат</h3>
<p>Каждая правка сохраняется. Кнопка «История» в форме текста показывает, кто и когда менял текст. Откройте нужную версию и нажмите «Восстановить» — текст вернётся. Первая запись — «Начальный текст».</p>
```

- [ ] **Step 6: `sections/info-pages.html`**

```django
<p><a href="{% url 'admin:core_infopage_changelist' %}">«Сайт → Инфо-страницы»</a> — отдельные страницы с текстом: правила безопасности, политика конфиденциальности и любые другие. Адрес — <code>/info/&lt;адрес страницы&gt;/</code>.</p>
<ul>
  <li>В меню инфо-страниц нет. Ссылки на сайте появляются, только если выбрать страницу в «Настройках сайта»: «Правила безопасности» (вкладка «О нас») — плашка на «О нас» и ссылка в подвале; «Политика конфиденциальности» (вкладка «Юридическое») — ссылка в подвале.</li>
  <li>Для любой другой страницы скопируйте ссылку кнопкой в поле «Ссылка на страницу» (появится после сохранения) и вставьте её в текст или соцсеть.</li>
  <li>Неопубликованная страница не откроется, и ссылок на неё на сайте не будет.</li>
</ul>

<h3>Политика конфиденциальности</h3>
<p>Типовой текст уже создан и выбран в настройках, но снят с публикации: в нём есть пометки «[укажите …]» — ФИО или наименование, ИНН, ОГРН(ИП), адрес, e-mail. Заполните их, проверьте дату редакции и поставьте «Опубликовано» — ссылка появится в подвале.</p>
```

- [ ] **Step 7: `sections/seo.html`**

```django
<p>SEO — то, как страницы выглядят в поиске Яндекса и Google и в превью ссылок в мессенджерах. Подробные подсказки, счётчики символов и превью сниппета — на самих вкладках, здесь только где что лежит.</p>
<ul>
  <li><b>Вкладка «SEO»</b> в форме категории, услуги, мероприятия и инфо-страницы — заголовок и описание этой страницы в поиске. Пусто — сайт составит их сам из названия и описания.</li>
  <li><b>«Настройки сайта» → «SEO»</b> — окончание заголовков («— Т-Парк, Калужская область»), картинка для соцсетей по умолчанию, заголовки и описания главной, «Мероприятий», «О нас», «Отзывов», «Галереи», «Контактов».</li>
  <li><b>«Разметка организации»</b> — адрес по частям, координаты, часы работы, уровень цен, ссылка на Т-Парк в Яндекс Картах: поисковики показывают это в карточке организации.</li>
  <li><b>«Вебмастер и Метрика»</b> — коды подтверждения для Яндекс Вебмастера и Google Search Console и номер счётчика Яндекс Метрики. С номером счётчика на сайте появляется Метрика и плашка про cookie.</li>
</ul>
```

- [ ] **Step 8: `sections/access.html`**

```django
<ul>
  <li><a href="{% url 'admin:auth_user_changelist' %}">«Доступ → Пользователи»</a> — кто может входить в админку. Чтобы человек вошёл, у него должна стоять галочка «Статус персонала»; «Статус суперпользователя» даёт все права без настройки групп.</li>
  <li><a href="{% url 'admin:auth_group_changelist' %}">«Доступ → Группы»</a> — наборы прав: какие разделы пользователь может смотреть и менять.</li>
  <li>Пароль меняется в форме пользователя — ссылкой под полем «Пароль».</li>
</ul>

<h3>Если вход заблокирован</h3>
<p>После 5 неверных паролей подряд вход для этого логина с этого устройства блокируется на 30 минут — так сайт защищается от подбора пароля. Появится страница «Учетная запись заблокирована: слишком много попыток входа». Подождите 30 минут: даже правильный пароль до этого не подойдёт. Срочно — попросите программиста снять блокировку (команда <code>axes_reset</code>).</p>
```

Перед записью проверить подписи полей пользователя: `cd src && uv run python -c "import django,os;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();from django.contrib.auth.models import User;print(User._meta.get_field('is_staff').verbose_name, '|', User._meta.get_field('is_superuser').verbose_name)"` и заменить «Статус персонала»/«Статус суперпользователя» на выведенные значения (с заглавной буквы). Ссылку на смену пароля проверить в форме пользователя на dev-сервере (задача 8) и при расхождении поправить формулировку.

- [ ] **Step 9: Run tests**

Run: `cd src && uv run pytest tests/test_admin_help.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add src/apps/core/admin_help.py src/templates/admin/help/sections src/tests/test_admin_help.py
git commit -m "Справка: настройки, тексты, инфо-страницы, SEO, доступ

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Вводные над списками и ссылка «Справка по разделу» в формах

**Files:**
- Create: `src/templates/admin/help/list_intro.html`, `src/templates/admin/help/form_link.html`
- Modify: `src/apps/core/admin_utils.py` (`SiteModelAdmin`)
- Modify: `src/apps/catalog/admin.py`, `src/apps/content/admin.py`, `src/apps/core/admin.py`, `src/apps/texts/admin.py`, `src/apps/texts/hints.py`
- Delete: `src/templates/admin/texts/list_before.html`
- Test: `src/tests/test_admin_help.py`

**Interfaces:**
- Consumes: `HELP_ANCHORS` (задача 4 — все 13 якорей), URL `admin_help`.
- Produces: `SiteModelAdmin.help_intro: str = ""` (доверенный HTML, пишет разработчик), `SiteModelAdmin.help_anchor: str = ""`; `apps.texts.hints.texts_intro` (ленивая строка).

- [ ] **Step 1: Write the failing tests**

```python
from django.conf import settings
from django.contrib import admin
from django.urls import resolve

from apps.core.admin import SiteSettingsAdmin


def _sidebar_admins():
    for group in settings.UNFOLD["SIDEBAR"]["navigation"]:
        for item in group["items"]:
            model_admin = getattr(resolve(str(item["link"])).func, "model_admin", None)
            if model_admin is not None:
                yield model_admin


def test_every_sidebar_section_has_help():
    admins = list(_sidebar_admins())
    assert len(admins) == 13
    for model_admin in admins:
        assert model_admin.help_anchor in HELP_ANCHORS, model_admin
        if not isinstance(model_admin, SiteSettingsAdmin):
            assert model_admin.help_intro, model_admin


def test_help_anchors_exist():
    for model_admin in admin.site._registry.values():
        if getattr(model_admin, "help_anchor", ""):
            assert model_admin.help_anchor in HELP_ANCHORS, model_admin


def test_changelist_shows_intro_and_help_link(admin_client):
    html = admin_client.get(reverse("admin:content_galleryphoto_changelist")).content.decode()
    assert "Как это выглядит" in html
    assert f'{reverse("admin_help")}#gallery' in html


def test_every_admin_form_links_to_help(admin_client):
    for model, model_admin in admin.site._registry.items():
        if not getattr(model_admin, "help_anchor", ""):
            continue
        info = (model._meta.app_label, model._meta.model_name)
        response = admin_client.get(reverse("admin:{}_{}_changelist".format(*info)), follow=True)
        if model_admin.has_add_permission(response.wsgi_request):
            response = admin_client.get(reverse("admin:{}_{}_add".format(*info)))
        html = response.content.decode()
        assert f'{reverse("admin_help")}#{model_admin.help_anchor}' in html, model
```

(Для «Настроек сайта» и «Текстов сайта» добавить нельзя — проверяется форма, куда ведёт список: у настроек это форма изменения, у текстов — сам список со ссылкой.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && uv run pytest tests/test_admin_help.py -k "sidebar_section or anchors_exist or changelist_shows or form_links" -v`
Expected: FAIL — `AttributeError: ... has no attribute 'help_anchor'` / нет ссылки в HTML.

- [ ] **Step 3: Шаблоны**

`src/templates/admin/help/list_intro.html`:

```django
{% with model_admin=cl.model_admin %}{% if model_admin.help_anchor %}
<p class="mb-4 text-sm text-base-500">{% if model_admin.help_intro %}{{ model_admin.help_intro|safe }} {% endif %}<a href="{% url 'admin_help' %}#{{ model_admin.help_anchor }}" class="text-primary-600 underline dark:text-primary-500">Подробнее в справке →</a></p>
{% endif %}{% endwith %}
```

`src/templates/admin/help/form_link.html`:

```django
{% with model_admin=adminform.model_admin %}{% if model_admin.help_anchor %}
<p class="mb-4 text-sm"><a href="{% url 'admin_help' %}#{{ model_admin.help_anchor }}" class="text-primary-600 underline dark:text-primary-500">Справка по разделу →</a></p>
{% endif %}{% endwith %}
```

- [ ] **Step 4: `SiteModelAdmin`** (`src/apps/core/admin_utils.py`)

```python
class SiteModelAdmin(ModelAdmin):
    """Базовая админка проекта: предупреждает при уходе со страницы с несохранёнными изменениями,
    у SEO-полей показывает счётчики символов и превью сниппета (admin_seo.js), над списком — вводную
    `help_intro`, над формой — ссылку на раздел справки `help_anchor` (apps/core/admin_help.py)."""

    help_intro = ""  # 1–2 предложения над списком; доверенный HTML (выводится через |safe)
    help_anchor = ""  # якорь раздела справки из HELP_SECTIONS
    list_before_template = "admin/help/list_intro.html"
    change_form_before_template = "admin/help/form_link.html"
```

(остальное тело класса — без изменений).

- [ ] **Step 5: Вводная «Текстов сайта» — `src/apps/texts/hints.py`**

Добавить в конец файла:

```python
def _texts_intro() -> str:
    return format_html(
        "Короткие фразы и заголовки блоков витрины. Вступления и длинные тексты страниц («О нас», биография, "
        "«Что рядом», текст контактов) — в <a href=\"{}\" class=\"text-primary-600 underline\">«Настройках сайта»</a>.",
        reverse("admin:core_sitesettings_changelist"),
    )


# Вводная над списком «Текстов сайта»: ссылка собирается при показе (URL-ы к этому моменту уже загружены).
texts_intro = lazy(_texts_intro, str)()
```

В `src/apps/texts/admin.py`: импорт `from apps.texts.hints import texts_intro`; в `SiteTextAdmin` заменить `list_before_template = "admin/texts/list_before.html"` на:

```python
    help_intro = texts_intro
    help_anchor = "texts"
```

Удалить `src/templates/admin/texts/list_before.html`: `git rm src/templates/admin/texts/list_before.html`.

- [ ] **Step 6: `help_intro`/`help_anchor` у остальных админок**

`src/apps/catalog/admin.py`:

```python
class CategoryGroupAdmin(SiteModelAdmin):
    help_intro = "Разделы меню «Услуги» в шапке и блоки категорий на главной. Порядок — перетаскиванием."
    help_anchor = "catalog"

class CategoryAdmin(BulkPhotosAdminMixin, SiteModelAdmin):
    help_intro = (
        "Страницы с услугами. В меню и на главной категория появится, когда опубликованы и она, и её группа. "
        "Новая категория — черновик."
    )
    help_anchor = "catalog"

class ServiceAdmin(BulkPhotosAdminMixin, SiteModelAdmin):
    help_intro = (
        "Услуги показываются на страницах категорий, в которые добавлены. "
        "Фильтр «Видна на сайте» находит услуги, которых посетители не увидят."
    )
    help_anchor = "catalog"
```

`src/apps/content/admin.py`:

```python
class EventAdmin(SiteModelAdmin):
    help_intro = (
        "Предстоящие — на странице «Мероприятия» и до трёх на главной. "
        "На следующий день после окончания мероприятие становится прошедшим."
    )
    help_anchor = "events"

class ReviewAdmin(SiteModelAdmin):
    help_intro = "Новые сверху — по дате отзыва. Ссылка на отзыв с Яндекса и кнопка «Подтянуть» заполнят текст и дату."
    help_anchor = "reviews"

class PartnerAdmin(OrderedPhotoAdmin):
    help_intro = "Логотипы в блоке «Партнёры» на странице «О нас». Порядок — перетаскиванием."
    help_anchor = "gallery"

class GalleryPhotoAdmin(OrderedPhotoAdmin):
    help_intro = (
        "Фото для страницы «Галерея» и полосы «Как это выглядит» на главной, «О нас» и «Отзывах». "
        "Порядок — перетаскиванием."
    )
    help_anchor = "gallery"
```

`src/apps/core/admin.py`:

```python
class SiteSettingsAdmin(SiteModelAdmin):
    help_anchor = "settings"  # списка нет — сразу форма, вводная не нужна

class InfoPageAdmin(SiteModelAdmin):
    help_intro = (
        "Отдельные страницы с текстом: правила, политика конфиденциальности. В меню их нет — "
        "ссылки выбираются в «Настройках сайта» или копируются из формы."
    )
    help_anchor = "info-pages"

class RedirectAdmin(SiteModelAdmin):
    help_intro = (
        "Перенаправления со старых адресов на новые. Создаются сами, когда меняют «Адрес страницы»; "
        "вручную добавлять нужно редко."
    )
    help_anchor = "basics"

class UserAdmin(BaseUserAdmin, SiteModelAdmin):
    help_intro = "Учётные записи для входа в админку."
    help_anchor = "access"

class GroupAdmin(BaseGroupAdmin, SiteModelAdmin):
    help_intro = "Наборы прав: какие разделы пользователь может смотреть и менять."
    help_anchor = "access"
```

(В `GroupAdmin` заменить `pass` на эти строки.)

- [ ] **Step 7: Run tests**

Run: `cd src && uv run pytest tests/test_admin_help.py tests/test_admin.py tests/test_texts.py -v`
Expected: PASS, в том числе `tests/test_texts.py::…` со ссылкой на настройки над списком текстов (строки 164–166). Если `test_every_admin_form_links_to_help` падает на форме пользователя или текста — проверить, что их шаблон формы расширяет `admin/change_form.html` Unfold (`grep -rn "extends" <шаблон>`), и при необходимости переопределить в админке `change_form_before_template` не нужно — ищем, где теряется include, и чиним в шаблоне проекта.

- [ ] **Step 8: Commit**

```bash
git add -A src/templates/admin src/apps src/tests/test_admin_help.py
git commit -m "Вводные над списками и ссылка на справку в формах админки

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: «Быстрый старт» на главной админки

**Files:**
- Modify: `src/templates/admin/dashboard_help.html`
- Modify: `src/templates/admin/index.html` (комментарий)
- Test: `src/tests/test_admin.py` (`test_admin_index_has_instructions`, ~строка 423)

**Interfaces:**
- Consumes: URL `admin_help`.

- [ ] **Step 1: Обновить тест (падающий)**

Заменить `test_admin_index_has_instructions` в `src/tests/test_admin.py`:

```python
def test_admin_index_has_quick_start(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    assert "Быстрый старт" in html
    assert reverse("admin_help") in html
    for name in (
        "admin:catalog_service_add",
        "admin:content_event_add",
        "admin:content_review_add",
        "admin:content_galleryphoto_bulk_upload",
        "admin:core_sitesettings_changelist",
    ):
        assert f'href="{reverse(name)}"' in html, name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src && uv run pytest tests/test_admin.py::test_admin_index_has_quick_start -v`
Expected: FAIL — `assert "Быстрый старт" in html`.

- [ ] **Step 3: Новый `dashboard_help.html`**

```django
{% url 'admin_help' as help_url %}
<section class="mb-8 rounded-default border border-base-200 bg-white p-5 dark:border-base-800 dark:bg-base-900" aria-label="Быстрый старт">
  <h2 class="mb-2 font-semibold text-font-important-light dark:text-font-important-dark">Быстрый старт</h2>
  <p class="mb-4">Впервые здесь? Начните со <a href="{{ help_url }}" class="text-primary-600 underline dark:text-primary-500">справки</a>: как устроен сайт, что где править и <a href="{{ help_url }}#not-visible" class="text-primary-600 underline dark:text-primary-500">почему что-то не видно на сайте</a>.</p>
  <div class="flex flex-wrap gap-2">
    <a href="{% url 'admin:catalog_service_add' %}" class="inline-flex items-center rounded-default border border-base-200 px-3 py-2 font-semibold hover:text-primary-600 dark:border-base-700">Добавить услугу</a>
    <a href="{% url 'admin:content_event_add' %}" class="inline-flex items-center rounded-default border border-base-200 px-3 py-2 font-semibold hover:text-primary-600 dark:border-base-700">Добавить мероприятие</a>
    <a href="{% url 'admin:content_review_add' %}" class="inline-flex items-center rounded-default border border-base-200 px-3 py-2 font-semibold hover:text-primary-600 dark:border-base-700">Добавить отзыв</a>
    <a href="{% url 'admin:content_galleryphoto_bulk_upload' %}" class="inline-flex items-center rounded-default border border-base-200 px-3 py-2 font-semibold hover:text-primary-600 dark:border-base-700">Загрузить фото в галерею</a>
    <a href="{% url 'admin:core_sitesettings_changelist' %}" class="inline-flex items-center rounded-default border border-base-200 px-3 py-2 font-semibold hover:text-primary-600 dark:border-base-700">Настройки сайта</a>
  </div>
</section>
```

Проверить, что `hover:text-primary-600` есть в CSS Unfold: `grep -c 'hover\\:text-primary-600' src/.venv/lib/python3.14/site-packages/unfold/static/unfold/css/styles.css` — если 0, заменить на `hover:text-primary-700`.

В `src/templates/admin/index.html` поправить комментарий: «+ быстрый старт со ссылкой на справку (admin/dashboard_help.html)».

- [ ] **Step 4: Run tests**

Run: `cd src && uv run pytest tests/test_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/templates/admin/dashboard_help.html src/templates/admin/index.html src/tests/test_admin.py
git commit -m "Главная админки: быстрый старт со ссылкой на справку

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Подсказки у полей и исправление неточных подсказок

**Files:**
- Modify: `src/apps/catalog/models.py`, `src/apps/content/models.py`, `src/apps/core/models.py`, `src/apps/texts/registry.py`
- Create: миграции `catalog/00NN_help_texts.py`, `content/00NN_help_texts.py`, `core/0020_help_texts.py` (генерируются)
- Test: `src/tests/test_admin_help.py`

**Interfaces:** нет новых.

- [ ] **Step 1: Write the failing tests**

```python
from django.core.management import call_command

from apps.catalog.models import Category, CategoryGroup, Service
from apps.content.models import GalleryPhoto, Partner, Review
from apps.core.models import InfoPage, Phone, SiteSettings
from apps.texts.registry import BY_KEY


def _help(model, field):
    return str(model._meta.get_field(field).help_text)


def test_fields_explain_where_they_show():
    assert "без даты" in _help(Review, "date")
    assert "кружок" in _help(Review, "photo")
    assert "без обрезки" in _help(Partner, "logo")
    assert "плитка" in _help(Partner, "name")
    assert "квадрат" in _help(GalleryPhoto, "image")
    assert "весь экран" in _help(GalleryPhoto, "caption")
    assert "только у одного" in _help(Phone, "is_whatsapp")
    assert "только у одного" in _help(Phone, "is_telegram")
    assert "Связаться" in _help(Phone, "number")
    assert "подвале" in _help(InfoPage, "is_published")
    assert "меню «Услуги»" in _help(CategoryGroup, "name")
    assert "под заголовком" in _help(Category, "description")
    assert "подвал" in _help(SiteSettings, "address")
    assert "поисковиков" in _help(SiteSettings, "home_intro")


def test_fixed_hints_match_site():
    assert "главной" in _help(SiteSettings, "reviews_url")
    assert "подвале" in _help(SiteSettings, "safety_page")
    assert "прямой ссылке" in _help(Service, "is_published")
    assert "Отзывы" in BY_KEY["common.photo_strip_title"].where


def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src && uv run pytest tests/test_admin_help.py -k "explain_where or fixed_hints or missing_migrations" -v`
Expected: `test_fields_explain_where_they_show` и `test_fixed_hints_match_site` — FAIL (`assert 'без даты' in ''`); `test_no_missing_migrations` — PASS (пока моделей не трогали).

- [ ] **Step 3: `src/apps/catalog/models.py`**

```python
class CategoryGroup(OrderedModel):
    name = models.CharField(
        "Название", max_length=128, help_text="Заголовок раздела в меню «Услуги» в шапке и блока на главной."
    )
    categories = models.ManyToManyField(
        "Category",
        related_name="groups",
        blank=True,
        verbose_name="Категории",
        help_text="Одна категория может быть в нескольких группах.",
    )
    is_published = models.BooleanField(
        "Опубликовано",
        default=True,
        help_text="Снятая — группа и её категории пропадут из меню и с главной; страницы категорий открываются.",
    )
```

`Category.description`:

```python
    description = HtmlField(
        "Описание",
        help_text="Текст под заголовком страницы категории. Если на вкладке «SEO» описание пустое — идёт и в поиск.",
    )
```

`Service.is_published` (заменить help_text):

```python
    is_published = models.BooleanField(
        "Опубликовано",
        default=True,
        help_text=(
            "В списках услуга видна только внутри опубликованной категории; "
            "отдельная страница открывается и по прямой ссылке."
        ),
    )
```

- [ ] **Step 4: `src/apps/content/models.py`**

```python
class Review(models.Model):
    ...
    date = models.DateField(
        "Дата отзыва",
        null=True,
        blank=True,
        help_text="От неё зависит порядок: новые сверху, без даты — в конце. «Подтянуть» заполнит её сама.",
    )
    photo = photo_field(
        "Фото",
        "reviews",
        help_text="Маленький кружок рядом с подписью «Гость Т-Парка», кадр обрезается до квадрата. Необязательно.",
    )
    ...
    is_published = models.BooleanField("Опубликовано", default=True, help_text="Снимите, чтобы скрыть отзыв на сайте.")


class Partner(OrderedModel):
    name = models.CharField(
        "Название",
        max_length=128,
        blank=True,
        help_text="Описание логотипа для поисковиков; без логотипа на сайте будет плитка с этим названием.",
    )
    link = models.URLField(
        "Ссылка", max_length=500, blank=True, help_text="Откроется в новой вкладке. Пусто — логотип без ссылки."
    )
    logo = photo_field(
        "Логотип",
        "partners",
        size=(800, 800),
        fmt=None,
        help_text="На «О нас» — целиком, без обрезки. Лучше PNG с прозрачным или белым фоном.",
    )


class GalleryPhoto(OrderedModel):
    ...
    image = photo_field(
        "Фото", "gallery", blank=False, help_text="В галерее — квадратом с обрезкой краёв, по клику — целиком."
    )
    caption = models.CharField(
        "Подпись",
        max_length=255,
        blank=True,
        help_text="Видна при просмотре фото на весь экран и описывает фото для поисковиков.",
    )
```

- [ ] **Step 5: `src/apps/core/models.py`**

`SiteSettings`:

```python
    address = models.CharField(
        "Адрес",
        max_length=255,
        blank=True,
        default=PARK_ADDRESS,
        help_text="Главная, подвал, «Контакты», «О нас» и место мероприятий без своего адреса.",
    )
    vk_url = models.URLField(
        "ВКонтакте",
        max_length=500,
        blank=True,
        help_text="Кнопка в «Связаться», в подвале и на «Контактах». Пусто — кнопки нет.",
    )
    home_intro = HtmlField(
        "Вступление на главной",
        help_text="Текст в начале главной. Он же — описание сайта для поисковиков и соцсетей по умолчанию.",
    )
    events_intro = HtmlField("Вступление на странице мероприятий", help_text="Текст в начале страницы «Мероприятия».")
    contacts_text = HtmlField("Текст на странице контактов", help_text="Блок текста внизу страницы «Контакты».")
    nearby_text = HtmlField("Что рядом", help_text="Блок «Что рядом» на «О нас»: достопримечательности, жильё, кафе.")
```

`reviews_url` (заменить help_text):

```python
        help_text=(
            "Страница отзывов о Т-Парке: кнопки «Все отзывы» и «Оставить отзыв» на страницах отзывов и контактов "
            "и ссылка «Оставить отзыв» на главной. Пусто — кнопок нет."
        ),
```

`safety_page` (заменить help_text):

```python
        help_text="Инфо-страница, на которую ведут плашка «Правила безопасности» на «О нас» и ссылка в подвале.",
```

`Phone`:

```python
    number = models.CharField(
        "Номер",
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", "10 цифр без +7 и 8, например 9029856594.")],
        help_text="10 цифр без +7, 8 и пробелов. Первый номер — главный в кнопке «Связаться».",
    )
    is_whatsapp = models.BooleanField(
        "WhatsApp", default=False, help_text="Кнопка WhatsApp ведёт на этот номер. Можно отметить только у одного."
    )
    is_telegram = models.BooleanField(
        "Telegram", default=False, help_text="Кнопка Telegram ведёт на этот номер. Можно отметить только у одного."
    )
```

`InfoPage`:

```python
    body = HtmlField("Текст", help_text="Заголовки, списки и ссылки — кнопками редактора.")
    is_published = models.BooleanField(
        "Опубликовано",
        default=True,
        help_text="Снятая — страница не откроется, ссылок на неё в подвале и на «О нас» не будет.",
    )
```

Перед правкой `contacts_text` проверить, где он на странице: `grep -n "contacts_text" src/templates/content/contacts.html` — если не внизу, поправить «внизу» на фактическое место. Перед правкой `PhoneInline`: у табличного инлайна подсказки показываются иконкой у заголовка колонки — проверить на dev-сервере (задача 8).

- [ ] **Step 6: `src/apps/texts/registry.py`** — `common.photo_strip_title`, поле «где на сайте»:

```python
        "Главная, «О нас» и «Отзывы», полоса фото со ссылкой на галерею",
```

(Поле `where` берётся из реестра при показе, в базе не хранится — миграция не нужна. Проверить: `grep -n "where" src/apps/texts/models.py` — должно быть пусто.)

- [ ] **Step 7: Миграции**

Run: `cd src && uv run manage.py makemigrations catalog content core -n help_texts`
Expected: три файла `*_help_texts.py` только с `AlterField`. Проверить: `git diff --stat` и `grep -c "AlterField" src/apps/*/migrations/*_help_texts.py`; других операций быть не должно.

- [ ] **Step 8: Run tests**

Run: `cd src && uv run pytest tests/test_admin_help.py tests/test_admin.py tests/test_texts.py tests/test_core_models.py -v`
Expected: PASS. Если упал `tests/test_texts.py::test_registry_matches_templates` — реестр сверяется только по ключам, `where` не влияет; искать причину в опечатке строки.

- [ ] **Step 9: Commit**

```bash
git add src/apps src/tests/test_admin_help.py
git commit -m "Подсказки у полей отзывов, партнёров, галереи, телефонов, инфо-страниц и настроек

Исправлены подсказки, расходившиеся с сайтом: ссылка на отзывы, правила безопасности,
публикация услуги, полоса фото.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Документация, полная проверка, просмотр на dev-сервере

**Files:**
- Modify: `CLAUDE.md` (раздел Architecture)
- Modify: `docs/decisions.md` (раздел «Админка (согласовано)», таблица решений — следующий номер)

- [ ] **Step 1: `CLAUDE.md`** — после пункта про главную админки (`templates/admin/index.html`) добавить:

```markdown
- Справка админки — `/admin/help/` (`apps/core/admin_help.py`: `HELP_SECTIONS`, по шаблону на раздел в `templates/admin/help/sections/`, стили — `static/css/admin_help.css`), пункт «Справка» вверху бокового меню. Над списками — вводная `help_intro` и ссылка на раздел `help_anchor`, над формами — «Справка по разделу» (атрибуты `SiteModelAdmin`, шаблоны `admin/help/list_intro.html`, `form_link.html`); тест требует их у каждого раздела бокового меню. Меняешь поведение, заметное администратору (публикация, фото, порядок, новые поля и разделы), — обнови раздел справки, вводную и `help_text`.
```

И в описании `index.html` заменить «инструкция `admin/dashboard_help.html`» на «быстрый старт `admin/dashboard_help.html`».

- [ ] **Step 2: `docs/decisions.md`** — посмотреть последний номер решения (`grep -n "^| [0-9]" docs/decisions.md | tail -1`) и добавить строку со следующим номером в таблицу раздела «Админка»:

```markdown
| N | **Справка админки — шаблоны в git, одна страница `/admin/help/` с якорями, без скриншотов**; вводные над списками и ссылки из форм ведут в её разделы | Справка описывает поведение кода и меняется вместе с ним; редактируемая из админки — устарела бы молча; скриншоты устаревают при каждом обновлении Unfold |
```

- [ ] **Step 3: Полная проверка**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run manage.py makemigrations --check --dry-run`
Expected: все тесты PASS, ruff без замечаний, «No changes detected».

Из корня: `uv run --project src pre-commit run --all-files` — PASS.

- [ ] **Step 4: Просмотр на dev-сервере**

Run: `cd src && uv run manage.py tailwind runserver` (в фоне), войти суперпользователем и проверить:
1. `/admin/` — «Быстрый старт», пункт «Справка» вверху меню.
2. `/admin/help/` — оглавление, переходы по якорям, «↑ К оглавлению», таблицы; светлая и тёмная тема (переключатель темы Unfold); ширина 375 px (таблицы прокручиваются внутри, страница — нет).
3. Списки «Галерея», «Услуги», «Тексты сайта» — вводная и ссылка; «Тексты сайта» — ссылка на настройки рабочая.
4. Формы «Услуга», «Настройки сайта», «Пользователь» — «Справка по разделу» ведёт в нужный раздел.
5. Форма «Настройки сайта» → блок телефонов: подсказки WhatsApp/Telegram видны. Форма пользователя: подпись ссылки смены пароля совпадает с текстом раздела «Доступ и вход» — иначе поправить `sections/access.html`.

Найденные расхождения — исправить, перезапустить `uv run pytest tests/test_admin_help.py`.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/decisions.md src
git commit -m "Справка админки: документация и правило поддержки

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
