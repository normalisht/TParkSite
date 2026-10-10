# Исправления по UX-аудиту: план по этапам

> **Для агентов-исполнителей:** ОБЯЗАТЕЛЬНЫЙ НАВЫК: superpowers:subagent-driven-development (рекомендуется) или superpowers:executing-plans — задачи выполняются по одной. Шаги отмечаются чекбоксами (`- [ ]`).

**Цель:** устранить недостатки из UX-аудита: сначала то, что ломает мобильную версию, затем доступность и скорость, конверсию, юридические требования и развитие.

**Архитектура:** почти все правки касаются шаблонов (`src/templates/`), `tailwind/source.css` и `static/js/site.js`. Новые данные (MAX, политика, место мероприятия) — поля `SiteSettings`/`Event` с миграциями и вкладками в админке, по образцу уже существующих (`safety_page`, `FounderFact`). Новых зависимостей в рантайме нет; для браузерной проверки вёрстки добавляется необязательная группа `e2e` (Playwright).

**Стек:** Python 3.14, Django 6.1, Tailwind 4 (`django-tailwind-cli`), Alpine, Swiper 12, GLightbox, django-imagekit, pytest + pytest-django; для e2e — pytest-playwright.

**Спецификация:** `docs/ux-audit-2026-10-10.md` (номера пунктов ниже — оттуда). Правила проекта — `CLAUDE.md`.

## Как устроен план

| Этап | Что | Детализация |
|---|---|---|
| **1. Мобильная вёрстка** | п. 1–3, переносы «Т-Парк», Swiper, skip-link, фокус, reduced motion | Полная: код и тесты |
| **2. Доступность и скорость** | цели нажатия, «Прошло», цена с единицей, `srcset`, «Ещё в категории» | Полная: код и тесты |
| **3. Конверсия** | WhatsApp с текстом, цели Метрики, VK и MAX в кнопках связи, сетка категорий (п. 5) | Полная: код и тесты |
| **4. Доверие и юридическое** | политика конфиденциальности, уведомление о cookie, подвал | Задачи, поля и тесты; текст политики — от владельца |
| **5. Развитие** | меню «Услуги» на ПК, галерея, место мероприятия, «О нас», «Другие категории» | Задачи и подход |
| **К. Контент (админка)** | фото, тексты, бренд, дубли | Чек-лист для администратора, без кода |

Решения владельца — в конце плана. Каждый этап — отдельная ветка и отдельный мерж.

## Глобальные ограничения

- Весь пользовательский текст — на русском. Название бренда в тексте — «Т-Парк» (кириллица, дефис, «П» заглавная).
- Админки наследуются от `apps.core.admin_utils.SiteModelAdmin`.
- Миниатюры в шаблонах — только через `obj|spec_url:"spec"`.
- Серый текст — только `text-ink/75` и `text-ink/65` (тест `test_no_low_contrast_gray_text`).
- Оранжевый (brand) — только кликабельное; зелёный (pine) — «природа и место»; navy — информационные иконки.
- Комментарии `{# … #}` — однострочные; длинные — `{% comment %}`.
- Фронт без Node и CDN; vendored-JS без `sourceMappingURL`.
- Стили, которые должны перебить vendored-CSS (Swiper, GLightbox), пишутся **без слоя** в `tailwind/source.css`; общие компоненты — в `@layer components`. Правило без слоя перебивает и утилиты Tailwind — использовать только там, где это и нужно.
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Перед коммитом: `uv run pytest` зелёный, `uv run ruff check .` чистый. После правки шаблонов — пересобрать CSS: `uv run manage.py tailwind build`.

## Что тесты не ловят — проверять глазами

1. **Ширина 320 px с реальным контентом.** Длинные названия категорий, адрес, ссылки в отзывах. e2e-тест (задача 1.1) проверяет на синтетике; после каждого этапа прогнать его на копии `current_content/` (шаг в задаче 1.6).
2. **Открытое мобильное меню + плавающая кнопка + баннер cookie** (после этапа 4): ни один слой не закрывает другой, Escape и клик по затемнению закрывают меню.
3. **Шапка на 1024 px** с телефоном и кнопкой «Написать»: пункты меню не переносятся, логотип не сжимается.
4. **Слайдер на светлом фото**: стрелки и точки видны; на тёмном — не кричат.
5. **iOS Safari**: `overflow-x: clip` не ломает `position: sticky` у шапки и карточки цены (проверить на живом устройстве — в аудите эмуляция).

---

## Этап 1. Мобильная вёрстка (критичное)

Ветка: `fix/mobile-layout`.

### Задача 1.1. e2e-тест «нет горизонтальной прокрутки»

Сторож для задач 1.2–1.3: открывает страницы в Chromium на 320 и 375 px и ищет элементы, вылезающие за правый край. Ленты со свайпом (`overflow-x: auto`) и обрезанные контейнеры не считаются. Тест опциональный: без группы `e2e` он пропускается.

**Файлы:**
- Изменить: `src/pyproject.toml` (группа `e2e`), `Makefile` (цель `e2e`)
- Создать: `src/tests/e2e/__init__.py`, `src/tests/e2e/test_mobile_layout.py`

- [ ] **Шаг 1: добавить зависимость**

```bash
cd src
uv add --group e2e pytest-playwright
uv run --group e2e playwright install chromium
```

Группа `dev` по умолчанию её не тянет: обычный `uv sync`/`uv run pytest` не меняются.

- [ ] **Шаг 2: написать тест**

`src/tests/e2e/__init__.py` — пустой. `src/tests/e2e/test_mobile_layout.py`:

```python
"""Вёрстка в настоящем браузере: на узких экранах ничего не вылезает за правый край.

Запуск: `make e2e` (нужны `uv sync --group e2e`, `uv run --group e2e playwright install chromium`
и собранный CSS: `uv run manage.py tailwind build`).
"""

import os
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

pytest.importorskip("playwright")

from apps.catalog.models import Category, CategoryGroup, CategoryService, Service  # noqa: E402
from apps.content.models import Event, Review  # noqa: E402
from apps.core.models import Phone, SiteSettings  # noqa: E402

# Playwright держит в потоке теста event loop — без этого ORM в фикстурах падает с SynchronousOnlyOperation.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.django_db(transaction=True)

WIDTHS = [320, 375]

# Элементы, правый край которых за пределами экрана, кроме лежащих внутри прокручиваемых/обрезанных контейнеров.
FIND_OVERFLOW = """
() => {
  const vw = document.documentElement.clientWidth;
  const found = [];
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.right <= vw + 1) continue;
    let p = el.parentElement, clipped = false;
    while (p && p !== document.body) {
      if (getComputedStyle(p).overflowX !== "visible") { clipped = true; break; }
      p = p.parentElement;
    }
    if (!clipped) found.push(`${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 5).join(".")} +${Math.round(r.right - vw)}px`);
  }
  return found;
}
"""


@pytest.fixture(autouse=True)
def built_css():
    if not (Path(settings.BASE_DIR) / "static/css/tailwind.css").exists():
        pytest.skip("Нет static/css/tailwind.css: uv run manage.py tailwind build")


@pytest.fixture
def content():
    """Худший случай для узкого экрана: длинные заголовки, адрес, ссылка у отзыва, цена с единицей."""
    site = SiteSettings.load()
    site.latitude, site.longitude = 55.0, 36.5
    site.opening_hours = "Mo-Su 10:00-18:00"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True, is_telegram=True)
    group = CategoryGroup.objects.create(name="Групповые приключения")
    category = Category.objects.create(name="Корпоративные мероприятия и тимбилдинг", is_published=True)
    group.categories.add(category, Category.objects.create(name="Сплавы", is_published=True))
    service = Service.objects.create(
        name="Виа-феррата", price="1000", price_unit="10 выстрелов", has_page=True, description="<p>Текст</p>"
    )
    other = Service.objects.create(name="Скалодром", price="500", price_unit="человек", has_page=True)
    for order, item in enumerate([service, other]):
        CategoryService.objects.create(category=category, service=item, order=order)
    today = timezone.localdate()
    events = [
        Event.objects.create(title=f"Инструкторы для детского туристического клуба {i}", date=today + timedelta(days=i))
        for i in range(1, 4)
    ]
    Review.objects.create(
        text="<p>Очень понравилось! https://yandex.ru/maps/org/t_park/1234567890/reviews/?utm_source=share</p>",
        link="https://yandex.ru/maps/org/t_park/1234567890/reviews/",
        date=today,
    )
    return {"category": category, "service": service, "event": events[0]}


@pytest.mark.xfail(strict=True, reason="Переполнение на телефоне — исправляется в задачах 1.2–1.3")
@pytest.mark.parametrize("width", WIDTHS)
def test_no_horizontal_overflow(live_server, browser, content, width):
    pages = [
        "/",
        "/contacts/",
        "/reviews/",
        "/events/",
        content["category"].get_absolute_url(),
        content["service"].get_absolute_url(),
        content["event"].get_absolute_url(),
    ]
    context = browser.new_context(
        viewport={"width": width, "height": 800}, device_scale_factor=3, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    problems = {}
    for url in pages:
        page.goto(live_server.url + url)
        page.wait_for_load_state("networkidle")
        if found := page.evaluate(FIND_OVERFLOW):
            problems[url] = found
    context.close()
    assert problems == {}
```

- [ ] **Шаг 3: цель в Makefile** (после `check:`)

```make
e2e: ## Браузерные тесты вёрстки (Playwright; один раз: cd src && uv sync --group e2e && uv run --group e2e playwright install chromium)
	cd $(SRC) && uv run manage.py tailwind build && uv run --group e2e pytest tests/e2e $(ARGS)
```

И добавить `e2e` в `.PHONY`.

- [ ] **Шаг 4: прогнать и записать, что вылезает**

Run: `make e2e ARGS="-rxX --runxfail"`
Ожидаемо: FAIL; в выводе — словарь «страница → элементы». Сверить с аудитом (главная и мероприятие — заголовок секции со ссылкой; контакты — кнопка «Скопировать»; отзывы — карточка). Если в списке есть что-то ещё — добавить в задачу 1.2.

- [ ] **Шаг 5: убедиться, что обычный прогон не задет**

Run: `cd src && uv run pytest`
Ожидаемо: PASS, `tests/e2e` — skipped (нет playwright в группе dev).

- [ ] **Шаг 6: коммит**

```bash
git add src/pyproject.toml src/uv.lock Makefile src/tests/e2e
git commit -m "e2e: тест горизонтального переполнения на 320/375 px"
```

### Задача 1.2. Убрать переполнение (п. 1)

**Файлы:**
- Изменить: `src/templates/catalog/home.html:45,57`, `src/templates/content/event.html:59`, `src/templates/catalog/service.html:37`, `src/templates/content/contacts.html:58-68`, `src/templates/content/partials/review_card.html:3,17`, `src/tailwind/source.css`
- Создать: `src/tests/test_layout.py`
- Тест: `src/tests/e2e/test_mobile_layout.py` (снять `xfail`)

- [ ] **Шаг 1: тест-линтер шаблонов**

`src/tests/test_layout.py`:

```python
"""Правила вёрстки, которые проверяются по исходникам шаблонов (браузерная проверка — tests/e2e)."""

import re
from pathlib import Path

from django.conf import settings

TEMPLATES = Path(settings.BASE_DIR) / "templates"

# Шапка секции «Заголовок … ссылка справа»: без flex-wrap длинный заголовок выталкивает ссылку за край экрана.
SECTION_HEAD = re.compile(r'<div class="(mb-4 flex [^"]*justify-between[^"]*)">\s*<h2')


def test_section_heads_wrap_on_narrow_screens():
    heads = [
        (path.relative_to(TEMPLATES), match.group(1))
        for path in TEMPLATES.rglob("*.html")
        for match in SECTION_HEAD.finditer(path.read_text())
    ]
    assert heads, "шаблон шапки секции не найден — обновите регулярку"
    assert [(path, cls) for path, cls in heads if "flex-wrap" not in cls] == []
```

- [ ] **Шаг 2: убедиться, что падает**

Run: `cd src && uv run pytest tests/test_layout.py -v`
Ожидаемо: FAIL — четыре шапки без `flex-wrap` (home ×2, event, service).

- [ ] **Шаг 3: шапки секций**

Во всех четырёх местах заменить

```html
<div class="mb-4 flex items-end justify-between gap-4 md:mb-6">
```

на

```html
<div class="mb-4 flex flex-wrap items-end justify-between gap-x-4 gap-y-2 md:mb-6">
```

и добавить `min-w-0` заголовку `<h2 …>` в этих блоках. В блоке отзывов на главной (`home.html:59`) у обёртки ссылок убрать `shrink-0`.

- [ ] **Шаг 4: контакты — кнопка «Скопировать» под текстом на узком экране**

`contacts.html`, строки адреса и координат:

```html
<div class="mt-1 flex flex-col items-start gap-3 sm:flex-row">
  <p class="flex min-w-0 flex-1 gap-2 text-lg font-semibold"><span class="icon mt-1 h-5 w-5 text-pine-700">{% include "icons/map-pin.svg" %}</span>{{ site.address }}</p>
  {% include "partials/copy_button.html" with value=site.address %}
</div>
```

```html
<div class="mt-1 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
  <p class="min-w-0 flex-1 font-mono text-lg">{{ route.coordinates }}</p>
  {% include "partials/copy_button.html" with value=route.coordinates %}
</div>
```

- [ ] **Шаг 5: отзывы — длинные ссылки и подпись**

`tailwind/source.css`, в `@layer components`:

```css
  .rich-text { @apply leading-relaxed text-ink/85; overflow-wrap: anywhere; }
```

(вместо текущей строки `.rich-text { … }` — длинный URL в тексте переносится, а не распирает карточку или колонку сетки).

`review_card.html:3` — паддинг меньше на телефоне: `p-6` → `p-5 sm:p-6`.
`review_card.html:17` — строку «Яндекс Карты · дата» сделать переносимой: `<p class="text-sm text-ink/65">` → `<p class="flex flex-wrap items-center gap-x-1 text-sm text-ink/65">`.

- [ ] **Шаг 6: подстраховка**

`tailwind/source.css`, рядом с `html { scrollbar-gutter: stable; }`:

```css
/* Подстраховка от горизонтальной прокрутки на телефоне. clip, а не hidden: не создаёт контейнер прокрутки и не ломает sticky. */
body { overflow-x: clip; }
```

e2e-тест от этого не «ослепнет»: он ищет элементы за краем по координатам, а не по `scrollWidth`.

- [ ] **Шаг 7: тесты**

Run: `cd src && uv run pytest tests/test_layout.py -v` → PASS.
Run: `make e2e` → тест XPASS(strict) = FAIL; это сигнал, что всё исправлено. Удалить строку `@pytest.mark.xfail(...)` в `tests/e2e/test_mobile_layout.py` и прогнать снова → PASS.
Если e2e по-прежнему находит элементы — исправить их тем же способом (`flex-wrap`/`min-w-0`/`flex-col sm:flex-row`) и дописать сюда.

- [ ] **Шаг 8: коммит**

```bash
git add src/templates src/tailwind/source.css src/tests/test_layout.py src/tests/e2e
git commit -m "Вёрстка: нет горизонтальной прокрутки на 320/375 px"
```

### Задача 1.3. Кнопка «Связаться»: не поверх меню, отступ снизу, телефон в шапке (п. 2, 3)

Решение: плавающая кнопка остаётся до 1024 px (`lg:hidden`, сейчас `md:hidden`) — на планшете она нужна; с 1024 px телефон и «Написать» — в шапке вместо строки «Тренинг-парк Дмитрия Сергеева».

**Файлы:**
- Изменить: `src/templates/partials/header.html:3,17`, `src/templates/partials/contact_button.html:3`, `src/templates/partials/footer.html:32`, `src/tailwind/source.css`
- Тест: `src/tests/test_pages_home.py`

- [ ] **Шаг 1: тесты**

В `tests/test_pages_home.py`:

```python
def _header(html: str) -> str:
    return html.split("<header", 1)[1].split("</header>", 1)[0]


def test_header_shows_phone_on_desktop(client):
    site = SiteSettings.load()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    header = _header(client.get("/").content.decode())
    assert 'href="tel:+79029856594"' in header
    assert "+7 (902) 985-65-94" in header
    assert "https://wa.me/79029856594" in header
    assert "Тренинг-парк Дмитрия Сергеева" not in header


def test_contact_button_yields_to_menu_and_footer(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    html = client.get("/").content.decode()
    fab = re.search(r'<div [^>]*class="(contact-fab [^"]*)"', html).group(1)
    assert "lg:hidden" in fab and "md:hidden" not in fab
    # Меню помечает <html> классом menu-open — по нему кнопка прячется (tailwind/source.css).
    assert "toggle('menu-open', open)" in html
    # Подвал не прячется под кнопкой: снизу место под неё, на ПК — обычный отступ.
    assert "pb-20 lg:pb-5" in html.split("<footer", 1)[1]
```

Run: `cd src && uv run pytest tests/test_pages_home.py -k "header_shows_phone or contact_button_yields" -v` → FAIL.

- [ ] **Шаг 2: шапка**

`header.html:3`:

```html
        x-effect="document.documentElement.classList.toggle('overflow-hidden', open); document.documentElement.classList.toggle('menu-open', open)"
```

`header.html:17` — вместо `<p …>Тренинг-парк Дмитрия Сергеева</p>`:

```html
    {% if phones %}
    <div class="hidden shrink-0 items-center gap-3 lg:flex">
      <a href="{{ phones.0.tel_url }}" class="inline-flex items-center gap-2 whitespace-nowrap text-sm font-semibold tabular-nums hover:text-brand-700"><span class="icon h-4 w-4 text-navy">{% include "icons/phone.svg" %}</span>{{ phones.0.display }}</a>
      {% if whatsapp_phone %}<a href="{{ whatsapp_phone.whatsapp_url }}" class="btn btn-primary py-2" target="_blank" rel="noopener">Написать</a>{% endif %}
    </div>
    {% endif %}
```

- [ ] **Шаг 3: плавающая кнопка**

`contact_button.html:3`: `class="fixed bottom-4 right-4 z-50 flex flex-col items-end md:hidden"` → `class="contact-fab fixed bottom-4 right-4 z-50 flex flex-col items-end lg:hidden"`.

`tailwind/source.css`, без слоя (утилита `flex` из слоя utilities иначе победит):

```css
/* Открыто мобильное меню (класс на <html> ставит partials/header.html) — плавающая «Связаться» не закрывает его пункты. */
html.menu-open .contact-fab { display: none; }
```

- [ ] **Шаг 4: отступ в подвале**

`footer.html:32`:

```html
    <p class="mx-auto max-w-6xl px-4 pt-5 text-sm text-white/70 {% if phones %}pb-20 lg:pb-5{% else %}pb-5{% endif %}">© {% now "Y" %} Т-Парк</p>
```

- [ ] **Шаг 5: тесты и проверка глазами**

Run: `cd src && uv run pytest` → PASS. `make e2e` → PASS.
Глазами (`make run`): 375 px — открыть меню, кнопки «Связаться» нет; закрыть — есть; долистать до низа — телефоны подвала не закрыты. 800 px — кнопка есть. 1024 и 1440 px — в шапке телефон и «Написать», пункты меню в одну строку.

- [ ] **Шаг 6: коммит**

```bash
git add src/templates/partials src/tailwind/source.css src/tests/test_pages_home.py
git commit -m "Связаться: телефон в шапке на ПК, кнопка не перекрывает меню и подвал"
```

### Задача 1.4. Бренд без переноса по дефису

Фильтр `nobr` оборачивает «Т-Парк…» и «Тренинг-парк…» в `<span class="whitespace-nowrap">`. Применяется к строкам из шаблонов; HTML из админки (`rich-text`) не трогаем — там регулярка задела бы атрибуты.

**Файлы:**
- Изменить: `src/apps/core/templatetags/site_tags.py`, `src/templates/partials/cta_card.html:5-6`, `src/templates/partials/review_cta.html:7`, `src/templates/content/reviews.html:9`, `src/templates/catalog/home.html:9,91`
- Тест: `src/tests/test_core_helpers.py`

- [ ] **Шаг 1: тест**

```python
from apps.core.templatetags.site_tags import nobr


def test_nobr_keeps_brand_on_one_line():
    assert nobr("Своё событие в Т-Парке") == 'Своё событие в <span class="whitespace-nowrap">Т-Парке</span>'
    assert nobr("Тренинг-парк Дмитрия") == '<span class="whitespace-nowrap">Тренинг-парк</span> Дмитрия'


def test_nobr_escapes_html():
    assert nobr("<b>Т-Парк</b>") == '&lt;b&gt;<span class="whitespace-nowrap">Т-Парк</span>&lt;/b&gt;'
```

Run: `cd src && uv run pytest tests/test_core_helpers.py -k nobr -v` → FAIL (ImportError).

- [ ] **Шаг 2: фильтр**

`site_tags.py` (импорты `re` и `from django.utils.html import conditional_escape` — наверх):

```python
_BRAND = re.compile(r"(?:Т-Парк|Тренинг-парк)[а-яё]*", re.IGNORECASE)


@register.filter(needs_autoescape=True)
def nobr(value, autoescape=True) -> str:
    """«Т-Парк», «Тренинг-парк» в любом падеже — без переноса по дефису (иначе «Т-/Парке» на телефоне)."""
    text = conditional_escape(value) if autoescape else str(value)
    return mark_safe(_BRAND.sub(lambda m: f'<span class="whitespace-nowrap">{m.group(0)}</span>', text))
```

- [ ] **Шаг 3: применить**

- `cta_card.html`: `{{ title }}` → `{{ title|nobr }}`, `{{ text }}` → `{{ text|nobr }}`; в начале файла `{% load site_tags %}`.
- `review_cta.html:7`, `reviews.html:9`, `home.html:91`: «Т-Парк…» в тексте шаблона — обернуть вручную: `<span class="whitespace-nowrap">Т-Парка</span>`.
- `home.html:9`: `<span class="whitespace-nowrap">Тренинг-парк</span> Дмитрия Сергеева`.

- [ ] **Шаг 4: тесты и коммит**

Run: `cd src && uv run pytest` → PASS.

```bash
git add src/apps/core/templatetags/site_tags.py src/templates src/tests/test_core_helpers.py
git commit -m "«Т-Парк» не переносится по дефису"
```

### Задача 1.5. Слайдер в цветах сайта; skip-link, фокус, reduced motion

**Файлы:**
- Изменить: `src/tailwind/source.css`, `src/templates/catalog/partials/slider.html:12-13`, `src/templates/base.html:2,31-33`
- Тест: `src/tests/test_layout.py`

- [ ] **Шаг 1: тесты**

В `tests/test_layout.py` (`import pytest` — к остальным импортам в начале файла):

```python

@pytest.mark.django_db
def test_skip_link_and_reduced_motion(client):
    html = client.get("/").content.decode()
    assert '<html lang="ru" class="motion-safe:scroll-smooth">' in html
    body = html.split("<body", 1)[1]
    # Ссылка «Перейти к содержимому» — первый фокусируемый элемент страницы.
    assert body.index('href="#content"') < body.index("<header")
    assert '<main id="content" tabindex="-1"' in html


def test_slider_uses_brand_colors():
    css = (Path(settings.BASE_DIR) / "tailwind/source.css").read_text()
    assert "--swiper-theme-color: var(--color-brand-500)" in css
```

Run → FAIL.

- [ ] **Шаг 2: base.html**

```html
<html lang="ru" class="motion-safe:scroll-smooth">
```

```html
<body class="flex min-h-screen flex-col bg-white font-sans text-ink antialiased">
  <a href="#content" class="btn btn-primary sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60]">Перейти к содержимому</a>
  {% include "partials/header.html" %}
  <main id="content" tabindex="-1" class="flex-1 outline-none">{% block content %}{% endblock %}</main>
```

- [ ] **Шаг 3: фокус**

`tailwind/source.css`, в `@layer base` (рядом с правилом курсора):

```css
  /* Заметный фокус с клавиатуры в цвет бренда; у .card-link своё кольцо (утилиты перебивают base). */
  :focus-visible { outline: 3px solid var(--color-brand-500); outline-offset: 2px; }
```

- [ ] **Шаг 4: слайдер**

`tailwind/source.css`, без слоя (иначе vendored-CSS Swiper перебьёт), рядом с правилами GLightbox:

```css
/* Слайдер фото: точки в цвет бренда, стрелки на тёмной подложке — видны и на светлых фото. */
.js-slider {
  --swiper-theme-color: var(--color-brand-500);
  --swiper-pagination-bullet-inactive-color: #fff;
  --swiper-pagination-bullet-inactive-opacity: 0.7;
  --swiper-navigation-size: 40px;
  --swiper-navigation-color: #fff;
}
.js-slider .swiper-button-prev,
.js-slider .swiper-button-next {
  padding: 11px;
  border-radius: 9999px;
  background-color: rgb(0 0 0 / 0.4);
}
```

`slider.html:12-13` — убрать `!text-white` (цвет теперь из `--swiper-navigation-color`).

- [ ] **Шаг 5: тесты и проверка**

Run: `cd src && uv run pytest` → PASS.
Глазами: категория со светлым фото — стрелки видны, активная точка оранжевая. Tab с начала страницы — первой появляется «Перейти к содержимому», Enter переводит фокус в `main`. В macOS «Уменьшить движение» — якорные ссылки прыгают без анимации.

- [ ] **Шаг 6: коммит**

```bash
git add src/tailwind/source.css src/templates src/tests/test_layout.py
git commit -m "Слайдер в цветах сайта, skip-link, заметный фокус, без плавной прокрутки при reduced motion"
```

### Задача 1.6. Приёмка этапа на реальном контенте

- [ ] `cd src && uv run manage.py tailwind build && uv run manage.py runserver` на копии `current_content/db.sqlite3`.
- [ ] e2e работает на своей тестовой БД, поэтому реальный контент — вручную в Chrome DevTools: 320, 375, 768, 1024, 1440 px, страницы из аудита. На каждой странице в консоли — функция `FIND_OVERFLOW` из `tests/e2e/test_mobile_layout.py`: результат `[]`. (`scrollWidth` после `overflow-x: clip` ничего не покажет.)
- [ ] Отметить в `docs/ux-audit-2026-10-10.md` пп. 1–3 как сделанные (строка «Сделано: <дата>, ветка»).
- [ ] `uv run --project src pre-commit run --all-files`, мерж ветки.

---

## Этап 2. Доступность и скорость

Ветка: `fix/a11y-perf`.

### Задача 2.1. Цели нажатия ≥ 44 px и бейдж «Прошло»

**Файлы:**
- Изменить: `src/templates/partials/header.html:19`, `src/templates/partials/footer.html:11-13,18,25`, `src/templates/partials/breadcrumbs.html:3`, `src/templates/content/partials/review_card.html:7`, `src/templates/content/partials/event_timing.html:1`
- Тест: `src/tests/test_layout.py`

- [ ] **Шаг 1: тест**

```python
@pytest.mark.django_db
def test_touch_targets_are_large_enough(client):
    from apps.core.models import Phone, SiteSettings

    site = SiteSettings.load()
    site.vk_url = "https://vk.com/tpark"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    html = client.get("/").content.decode()
    header = html.split("<header", 1)[1].split("</header>", 1)[0]
    assert re.search(r'<button type="button" class="[^"]*\bh-11 w-11\b[^"]*md:hidden"', header)  # бургер
    footer = html.split("<footer", 1)[1]
    assert footer.count("h-11 w-11") == 2  # иконки WhatsApp и VK
    assert "h-8 w-8" not in footer
    assert re.search(r'<a href="tel:\+79029856594" class="[^"]*\bmin-h-11\b', footer)
```

- [ ] **Шаг 2: правки**

- Бургер (`header.html:19`): `class="icon h-8 w-8 md:hidden"` → `class="-mr-2 flex h-11 w-11 items-center justify-center md:hidden"`, у `<svg class="burger …">` добавить `h-7 w-7`.
- Иконки соцсетей в подвале: `icon icon-fill h-8 w-8` → `icon icon-fill h-11 w-11 p-1.5`; у обёртки `mt-5 flex gap-4` → `mt-4 -ml-1.5 flex gap-2`.
- Ссылки разделов подвала (`footer.html:18`): `gap-y-2` → `gap-y-0`, `link_class="hover:text-brand-300"` → `link_class="inline-flex min-h-11 items-center hover:text-brand-300"`; так же у ссылки «Главная» в этой строке.
- Телефоны подвала (`footer.html:25`): у `<a>` добавить `min-h-11`, у `<ul>` `space-y-2` → `space-y-0`.
- Хлебные крошки: у `<a>` добавить `inline-block py-2.5 -my-2.5` (визуально как сейчас, область нажатия 37 px+ по высоте при `text-sm`; ближе к 44 не делаем — строки крошек сольются).
- «Читать полностью»: добавить `py-2 -my-2`.
- Бейдж (`event_timing.html`): `px-2.5 py-1 text-xs` → `px-3 py-1 text-sm`.

- [ ] **Шаг 3: тесты, проверка, коммит**

Run: `cd src && uv run pytest` → PASS; `make e2e` → PASS.
Глазами: подвал на 375 px не стал заметно выше (≤ +40 px), крошки не прыгают.

```bash
git add src/templates src/tests/test_layout.py
git commit -m "Доступность: цели нажатия 44 px, крупнее бейдж «Прошло»"
```

### Задача 2.2. Цена с единицей переносится без сдвига

Сейчас при переносе слеш скрыт через `visibility`, но его ширина остаётся — единица сдвинута вправо. Новое поведение: перенеслась — слеш убирается совсем (`display: none`), а единица становится блоком (всегда с новой строки, без отступа), поэтому «прыгнуть» обратно на первую строку не может. Перед замером атрибуты снимаются у всех цен сразу — одна перекомпоновка на все цены.

**Файлы:**
- Изменить: `src/templates/catalog/partials/price.html`, `src/static/js/site.js:111-118`
- Тест: `src/tests/test_pages.py:41-42`

- [ ] **Шаг 1: обновить тест**

`tests/test_pages.py:42`:

```python
    assert '<span class="js-price-unit inline-block data-wrapped:block"><span class="data-wrapped:hidden">/ </span>человек</span>' in html
```

Run: `cd src && uv run pytest tests/test_pages.py::test_category_page_lists_services` → FAIL.

- [ ] **Шаг 2: шаблон**

`price.html`:

```html
{# Цена и единица — неразрывные куски: перенос только по слешу; перенеслась единица — site.js (fitPrices) ставит data-wrapped: слеш убирается, единица с новой строки. #}
{% if service.price %}<span class="inline-block whitespace-nowrap">{{ service.price }} руб</span>{% if service.price_unit %} <span class="js-price-unit inline-block data-wrapped:block"><span class="data-wrapped:hidden">/ </span>{{ service.price_unit }}</span>{% endif %}{% endif %}
```

- [ ] **Шаг 3: site.js**

Вместо `fitPrices` (строки 111–118):

```js
  // Цена «1000 руб / 10 выстрелов»: если единица не влезла в строку, слеш убираем, а единицу ставим блоком с новой строки.
  // Сначала снимаем отметку у всех цен, потом меряем все разом — одна перекомпоновка, и сужение/расширение окна работает в обе стороны.
  const fitPrices = () => {
    const units = [...document.querySelectorAll(".js-price-unit")];
    units.forEach((unit) => unit.removeAttribute("data-wrapped"));
    const wrapped = units.map((unit) => unit.offsetTop > unit.previousElementSibling.offsetTop);
    units.forEach((unit, i) => unit.toggleAttribute("data-wrapped", wrapped[i]));
  };
```

- [ ] **Шаг 4: тесты, проверка, коммит**

Run: `cd src && uv run pytest` → PASS. Глазами: категория с ценой «1000 руб / 10 выстрелов» на 320 px — единица с новой строки ровно под ценой (с выравниванием строки справа — у правого края), без пустоты слева; расширить окно — вернулась в строку со слешем.

```bash
git add src/templates/catalog/partials/price.html src/static/js/site.js src/tests/test_pages.py
git commit -m "Цена: перенесённая единица без сдвига на ширину слеша"
```

### Задача 2.3. Миниатюры нужного размера в карточках услуг и слайдере

Карточка услуги на телефоне — строка с квадратом 112 px, с `sm` — карточка с фото 4:3. Разные пропорции → `<picture>` с `media` (art direction). Слайдер — `srcset` из `slide_small` 800×450 и `slide` 1600×900; `sizes` передаётся из страницы, т. к. ширина слайдера на категории и в услуге разная. Сверить с `docs/superpowers/plans/2026-10-09-avif-thumbnails.md`: если AVIF уже сделан — новые спецификации добавить и в AVIF-варианте.

**Файлы:**
- Изменить: `src/apps/catalog/models.py:72-73,144-146`, `src/templates/catalog/partials/service_card.html:4-9`, `src/templates/catalog/partials/slider.html:5-7`, `src/templates/catalog/category.html:41`, `src/templates/catalog/service.html:29`
- Тест: `src/tests/test_pages.py`

- [ ] **Шаг 1: тесты**

```python
def test_service_card_picture_and_slider_srcset(client, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True)
    service = Service.objects.create(name="Сплав", has_page=True)
    ServicePhoto.objects.create(service=service, image=make_image(size=(1600, 900)))
    CategoryPhoto.objects.create(category=category, image=make_image(size=(1600, 900)))
    CategoryService.objects.create(category=category, service=service)
    html = client.get(category.get_absolute_url()).content.decode()
    card = html.split("Услуги и цены</h2>")[1]
    # Телефон — квадрат row (336×336), с sm — card 640×480.
    assert '<picture><source media="(min-width: 640px)" srcset="' in card
    slider = html.split("js-slider")[1]
    assert re.search(r'srcset="[^"]+ 800w, [^"]+ 1600w" sizes="\(min-width: 1152px\) 1120px, calc\(100vw - 32px\)"', slider)
    html = client.get(service.get_absolute_url()).content.decode()
    assert 'sizes="(min-width: 1152px) 752px, (min-width: 1024px) calc(100vw - 400px), calc(100vw - 32px)"' in html
```

Run → FAIL. (В начале файла должен быть импорт `ServicePhoto`, `CategoryPhoto` — уже есть.)

- [ ] **Шаг 2: спецификации**

`apps/catalog/models.py`, у `CategoryPhoto` и у `ServicePhoto` после `slide`:

```python
    slide_small = image_spec("image", 800, 450, crop=False)  # слайдер на телефоне: srcset со slide
```

У `ServicePhoto` после `card`:

```python
    row = image_spec("image", 336, 336)  # квадрат в строке услуги на телефоне (112 px × 3)
```

`ImageSpecField` — не поле БД, миграция не нужна (проверить: `uv run manage.py makemigrations --check --dry-run` → «No changes»).

- [ ] **Шаг 3: карточка услуги**

`service_card.html:5-9`:

```html
    {% with url=service.cover|spec_url:"card" row=service.cover|spec_url:"row" %}{% if url %}
    <picture><source media="(min-width: 640px)" srcset="{{ url }}"><img src="{% firstof row url %}" alt="" width="640" height="480" loading="lazy" class="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105"></picture>
    {% else %}
```

- [ ] **Шаг 4: слайдер**

`slider.html:5-7`:

```html
    {% for photo in photos %}{% with url=photo|spec_url:"slide" small=photo|spec_url:"slide_small" %}{% if url %}
    <div class="swiper-slide" data-full="{{ photo.image.url }}">
      <img src="{{ url }}"{% if small %} srcset="{{ small }} 800w, {{ url }} 1600w" sizes="{{ sizes }}"{% endif %} alt="{{ alt }} — фото {{ forloop.counter }}" width="1600" height="900" class="aspect-[16/9] w-full cursor-zoom-in object-cover" {% if forloop.first %}fetchpriority="high"{% else %}loading="lazy"{% endif %}>
```

`category.html:41`: `with alt=category.name sizes="(min-width: 1152px) 1120px, calc(100vw - 32px)"`.
`service.html:29`: `with alt=service.name sizes="(min-width: 1152px) 752px, (min-width: 1024px) calc(100vw - 400px), calc(100vw - 32px)"` (контейнер 1120 − колонка 320 − зазор 48).

- [ ] **Шаг 5: тесты, проверка, коммит**

Run: `cd src && uv run pytest` → PASS.
Глазами (DevTools → Network, 375 px, DPR 3): на категории картинки строк услуг ~15–25 КБ, а не 640×480; в услуге первое фото слайдера — 800 px. Цель: категория на телефоне < 1 МБ (было 1,9 МБ).

```bash
git add src/apps/catalog/models.py src/templates/catalog src/tests/test_pages.py
git commit -m "Скорость: миниатюры под размер в строках услуг и слайдере"
```

### Задача 2.4. «Ещё в категории» без дублей названия

**Файлы:**
- Изменить: `src/apps/catalog/views.py:95`
- Тест: `src/tests/test_pages.py`

- [ ] **Шаг 1: тест**

```python
def test_service_related_skips_same_name_variants(client):
    category = Category.objects.create(name="Высота", is_published=True)
    services = [
        Service.objects.create(name=name, has_page=True)
        for name in ["Виа-феррата", "виа-феррата", "Скалодром", "Скалодром", "Тарзанка"]
    ]
    for order, service in enumerate(services):
        CategoryService.objects.create(category=category, service=service, order=order)
    related = client.get(services[0].get_absolute_url()).content.decode().split("Ещё в категории")[1]
    assert services[1].get_absolute_url() not in related  # тот же аттракцион другим вариантом
    assert services[2].get_absolute_url() in related
    assert services[3].get_absolute_url() not in related  # одинаковые названия — одна карточка
    assert services[4].get_absolute_url() in related
```

Run → FAIL.

- [ ] **Шаг 2: реализация**

`apps/catalog/views.py` — функция над `service_detail`:

```python
RELATED_SERVICES = 3


def related_services(category, service, limit: int = RELATED_SERVICES) -> list:
    """Другие услуги категории со своей страницей; варианты с тем же названием (в т. ч. текущей услуги) — один раз."""
    seen = {service.name.casefold()}
    result = []
    for item in category.published_services():
        name = item.name.casefold()
        if item.has_page and name not in seen:
            seen.add(name)
            result.append(item)
            if len(result) == limit:
                break
    return result
```

Строка 95: `related = related_services(category, service) if category else []`.

- [ ] **Шаг 3: тесты и коммит**

Run: `cd src && uv run pytest` → PASS.

```bash
git add src/apps/catalog/views.py src/tests/test_pages.py
git commit -m "«Ещё в категории»: без дублей по названию"
```

---

## Этап 3. Конверсия

Ветка: `feat/conversion`.

### Задача 3.1. WhatsApp с предзаполненным текстом (п. 6)

Страница услуги, категории и предстоящего мероприятия передаёт `contact_topic`; все кнопки WhatsApp на странице (карточка цены, плавающая кнопка, шапка, CTA) открывают чат с «Здравствуйте! Интересует «…»». Telegram по номеру текст не принимает — без изменений.

**Файлы:**
- Изменить: `src/apps/core/templatetags/site_tags.py`, `src/apps/catalog/views.py` (`category_detail`, `service_detail`), `src/apps/content/views.py` (`event_detail`), `src/templates/partials/contact_links.html:5`, `src/templates/partials/header.html` (кнопка «Написать» из задачи 1.3), `src/templates/partials/footer.html:11`
- Тест: `src/tests/test_pages.py`

- [ ] **Шаг 1: тест**

```python
def test_whatsapp_prefilled_with_service_name(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594", is_whatsapp=True)
    service = Service.objects.create(name="Виа-феррата", has_page=True)
    html = client.get(service.get_absolute_url()).content.decode()
    expected = "https://wa.me/79029856594?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5"
    assert expected in html  # «Здравствуйте…»
    assert "%C2%AB%D0%92%D0%B8%D0%B0-%D1%84%D0%B5%D1%80%D1%80%D0%B0%D1%82%D0%B0%C2%BB" in html  # «Виа-феррата»
    # На страницах без темы — ссылка без текста.
    assert 'href="https://wa.me/79029856594"' in client.get("/contacts/").content.decode()
```

- [ ] **Шаг 2: фильтр**

`site_tags.py` (импорт `from urllib.parse import quote`):

```python
@register.filter
def whatsapp_url(phone, topic: str = "") -> str:
    """Ссылка на чат; со страницы услуги или мероприятия — с готовым первым сообщением."""
    if not topic:
        return phone.whatsapp_url
    return f"{phone.whatsapp_url}?text={quote(f'Здравствуйте! Интересует «{topic}»')}"
```

- [ ] **Шаг 3: шаблоны и представления**

Во всех ссылках WhatsApp: `{{ whatsapp_phone.whatsapp_url }}` → `{{ whatsapp_phone|whatsapp_url:contact_topic }}` (+ `{% load site_tags %}` в начале партиала, где его нет). Неопределённая переменная в аргументе фильтра даёт `""` — на остальных страницах ссылка прежняя.

В контекст: `service_detail` — `"contact_topic": service.name`; `category_detail` — `"contact_topic": category.name`; `event_detail` — `"contact_topic": "" if event.is_past else event.title`.

- [ ] **Шаг 4: тесты и коммит**

Run: `cd src && uv run pytest` → PASS.

```bash
git commit -am "WhatsApp: первое сообщение с названием услуги или мероприятия"
```

### Задача 3.2. Цели Метрики на звонки и мессенджеры (п. 6)

**Файлы:**
- Изменить: `src/templates/partials/metrika.html`
- Тест: `src/tests/test_seo.py` (или где проверяется счётчик — `grep -rn metrika src/tests`)

- [ ] **Шаг 1: тест**

```python
def test_metrika_tracks_contact_clicks(client, settings):
    settings.DEBUG = False
    site = SiteSettings.load()
    site.yandex_metrika_id = "12345"
    site.save()
    html = client.get("/").content.decode()
    assert 'ym(12345, "reachGoal", goal)' in html
    for goal in ("call", "whatsapp", "telegram", "vk", "max"):
        assert f'"{goal}"' in html
```

- [ ] **Шаг 2: код** — в `metrika.html` перед `</script>`:

```js
  // Цели: звонок и переходы в мессенджеры (в Метрике — цели типа «JavaScript-событие» с этими идентификаторами).
  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link) return;
    var href = link.getAttribute("href");
    var goal = href.indexOf("tel:") === 0 ? "call"
      : href.indexOf("wa.me/") !== -1 ? "whatsapp"
      : href.indexOf("t.me/") !== -1 ? "telegram"
      : href.indexOf("vk.com/") !== -1 ? "vk"
      : href.indexOf("max.ru/") !== -1 ? "max" : "";
    if (goal) ym({{ site.yandex_metrika_id }}, "reachGoal", goal);
  });
```

- [ ] **Шаг 3: тесты, коммит, инструкция администратору**

Run: `cd src && uv run pytest` → PASS. Коммит. В чек-лист этапа К: «Метрика → Цели → JavaScript-событие: `call`, `whatsapp`, `telegram`, `vk`».

### Задача 3.3. VK и MAX в кнопках связи (п. 6)

Запасные каналы, когда WhatsApp/Telegram недоступны. MAX — новое поле `SiteSettings.max_url` (решение владельца: поле есть, пока пустое; кнопка появляется, только когда ссылка указана).

**Файлы:** `src/apps/core/models.py` (поле `max_url` после `vk_url`), миграция `core`, `src/apps/core/admin.py` (поле во вкладке контактов рядом с `vk_url`), `src/templates/icons/max.svg`, `src/templates/partials/contact_links.html`, `src/templates/content/contacts.html:22-28`, `src/templates/partials/footer.html:11-13`, тест `src/tests/test_pages_home.py`.

- [ ] **Шаг 1: тест**

```python
def test_contact_links_include_vk_and_max(client):
    site = SiteSettings.load()
    site.vk_url = "https://vk.com/tpark"
    site.save()
    Phone.objects.create(settings=site, number="9029856594")
    fab = client.get("/").content.decode().split('id="contact-menu"', 1)[1].split("</div>", 1)[0]
    assert 'href="https://vk.com/tpark"' in fab
    assert "MAX" not in fab  # ссылка не указана — кнопки нет
    site.max_url = "https://max.ru/u/tpark"
    site.save()
    html = client.get("/").content.decode()
    assert 'href="https://max.ru/u/tpark"' in html.split('id="contact-menu"', 1)[1].split("</div>", 1)[0]
    assert 'href="https://max.ru/u/tpark"' in client.get("/contacts/").content.decode()
```

- [ ] **Шаг 2: поле**

```python
    max_url = models.URLField("MAX", max_length=500, blank=True, help_text="Ссылка на профиль или канал в MAX. Пусто — кнопки нет.")
```

`uv run manage.py makemigrations core`.

- [ ] **Шаг 3: шаблоны** — в конец `contact_links.html`:

```html
{% if site.vk_url %}
<a href="{{ site.vk_url }}" class="btn btn-ghost" target="_blank" rel="noopener"><span class="icon icon-fill h-5 w-5 text-[#0077FF]">{% include "icons/vk.svg" %}</span>ВКонтакте</a>
{% endif %}
{% if site.max_url %}
<a href="{{ site.max_url }}" class="btn btn-ghost" target="_blank" rel="noopener"><span class="icon icon-fill h-5 w-5 text-[#7B4DFF]">{% include "icons/max.svg" %}</span>MAX</a>
{% endif %}
```

На контактах в блок «Написать» и в иконки подвала — MAX рядом с VK (условие `site.max_url`). Иконка `max.svg` — простой монохромный знак в `viewBox="0 0 24 24"` с `fill` от `currentColor` (как `vk.svg`). Цель Метрики (задача 3.2) — `max.ru/` → `"max"`.

Проверить глазами карточку цены в услуге на 1024 px: кнопки в столбик помещаются.

- [ ] **Шаг 4: тесты и коммит.**

### ~~Задача 3.4. Первый экран главной (п. 4)~~ — не делаем

Решение владельца: первый экран главной не меняем.

### Задача 3.5. Категории на телефоне — сетка в 2 колонки (п. 5)

**Файлы:** `src/templates/catalog/home.html:31-33`, `src/templates/catalog/partials/category_card.html:3,11`, тест `src/tests/test_pages_home.py`.

- [ ] **Шаг 1: тест**

```python
def test_home_categories_grid_on_phone(client):
    group = CategoryGroup.objects.create(name="Групповые приключения")
    for i in range(6):
        group.categories.add(Category.objects.create(name=f"Категория {i}", is_published=True))
    html = client.get("/").content.decode()
    section = html.split("Групповые приключения</h2>", 1)[1].split("</section>", 1)[0]
    assert "grid grid-cols-2" in section
    assert "overflow-x-auto" not in section
```

- [ ] **Шаг 2: код**

`home.html:31`:

```html
  <div class="grid grid-cols-2 gap-3 sm:gap-4 md:gap-6 {% if count > 2 %}lg:grid-cols-3{% endif %}">
```

`home.html:33`: обёртка карточки — `<div class="{% if count == 1 or count == 3 and forloop.first %}col-span-2 lg:col-span-1{% endif %}">` (одна категория — на всю ширину; из трёх — первая широкая, две под ней, без «дыры»). Комментарий над сеткой обновить.

`category_card.html`: на телефоне карточка 4:3 и шрифт мельче — `aspect-[3/2]` → `aspect-[4/3]`, заголовок `text-lg` → `text-base sm:text-xl`, паддинг `p-4` → `p-3 sm:p-5`. `width/height` у `<img>` не менять.

- [ ] **Шаг 3:** `uv run pytest`, `make e2e`, глазами 320/375 (названия в две строки помещаются), коммит.

---

## Этап 4. Доверие и юридическое

Ветка: `feat/legal`. Текст политики — от владельца; код готовит место под неё.

### Задача 4.1. Политика конфиденциальности

- Поле `SiteSettings.privacy_page` — FK на `InfoPage`, как `safety_page` (`on_delete=SET_NULL`, `related_name="+"`), вкладка «Юридическое» в админке.
- В контекст-процессор `site`: `privacy_page` (только опубликованная), чтобы ссылка была в подвале на всех страницах.
- Подвал, нижняя строка: «© 2026 Т-Парк · Политика конфиденциальности · Правила безопасности».
- Тест: страница указана и опубликована → ссылка в `<footer>`; снята с публикации → ссылки нет (по образцу `test_about_hides_unpublished_safety_page`).
- Контент: инфо-страница «Политика обработки персональных данных» (оператор, цели — связь и аналитика, Метрика и cookie, сроки, права субъекта, контакты). Текст согласует владелец.

### Задача 4.2. Уведомление о cookie

Решение владельца: только уведомление, Метрика грузится сразу.

- Партиал `partials/cookie_notice.html` в `base.html` перед `contact_button.html`, только при `metrika_enabled`: «Мы используем cookie и Яндекс Метрику, чтобы сайт работал удобнее.» + ссылка на политику (если `privacy_page`) + кнопка «Понятно».
- Alpine: показ, пока нет `localStorage["cookie-ok"]`; запись и чтение — в `try/catch` (приватный режим). Без JS баннер не показывается (`x-cloak`).
- Снизу на всю ширину, `z-[55]`; пока он открыт, у `<html>` класс `cookie-open`, и плавающая «Связаться» скрыта (`html.cookie-open .contact-fab { display: none; }` — без слоя, как `menu-open`). Проверить глазами 320 px.
- Тесты: с Метрикой баннер есть и ссылается на политику; без Метрики баннера нет.

### ~~Задача 4.3. Реквизиты~~ — не делаем

Решение владельца.

### Задача 4.4. Подвал: категории, часы, ссылки

- Перенести вычисление часов в контекст-процессор `site` (`hours = human_opening_hours(site.opening_hours)`), убрать дубли из `views.home`/`views.contacts`.
- Подвал в 4 колонки с `lg`: «Т-Парк» (адрес, соцсети), «Услуги» (категории из `menu_groups`, до 8), «Разделы», «Контакты» (телефоны + часы).
- Тест: категория опубликована → ссылка в `<footer>`; часы заданы → строка часов в `<footer>`.

---

## Этап 5. Развитие

Ветки по задачам. Порядок — по пользе; каждая задача независима.

### Задача 5.1. Выпадающее меню «Услуги» на ПК

- `header.html`: «Услуги» — `<button aria-expanded aria-controls>` с Alpine-выпадашкой (группы → категории, как в мобильном меню), закрытие по Escape, клику снаружи и уходу фокуса; ссылка «Все услуги» → главная.
- Выпадашка — колонки по группам, `max-w-3xl`, `card` с тенью.
- Тесты: в `<header>` у кнопки `aria-controls`, внутри — ссылки всех опубликованных категорий; неопубликованной нет.
- Глазами: Tab по шапке открывает/закрывает меню, фокус не теряется.

### Задача 5.2. Галерея: «Показать ещё»

Рекомендация — порционный показ, а альбомы — после, если понадобятся (нужна модель `GalleryAlbum` и разметка фото администратором).
- Все `<a class="glightbox">` остаются в HTML (просмотр листает всю галерею), фото после 24-го — с атрибутом `hidden`; кнопка «Показать ещё 24» (Alpine) снимает `hidden` у следующей порции. `loading="lazy"` у скрытых — браузер их не грузит.
- Тест: 30 фото → у 6 последних `hidden`, кнопка есть; 20 фото — кнопки нет.
- Цель: первая загрузка галереи на телефоне < 1 МБ.

### Задача 5.3. Место проведения мероприятия

- `Event.venue = models.CharField("Место проведения", max_length=255, blank=True, help_text="Пусто — в Т-Парке.")` + миграция + поле в админке.
- `event.html:34-38`: «Где» — `{% firstof event.venue site.address %}`; маршрут — только если `venue` пуст.
- JSON-LD `schema.org/Event` (`structured_data.event`): `location` — `Place` с `name=venue`, если задан.
- Тесты: с `venue` — его текст в «Где», ссылки «Маршрут» нет, в JSON-LD `location.name == venue`; без — как сейчас.

### Задача 5.4. «О нас» короче

- Шаблон `about.html:56`: `founder_text` — под `<details>` «Полная биография» (открыт на ПК не нужно — свёрнут везде), видимы фото, имя, подзаголовок и цифры.
- Контент (этап К): убрать повторы слогана в `about_text`, дубль «Этот человек придумал и создал Т-Парк» в `founder_text`, объединить 11 карточек биографии в 4–5.
- Тест: `founder_text` внутри `<details>`.
- Цель: «О нас» на телефоне ≤ 3 500 px.

### Задача 5.5. Категория: «Другие категории» и «К ценам»

- «Другие категории»: в коде уже `related_categories(limit=4)` — сначала проверить на реальной базе, откуда 7 карточек у «Корпоративов» (вероятно, это не этот блок). Раскладка: на телефоне лента из компактных карточек (как события), с `sm` — сетка 2/4 с одинаковыми карточками; одна карточка — не на всю ширину.
- «К ценам»: на телефоне под заголовком категории кнопка-якорь `#prices` (у секции «Услуги и цены» — `id="prices"` и `scroll-mt-20` под липкую шапку); фото в шапке на телефоне — `aspect-[16/9]`.
- Тесты: `id="prices"` и ссылка `href="#prices"` есть, если есть услуги.

### ~~Задача 5.6. Форма заявки~~ — не делаем

Решение владельца.

---

## Этап К. Контент (администратор)

Без кода, можно параллельно с этапами 1–2. Отмечать в админке и здесь.

- [ ] Фото для услуг без фото (в аудите — 17).
- [ ] Описание «Верёвочного парка».
- [ ] Объединить дубли услуг; выровнять единицы цен («человек», «час» — одинаково) и кавычки («ёлочки»).
- [ ] Исправить «рекрасное» → «прекрасное».
- [ ] Название бренда — «Т-Парк» везде в текстах (в т. ч. «T-park» в форматах на «О нас»); логотип T-PARK оставить.
- [ ] Место проведения у мероприятий вне парка (после задачи 5.3), например «Инструкторы для ДГТК Товарищ».
- [ ] «О нас» — сократить (задача 5.4).
- [ ] Метрика: цели `call`, `whatsapp`, `telegram`, `vk`, `max` (после задачи 3.2).
- [ ] Политика конфиденциальности — текст инфо-страницы (после задачи 4.1).

## Решения владельца (2026-10-10)

1. Первый экран главной не меняем — задача 3.4 снята.
2. Cookie — только уведомление (задача 4.2).
3. MAX — поле в настройках, пока пустое (задача 3.3).
4. Форму заявки не делаем — задача 5.6 снята.
5. Реквизиты не добавляем — задача 4.3 снята.
6. Пп. 7–9 аудита не восстанавливаем.

**Выполнение:** этапы 1–3 — в основной сессии (superpowers:executing-plans); этапы 4 и 5 — субагентами (superpowers:subagent-driven-development).
