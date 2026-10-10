# Доработки после UX-аудита — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Шесть доработок витрины по запросу владельца: автоподгрузка галереи, меню «Услуги» и «Связаться» в шапке ПК по наведению, официальная иконка MAX, «ВКонтакте» вместо «VK», типовая политика конфиденциальности в БД.

**Architecture:** Шаблоны Django + Alpine.js. Логика выпадающих меню при наведении — общий Alpine-компонент `hoverMenu` в новом `static/js/hover_menu.js` (подключается до Alpine). Галерея догружается через `IntersectionObserver`. Текст политики лежит в `apps/core/privacy_defaults.py` (без импорта моделей, по образцу `about_defaults.py`), его создают data-миграция и импорт старой базы.

**Tech Stack:** Django 6.1, Python 3.14, Alpine.js (vendored), Tailwind 4 (django-tailwind-cli), pytest-django, pytest-playwright (`make e2e`).

**Spec:** запрос владельца от 2026-10-10 (пункты 1–6 ниже) и решение по политике: «текст с пометками „[укажите …]“, страница создаётся снятой с публикации и уже выбранной в настройках сайта». Отдельного spec-файла нет. Исходный аудит — `docs/ux-audit-2026-10-10.md`.

Требования владельца (дословно по смыслу):
1. Картинки в галерее подгружаются автоматически при прокрутке, а не по кнопке.
2. На ПК кнопка «Услуги» в шапке открывает выпадающее меню при наведении, а не по клику.
3. На ПК в шапке вместо телефона и кнопки «Написать» — кнопка «Связаться», как в мобильной версии; контакты выезжают при наведении.
4. Иконка MAX — официальная, с max.ru.
5. Стандартный текст «Политики конфиденциальности», отвечающий основным требованиям; добавить в БД миграцией.
6. Везде «ВКонтакте» вместо «VK».

**Ветка:** работа продолжается на `fix/ux-audit` (она ещё не влита в `main`). Если владелец к началу выполнения решит влить её, новая ветка `feat/ux-followups` создаётся от `main`.

## Global Constraints

- Весь пользовательский текст — на русском.
- Фронт без Node и CDN: только vendored Alpine, свой JS — в `src/static/js/`.
- Комментарии `{# … #}` — только однострочные; длинные — `{% comment %}`.
- Оранжевый (brand) — только кликабельное; серый текст — только `ink/75` и `ink/65`.
- Миниатюры — только через `obj|spec_url:"spec"`.
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`; браузерные тесты — `make e2e` из корня.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; pre-commit (ruff) должен проходить.
- Не трогать `old_version/`, неотслеживаемый `.mcp.json` и чужую правку `.gitignore`.
- Поведение на устройствах без мыши (планшет 768–1279 px с тачем) не ухудшается: меню и «Связаться» открываются касанием.

## Review Focus

1. **Высокий экран галереи** (ПК 1280×4000, 72 фото): после первой порции метка догрузки остаётся в зоне видимости — `IntersectionObserver` не шлёт нового события, и галерея застревает на 48 фото. Ожидание: догружается всё, пока метка в зоне. Тест — задача 1 (`test_gallery_fills_tall_screen`).
2. **Путь мыши от кнопки к панели** при наведении: мышь пересекает пустую шапку (у «Услуг» — по диагонали к центрированной панели) — панель не должна закрыться. Тесты — задача 2 (движение по диагонали быстрее задержки закрытия) и задача 3 (пауза в зазоре под кнопкой «Связаться»).
3. **Клик по кнопке, когда меню уже открыто наведением**: панель не должна закрываться (пользователи кликают по привычке). Тесты — задачи 2 и 3.
4. **Тач-устройство шире 768 px** (планшет): наведения нет — касание открывает и закрывает меню. Тесты — задачи 2 и 3 (`is_mobile=True, has_touch=True`, 1024×768).
5. **Импорт старой базы после миграции политики**: миграция создаёт инфо-страницу, а импорт создаёт свои инфо-страницы с исходными `id` — возможен конфликт первичного ключа; после `--flush` политика пропала бы. Ожидание: импорт проходит, политика есть и выбрана в настройках. Тест — задача 6 (`test_import_keeps_privacy_page`).

Юридическая оговорка для итогового сообщения владельцу: текст политики — типовой, не юридическая консультация; перед публикацией стоит заполнить реквизиты и показать текст юристу (в частности, с 1 сентября 2025 г. согласие на обработку ПДн по 152-ФЗ оформляется отдельно от других документов).

---

### Задача 1: Галерея догружается при прокрутке

**Files:**
- Modify: `src/templates/content/gallery.html`
- Modify: `src/apps/content/views.py:105-113` (убрать `first_batch`)
- Test: `src/tests/test_pages.py` (тесты галереи ~строки 321–337)
- Test: `src/tests/e2e/test_mobile_layout.py` (заменить `test_gallery_load_more`)

**Interfaces:**
- Consumes: `GALLERY_PAGE = 24` и `page_size` в контексте (уже есть).
- Produces: ничего для других задач.

- [ ] **Шаг 1: переписать серверные тесты галереи**

В `src/tests/test_pages.py` заменить `test_gallery_shows_first_page_and_load_more_button` и `test_gallery_without_load_more_when_one_page` на:

```python
def test_gallery_shows_first_page_and_autoloads_rest(client, make_image):
    _make_gallery(make_image, 30)
    html = client.get("/gallery/").content.decode()
    anchors = _gallery_anchors(html)
    assert len(anchors) == 30  # просмотр листает всю галерею
    assert [" hidden" in a for a in anchors] == [False] * 24 + [True] * 6
    assert 'x-data="{ shown: 24, total: 30 }"' in html
    assert "data-gallery-more" in html and "IntersectionObserver" in html
    assert "Показать ещё" not in html


def test_gallery_without_autoload_when_one_page(client, make_image):
    _make_gallery(make_image, 20)
    html = client.get("/gallery/").content.decode()
    anchors = _gallery_anchors(html)
    assert len(anchors) == 20 and not any(" hidden" in a for a in anchors)
    assert "data-gallery-more" not in html
```

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_pages.py -k gallery`
Expected: FAIL `test_gallery_shows_first_page_and_autoloads_rest` (нет `total: 30` и `data-gallery-more`).

- [ ] **Шаг 3: шаблон — метка догрузки вместо кнопки**

В `src/templates/content/gallery.html` заменить открывающий тег обёртки и блок кнопки:

```django
  <div x-data="{ shown: {{ page_size }}, total: {{ photos|length }} }">
```

…сетка без изменений…

```django
  {% if photos|length > page_size %}
  {% comment %}
    Догрузка при прокрутке: невидимая метка под сеткой за 800 px до экрана открывает следующую порцию.
    После каждой порции наблюдение перезапускается — на высоком экране метка остаётся в зоне видимости,
    и без перезапуска новых событий не было бы. Когда показано всё, наблюдение снимается.
  {% endcomment %}
  <div data-gallery-more class="h-px" aria-hidden="true"
       x-init="const io = new IntersectionObserver(([entry]) => {
                 if (!entry.isIntersecting) return;
                 shown += {{ page_size }};
                 io.unobserve($el);
                 if (shown < total) $nextTick(() => io.observe($el));
               }, { rootMargin: '0px 0px 800px 0px' });
               io.observe($el)"></div>
  {% endif %}
```

Комментарий над сеткой («после первой порции — hidden…») оставить. Кнопку «Показать ещё» и её `<div class="mt-8 text-center" …>` удалить целиком.

- [ ] **Шаг 4: view — убрать `first_batch`**

В `src/apps/content/views.py` в `gallery()` удалить строку `"first_batch": …` — шаблон её больше не использует.

- [ ] **Шаг 5: серверные тесты проходят**

Run: `cd src && uv run pytest tests/test_pages.py -k gallery`
Expected: PASS (2 теста).

- [ ] **Шаг 6: e2e — заменить тест кнопки**

В `src/tests/e2e/test_mobile_layout.py` заменить `test_gallery_load_more` на:

```python
def _gallery(make_image, count):
    first = GalleryPhoto.objects.create(image=make_image())
    GalleryPhoto.objects.bulk_create([GalleryPhoto(image=first.image.name) for _ in range(count - 1)])


VISIBLE_PHOTOS = "document.querySelectorAll('a.glightbox:not([hidden])').length"


def test_gallery_autoloads_on_scroll(live_server, browser, make_image):
    """Следующая порция открывается сама, когда низ сетки подходит к экрану; кнопки нет."""
    _gallery(make_image, 60)
    context = browser.new_context(viewport={"width": 375, "height": 800}, device_scale_factor=3, is_mobile=True)
    page = context.new_page()
    page.goto(live_server.url + "/gallery/")
    page.wait_for_load_state("networkidle")
    assert page.locator("a.glightbox").count() == 60 and page.evaluate(VISIBLE_PHOTOS) == 24
    assert page.get_by_role("button", name="Показать ещё").count() == 0
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function(f"{VISIBLE_PHOTOS} === 48")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function(f"{VISIBLE_PHOTOS} === 60")
    context.close()


def test_gallery_fills_tall_screen(live_server, browser, make_image):
    """На высоком экране метка догрузки после порции остаётся видимой — галерея догружается дальше без прокрутки."""
    _gallery(make_image, 72)
    context = browser.new_context(viewport={"width": 1280, "height": 4000})
    page = context.new_page()
    page.goto(live_server.url + "/gallery/")
    page.wait_for_function(f"{VISIBLE_PHOTOS} === 72")
    context.close()
```

Если вспомогательная функция создания галереи в файле уже есть — использовать её, не дублируя.

- [ ] **Шаг 7: e2e проходят**

Run: `make e2e`
Expected: PASS. Проверка, что `test_gallery_fills_tall_screen` ловит ошибку: временно убрать `$nextTick(() => io.observe($el))` — тест должен упасть по таймауту (видно 48), затем вернуть.

- [ ] **Шаг 8: полный набор и коммит**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: все тесты зелёные.

```bash
git add src/templates/content/gallery.html src/apps/content/views.py src/tests/test_pages.py src/tests/e2e/test_mobile_layout.py
git commit -m "Галерея: следующая порция фото догружается при прокрутке вместо кнопки «Показать ещё»"
```

---

### Задача 2: «Услуги» в шапке ПК открываются при наведении

**Files:**
- Create: `src/static/js/hover_menu.js`
- Modify: `src/templates/base.html` (подключить скрипт до Alpine)
- Modify: `src/templates/partials/header.html` (блок `x-data="{ services: false }"`)
- Modify: `CLAUDE.md` (раздел Architecture, одна строка)
- Test: `src/tests/test_pages_home.py`
- Test: `src/tests/e2e/test_mobile_layout.py`

**Interfaces:**
- Produces: Alpine-компонент `hoverMenu` со свойствами `expanded: bool`, `hovering: bool` и методами `enter()`, `leave()`, `toggle()`, `close()`. Его использует задача 3.

- [ ] **Шаг 1: серверные тесты**

В `src/tests/test_pages_home.py` заменить `test_header_services_dropdown_ignores_focusout_without_target` на два теста:

```python
def test_hover_menu_script_loads_before_alpine(client):
    html = client.get("/").content.decode()
    assert html.index("js/hover_menu.js") < html.index("vendor/alpine.min.js")


def test_header_services_dropdown_opens_on_hover(client):
    CategoryGroup.objects.create(name="Активный отдых").categories.add(
        Category.objects.create(name="Байдарки", is_published=True)
    )
    header = _header(client.get("/").content.decode())
    wrapper = re.search(r'<div x-data="hoverMenu"[^>]*>', header).group(0)
    assert '@mouseenter="enter()"' in wrapper and '@mouseleave="leave()"' in wrapper
    # Клик по пустому месту панели даёт focusout с relatedTarget = null: он не должен закрывать меню.
    assert '@focusout="if ($event.relatedTarget && !$el.contains($event.relatedTarget)) close()"' in wrapper
    assert re.search(r'<button type="button"[^>]*@click="toggle\(\)"[^>]*aria-controls="services-menu"', header)
```

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_pages_home.py -k "hover"`
Expected: FAIL (нет `hover_menu.js` и `x-data="hoverMenu"`).

- [ ] **Шаг 3: компонент `hoverMenu`**

Создать `src/static/js/hover_menu.js`:

```js
// Выпадающее меню шапки на ПК (Alpine-компонент hoverMenu): на устройствах с мышью открывается наведением,
// на тач-экранах и с клавиатуры — кликом. Подключается до Alpine: регистрация — в событии alpine:init.
document.addEventListener("alpine:init", () => {
  const CLOSE_DELAY = 200; // мс: мышь успевает пересечь зазор между кнопкой и панелью или чуть промахнуться
  const canHover = window.matchMedia("(hover: hover) and (pointer: fine)");

  window.Alpine.data("hoverMenu", () => ({
    expanded: false,
    hovering: false,
    timer: null,
    enter() {
      if (!canHover.matches) return;
      clearTimeout(this.timer);
      this.hovering = true;
      this.expanded = true;
    },
    leave() {
      if (!canHover.matches) return;
      this.hovering = false;
      clearTimeout(this.timer);
      this.timer = setTimeout(() => (this.expanded = false), CLOSE_DELAY);
    },
    // Клик, пока мышь над меню, его не закрывает: оно уже открыто наведением, а кликают по привычке.
    toggle() {
      this.expanded = this.hovering || !this.expanded;
    },
    close() {
      clearTimeout(this.timer);
      this.expanded = false;
    },
  }));
});
```

В `src/templates/base.html` строкой выше `<script defer src="{% static 'vendor/alpine.min.js' %}"></script>` добавить:

```django
  <script defer src="{% static 'js/hover_menu.js' %}"></script>
```

- [ ] **Шаг 4: шапка — меню «Услуги» на компоненте**

В `src/templates/partials/header.html` заменить однострочный комментарий над меню и открывающий `<div x-data="{ services: false }" …>`, кнопку и тег панели:

```django
      {# Выпадающее меню «Услуги» (hoverMenu, static/js/hover_menu.js): наведение или клик; закрывается по Escape, клику снаружи и уходу фокуса (focusout без relatedTarget — клик по пустому месту панели — не закрывает); панель привязана к шапке, а не к кнопке — на 768 px иначе вылезла бы за край #}
      <div x-data="hoverMenu" @mouseenter="enter()" @mouseleave="leave()"
           @keydown.escape.window="if (expanded) { close(); $refs.trigger.focus() }"
           @click.outside="close()"
           @focusout="if ($event.relatedTarget && !$el.contains($event.relatedTarget)) close()">
        <button type="button" x-ref="trigger" class="inline-flex items-center gap-1 hover:text-brand-600" @click="toggle()" aria-controls="services-menu" :aria-expanded="expanded">
          Услуги
          <span class="icon h-4 w-4 transition-transform" :class="expanded && 'rotate-180'">{% include "icons/chevron-down.svg" %}</span>
        </button>
        {# before: — прозрачный «мостик» над панелью: мышь идёт от кнопки к панели, не покидая меню #}
        <div id="services-menu" x-show="expanded" x-cloak
             class="card absolute inset-x-4 top-full z-50 mx-auto mt-2 w-max max-w-[min(48rem,calc(100%-2rem))] p-6 shadow-lg before:absolute before:inset-x-0 before:-top-6 before:h-6">
```

Порядок атрибутов кнопки (`@click="toggle()"` перед `aria-controls="services-menu"`) важен для регулярки теста шага 1. Содержимое панели не меняется. Остальной `header.html` (переменная `open` мобильного меню) не трогать.

`test_header_services_dropdown_lists_published_categories` проверяет класс `max-w-[min(48rem,calc(100%-2rem))]` в теге панели — он сохранён.

- [ ] **Шаг 5: серверные тесты проходят**

Run: `cd src && uv run pytest tests/test_pages_home.py`
Expected: PASS.

- [ ] **Шаг 6: e2e**

В `src/tests/e2e/test_mobile_layout.py` добавить (существующий `test_services_menu_survives_click_on_empty_space` оставить — он должен пройти без изменений):

```python
def test_services_menu_opens_on_hover(live_server, browser, content):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    menu = page.locator("#services-menu")
    trigger = page.get_by_role("button", name="Услуги")

    trigger.hover()
    menu.wait_for(state="visible")
    # Панель центрирована в шапке, а не под кнопкой: мышь идёт к ней по диагонали через пустую шапку.
    # Путь в 8 шагов занимает меньше задержки закрытия (200 мс) — панель должна дождаться мыши.
    link = menu.get_by_role("link").first.bounding_box()
    page.mouse.move(link["x"] + 5, link["y"] + link["height"] / 2, steps=8)
    page.wait_for_timeout(400)
    assert menu.is_visible(), "панель закрылась, пока мышь шла к ней"

    trigger.click()  # меню открыто наведением — клик его не закрывает
    page.wait_for_timeout(100)
    assert menu.is_visible()

    page.mouse.move(5, 700)
    menu.wait_for(state="hidden")
    context.close()


def test_services_menu_toggles_by_tap_on_touch(live_server, browser, content):
    """На планшете наведения нет: меню открывается и закрывается касанием."""
    context = browser.new_context(viewport={"width": 1024, "height": 768}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    menu = page.locator("#services-menu")
    trigger = page.get_by_role("button", name="Услуги")
    trigger.tap()
    menu.wait_for(state="visible")
    trigger.tap()
    menu.wait_for(state="hidden")
    context.close()
```

Run: `make e2e`
Expected: PASS, включая старый `test_services_menu_survives_click_on_empty_space`.

- [ ] **Шаг 7: CLAUDE.md**

В разделе Architecture, после пункта про Swiper/GLightbox, добавить строку:

```markdown
- Выпадающие меню шапки на ПК («Услуги», «Связаться») — Alpine-компонент `hoverMenu` (`static/js/hover_menu.js`, подключён в `base.html` до Alpine): наведение на устройствах с мышью, клик на тач-экранах и с клавиатуры.
```

- [ ] **Шаг 8: полный набор и коммит**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: все тесты зелёные.

```bash
git add src/static/js/hover_menu.js src/templates/base.html src/templates/partials/header.html CLAUDE.md src/tests/test_pages_home.py src/tests/e2e/test_mobile_layout.py
git commit -m "Шапка ПК: меню «Услуги» открывается при наведении (на тач-экранах — касанием)"
```

---

### Задача 3: «Связаться» в шапке ПК вместо телефона и «Написать»

**Files:**
- Modify: `src/templates/partials/header.html` (блок `{% if phones %}<div class="hidden shrink-0 items-center gap-3 lg:flex">…`)
- Test: `src/tests/test_pages_home.py` (`test_header_shows_phone_on_desktop`)
- Test: `src/tests/e2e/test_mobile_layout.py`

**Interfaces:**
- Consumes: компонент `hoverMenu` из задачи 2 (`expanded`, `enter()`, `leave()`, `toggle()`, `close()`); `partials/contact_links.html` (те же кнопки, что в плавающей «Связаться»).
- Produces: `id="header-contact-menu"`.

- [ ] **Шаг 1: серверный тест**

В `src/tests/test_pages_home.py` заменить `test_header_shows_phone_on_desktop` на:

```python
def test_header_contact_dropdown_on_desktop(client):
    site = SiteSettings.load()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    header = _header(client.get("/").content.decode())
    wrapper = re.search(r'<div x-data="hoverMenu"[^>]*class="([^"]*)"[^>]*>\s*<button[^>]*aria-controls="header-contact-menu"', header)
    assert wrapper and "hidden" in wrapper.group(1).split() and "lg:block" in wrapper.group(1)
    menu = header.split('id="header-contact-menu"', 1)[1].split("</div>", 1)[0]
    assert 'href="tel:+79029856594"' in menu and "+7 (902) 985-65-94" in menu
    assert "https://wa.me/79029856594" in menu
    assert ">Написать<" not in header
    assert "Тренинг-парк Дмитрия Сергеева" not in header


def test_header_has_no_contact_dropdown_without_phones(client):
    assert 'id="header-contact-menu"' not in _header(client.get("/").content.decode())
```

Regex wrapper: атрибуты обёртки в шаге 3 идут в порядке `x-data`, `@mouseenter`, …, `class` — регулярка `[^>]*class=` это допускает.

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `cd src && uv run pytest tests/test_pages_home.py -k header_contact`
Expected: FAIL (нет `header-contact-menu`).

- [ ] **Шаг 3: разметка**

В `src/templates/partials/header.html` заменить весь блок `{% if phones %} … {% endif %}` между `</nav>` и кнопкой-бургером на:

```django
    {% if phones %}
    {# «Связаться» на ПК — те же кнопки, что у плавающей кнопки на телефоне (partials/contact_links.html); выезжают при наведении (hoverMenu), на тач-экранах — по касанию #}
    <div x-data="hoverMenu" @mouseenter="enter()" @mouseleave="leave()"
         @keydown.escape.window="if (expanded) { close(); $refs.trigger.focus() }"
         @click.outside="close()"
         @focusout="if ($event.relatedTarget && !$el.contains($event.relatedTarget)) close()"
         class="relative hidden shrink-0 lg:block">
      <button type="button" x-ref="trigger" @click="toggle()" aria-controls="header-contact-menu" :aria-expanded="expanded" class="btn btn-primary py-2">
        <span class="icon h-4 w-4" aria-hidden="true">{% include "icons/phone.svg" %}</span>Связаться
      </button>
      {# pt-3 — прозрачный «мостик» от кнопки к списку: мышь не покидает меню #}
      <div id="header-contact-menu" x-show="expanded" x-cloak
           x-transition:enter="transition duration-150 ease-out" x-transition:enter-start="-translate-y-2 opacity-0" x-transition:enter-end="translate-y-0 opacity-100"
           x-transition:leave="transition duration-100 ease-in" x-transition:leave-start="opacity-100" x-transition:leave-end="opacity-0"
           class="absolute right-0 top-full z-50 flex flex-col items-end gap-2 pt-3">
        {% include "partials/contact_links.html" %}
      </div>
    </div>
    {% endif %}
```

Плавающая кнопка (`partials/contact_button.html`, `lg:hidden`) не меняется: на ПК её нет, на 768–1023 px её заменяет только она — как и сейчас.

- [ ] **Шаг 4: серверные тесты проходят**

Run: `cd src && uv run pytest tests/test_pages_home.py tests/test_layout.py`
Expected: PASS. (`test_touch_targets_are_large_enough` смотрит бургер и подвал — не затронуты.)

- [ ] **Шаг 5: e2e**

В `src/tests/e2e/test_mobile_layout.py` добавить:

```python
def _gap_point(trigger, target):
    """Точка в зазоре под кнопкой, над первым пунктом списка — там, где мышь пересекает пустое место."""
    t, p = trigger.bounding_box(), target.bounding_box()
    return t["x"] + t["width"] / 2, (t["y"] + t["height"] + p["y"]) / 2


def test_header_contacts_slide_out_on_hover(live_server, browser, content):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    menu = page.locator("#header-contact-menu")
    trigger = page.locator("header").get_by_role("button", name="Связаться")
    assert page.locator(".contact-fab").is_hidden()  # плавающая кнопка на ПК не дублирует шапку

    trigger.hover()
    menu.wait_for(state="visible")
    assert menu.get_by_role("link", name="+7 (902) 985-65-94").is_visible()
    page.mouse.move(*_gap_point(trigger, menu.get_by_role("link").first))
    page.wait_for_timeout(400)
    assert menu.is_visible(), "список закрылся, пока мышь шла к нему"

    trigger.click()
    page.wait_for_timeout(100)
    assert menu.is_visible()

    page.mouse.move(5, 700)
    menu.wait_for(state="hidden")
    context.close()


def test_header_contacts_toggle_by_tap_on_touch(live_server, browser, content):
    context = browser.new_context(viewport={"width": 1280, "height": 800}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    menu = page.locator("#header-contact-menu")
    trigger = page.locator("header").get_by_role("button", name="Связаться")
    trigger.tap()
    menu.wait_for(state="visible")
    trigger.tap()
    menu.wait_for(state="hidden")
    context.close()
```

Run: `make e2e`
Expected: PASS; `test_no_horizontal_overflow` (320/375 px) не затронут — блок `hidden` до `lg`.

- [ ] **Шаг 6: проверка глазами**

`cd src && uv run manage.py tailwind runserver` на копии БД, на 1280 px навести на «Связаться» — список выезжает вниз, прижат к правому краю, не вылезает за экран; на 1024 px шапка с «Связаться» и пунктами меню помещается в одну строку.

- [ ] **Шаг 7: полный набор и коммит**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`

```bash
git add src/templates/partials/header.html src/tests/test_pages_home.py src/tests/e2e/test_mobile_layout.py
git commit -m "Шапка ПК: кнопка «Связаться» с контактами при наведении вместо телефона и «Написать»"
```

---

### Задача 4: Официальная иконка MAX

**Files:**
- Modify: `src/templates/icons/max.svg`
- Modify: `src/templates/partials/contact_links.html` (цвет иконки MAX)
- Test: `src/tests/test_layout.py`

**Источник:** брендбук MAX — https://go.max.ru/brandbook, архив https://st.max.ru/brandbook/max-dark.zip, файл `Max dark.svg` (монохромный знак). Знак — контур маски `<mask id="mask0_…">` этого файла: «облачко» с круглым вырезом, viewBox 0 0 100 100. Отрисовка проверена: со стандартным `fill-rule` (nonzero) вырез на месте, совпадает с оригиналом. Фирменный цвет из цветного варианта (`max-colored.zip`) — фиолетовый `#8114FF`.

- [ ] **Шаг 1: тест**

В `src/tests/test_layout.py` добавить:

```python
def test_max_icon_is_official_mark():
    """Знак MAX — контур из брендбука max.ru (st.max.ru/brandbook/max-dark.zip), а не самодельный рисунок."""
    svg = (TEMPLATES / "icons/max.svg").read_text()
    assert 'viewBox="0 0 100 100"' in svg and svg.count("<path") == 1
    assert 'd="M50.7571 0.261719C78.2929' in svg
```

- [ ] **Шаг 2: убедиться, что тест падает**

Run: `cd src && uv run pytest tests/test_layout.py -k max_icon`
Expected: FAIL.

- [ ] **Шаг 3: заменить иконку**

`src/templates/icons/max.svg` — одна строка (как другие иконки; цвет — `currentColor` через класс `.icon-fill`):

```html
<svg role="img" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><title>MAX</title><path d="M50.7571 0.261719C78.2929 0.261719 99.8857 22.5974 99.8857 50.1474C99.8857 77.6974 77.6071 99.4903 51.0214 99.4903C41.5857 99.4903 37.0143 98.1617 29.65 92.9474C29.1429 92.5903 28.45 92.6831 28.0214 93.1403C22.3571 99.1831 7.85 103.426 7.18571 95.176C7.18571 80.7903 0 71.4474 0 49.876C0 21.5546 23.2214 0.261719 50.7571 0.261719ZM51.5286 24.8117C38.4643 24.126 28.2643 33.1974 26.0143 47.3831C24.15 59.1332 27.45 73.4546 30.2786 74.176C31.4786 74.4832 34.3571 72.276 36.4571 70.2974C36.85 69.926 37.45 69.8617 37.9071 70.1474C41.1786 72.1474 44.8786 73.6474 48.9571 73.8617C62.3714 74.5617 74.2571 64.0617 74.9643 50.6474C75.6643 37.2331 64.9429 25.5046 51.5286 24.8046V24.8117Z"/></svg>
```

В `src/templates/partials/contact_links.html` у кнопки MAX заменить `text-[#7B4DFF]` на `text-[#8114FF]`.

- [ ] **Шаг 4: тест проходит, проверка глазами**

Run: `cd src && uv run pytest tests/test_layout.py`
Expected: PASS. Глазами: кнопка MAX в «Связаться» и иконка в подвале (белая на синем) — знак узнаваем, по размеру сопоставим с соседними иконками.

- [ ] **Шаг 5: коммит**

```bash
git add src/templates/icons/max.svg src/templates/partials/contact_links.html src/tests/test_layout.py
git commit -m "Иконка MAX — официальный знак из брендбука max.ru"
```

---

### Задача 5: «ВКонтакте» вместо «VK»

**Files:**
- Modify: `src/templates/content/contacts.html:28` (`VK` → `ВКонтакте`)
- Modify: `src/templates/content/events.html:40,42` («в нашей группе VK» → «в нашей группе ВКонтакте», «Группа VK» → «Группа ВКонтакте»)
- Modify: `src/templates/partials/footer.html:13` (`aria-label="VK"` → `aria-label="ВКонтакте"`)
- Modify: `src/templates/icons/vk.svg` (`<title>VK</title>` → `<title>ВКонтакте</title>`)
- Modify: `src/templates/admin/seo/object.html:2` («в VK и мессенджерах» → «во ВКонтакте и мессенджерах»)
- Modify: `src/templates/admin/seo/site.html:4,13` («в VK, Telegram» → «во ВКонтакте, Telegram»; «из VK» → «из ВКонтакте»)
- Modify: `src/apps/core/models.py:64` (verbose_name `"VK"` → `"ВКонтакте"`), `:153` (help_text «в VK, Telegram» → «во ВКонтакте, Telegram»)
- Modify: `src/apps/content/models.py:138,168` (`"vk.com": "VK"` → `"vk.com": "ВКонтакте"`, докстринг «VK» → «ВКонтакте»)
- Modify: `src/apps/core/structured_data.py:48` (докстринг)
- Create: миграция `src/apps/core/migrations/0013_vk_label.py` (через makemigrations)
- Test: `src/tests/test_layout.py`, `src/tests/test_content_models.py:107`

Не трогать: цель Метрики `"vk"` (`partials/metrika.html`), имена полей/классов (`vk_url`, `vk.svg`), тесты импорта со старым текстом «Пост в VK» (`tests/legacy/`) — это исходные данные.

- [ ] **Шаг 1: тесты**

В `src/tests/test_layout.py` добавить:

```python
def test_vk_is_called_vkontakte_everywhere():
    """В текстах сайта и админки соцсеть называется «ВКонтакте», а не «VK»."""
    offenders = [
        f"{path.relative_to(TEMPLATES)}: {line.strip()}"
        for path in TEMPLATES.rglob("*")
        if path.suffix in {".html", ".svg"}
        for line in path.read_text().splitlines()
        if re.search(r"\bVK\b", line)
    ]
    assert offenders == []


def test_vk_labels_in_models():
    from apps.core.models import SiteSettings

    assert SiteSettings._meta.get_field("vk_url").verbose_name == "ВКонтакте"
    assert "VK" not in SiteSettings._meta.get_field("og_image").help_text
```

В `src/tests/test_content_models.py` в параметрах `test_review_source_label` заменить `("https://vk.com/wall1", "VK")` на `("https://vk.com/wall1", "ВКонтакте")`.

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_layout.py tests/test_content_models.py -k "vk or source_label"`
Expected: FAIL, в списке нарушителей — contacts.html, events.html, footer.html, vk.svg, admin/seo/*.

- [ ] **Шаг 3: заменить тексты**

Внести замены из списка Files. Затем проверить, что ничего не осталось:

Run: `cd src && grep -rnw "VK" templates apps --include="*.html" --include="*.svg" --include="*.py" | grep -v "/migrations/" | grep -v "/legacy/"`
Expected: пусто.

- [ ] **Шаг 4: миграция**

Run: `cd src && uv run manage.py makemigrations core -n vk_label`
Expected: `0013_vk_label.py` с двумя `AlterField` (`vk_url`, `og_image`). Других изменений быть не должно.

- [ ] **Шаг 5: тесты проходят, полный набор**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: все зелёные.

- [ ] **Шаг 6: коммит**

```bash
git add src/templates src/apps/core/models.py src/apps/content/models.py src/apps/core/structured_data.py src/apps/core/migrations/0013_vk_label.py src/tests/test_layout.py src/tests/test_content_models.py
git commit -m "«ВКонтакте» вместо «VK» на сайте и в админке"
```

---

### Задача 6: Политика конфиденциальности — типовой текст в БД

**Files:**
- Create: `src/apps/core/privacy_defaults.py`
- Create: `src/apps/core/migrations/0014_privacy_policy.py`
- Modify: `src/apps/core/legacy/site.py` (импорт инфо-страниц)
- Modify: `CLAUDE.md` (одна строка)
- Test: `src/tests/test_core_models.py`, `src/tests/legacy/test_import_site.py`

**Interfaces:**
- Consumes: `SiteSettings.privacy_page` (FK на `InfoPage`, `SET_NULL`), контекст-процессор `site` показывает ссылку только для опубликованной страницы (уже есть); `sanitize_html` из `apps.core.fields`.
- Produces: `PRIVACY_SLUG = "privacy-policy"`, `PRIVACY_TITLE = "Политика конфиденциальности"`, `PRIVACY_HTML: str`, `ensure_privacy_page(info_page_model, site_model)` → страница.

Поведение: если страницы со слагом `privacy-policy` нет — создать её снятой с публикации (`is_published=False`) с текстом `sanitize_html(PRIVACY_HTML)`; если настройки сайта (`pk=1`) уже существуют и `privacy_page` пуст — выбрать эту страницу. Существующую страницу и уже выбранную политику не трогать. Пока страница не опубликована, ссылок в подвале и баннере cookie нет; владелец заполняет пометки «[укажите …]» в админке и ставит «Опубликовано».

- [ ] **Шаг 1: тесты**

В `src/tests/test_core_models.py` добавить:

```python
import importlib

from django.apps import apps as django_apps

from apps.core.models import InfoPage, SiteSettings
from apps.core.privacy_defaults import PRIVACY_SLUG, ensure_privacy_page


def _privacy_migration():
    return importlib.import_module("apps.core.migrations.0014_privacy_policy")


@pytest.mark.django_db
def test_privacy_page_created_unpublished_and_selected(client):
    InfoPage.objects.filter(slug=PRIVACY_SLUG).delete()  # миграция могла создать её в тестовой БД
    site = SiteSettings.load()
    _privacy_migration().forwards(django_apps, None)
    page = InfoPage.objects.get(slug=PRIVACY_SLUG)
    assert page.title == "Политика конфиденциальности" and not page.is_published
    for required in ("152-ФЗ", "Оператор", "Яндекс Метрика", "cookie", "Роскомнадзор", "[укажите ИНН]", "[укажите e-mail]"):
        assert required in page.body, required
    assert page.body.count("<h2>") == 10
    site.refresh_from_db()
    assert site.privacy_page == page
    assert page.get_absolute_url() not in client.get("/").content.decode()  # пока не опубликована — ссылки нет
    page.is_published = True
    page.save()
    assert page.get_absolute_url() in client.get("/").content.decode().split("<footer", 1)[1]


@pytest.mark.django_db
def test_ensure_privacy_page_keeps_existing_choice():
    InfoPage.objects.filter(slug=PRIVACY_SLUG).delete()
    site = SiteSettings.load()
    own = InfoPage.objects.create(title="Наша политика", body="<p>x</p>")
    site.privacy_page = own
    site.save()
    page = ensure_privacy_page(InfoPage, SiteSettings)
    assert ensure_privacy_page(InfoPage, SiteSettings) == page  # второй вызов ничего не создаёт
    assert InfoPage.objects.filter(slug=PRIVACY_SLUG).count() == 1
    site.refresh_from_db()
    assert site.privacy_page == own
```

(Импорты `importlib`, `django_apps`, `InfoPage`, `SiteSettings` — в начало файла, к существующим; не дублировать.)

В `src/tests/legacy/test_import_site.py` добавить:

```python
def test_import_keeps_privacy_page(legacy):
    """Миграция уже создала политику; импорт кладёт инфо-страницы с исходными id — конфликта нет, политика остаётся выбранной."""
    from apps.core.privacy_defaults import PRIVACY_SLUG, ensure_privacy_page

    taken_id = ensure_privacy_page(InfoPage, SiteSettings).id
    legacy.insert("text", id=taken_id, title=None, text="<p><strong>Правила</strong></p>", status=1)
    legacy.run()
    assert InfoPage.objects.get(id=taken_id).title == "Правила"
    privacy = InfoPage.objects.get(slug=PRIVACY_SLUG)
    assert not privacy.is_published
    assert SiteSettings.load().privacy_page == privacy
```

- [ ] **Шаг 2: убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_core_models.py tests/legacy/test_import_site.py -k privacy`
Expected: FAIL/ERROR — нет модуля `apps.core.privacy_defaults`.

- [ ] **Шаг 3: модуль с текстом**

Создать `src/apps/core/privacy_defaults.py`:

```python
"""Типовая политика конфиденциальности (152-ФЗ) для сайта Т-Парка.

Реквизиты оператора — пометки «[укажите …]»: владелец заполняет их в админке и публикует страницу.
Без импорта моделей — используется и в data-миграции, и при импорте старой базы."""

from apps.core.fields import sanitize_html

PRIVACY_SLUG = "privacy-policy"
PRIVACY_TITLE = "Политика конфиденциальности"

PRIVACY_HTML = """
<p>Редакция от 10 октября 2026 г.</p>
<p>Настоящая политика определяет порядок обработки и защиты персональных данных посетителей сайта t-camp.ru (далее — Сайт) и клиентов Т-Парка. Политика составлена в соответствии с Федеральным законом от 27.07.2006 № 152-ФЗ «О персональных данных» и опубликована для неограниченного доступа.</p>
<h2>1. Оператор</h2>
<p>Оператор персональных данных — <strong>[укажите ФИО индивидуального предпринимателя или наименование организации]</strong>, ИНН <strong>[укажите ИНН]</strong>, ОГРН/ОГРНИП <strong>[укажите ОГРН или ОГРНИП]</strong>, адрес: <strong>[укажите адрес]</strong> (далее — Оператор).</p>
<p>Электронная почта для обращений по вопросам персональных данных: <strong>[укажите e-mail]</strong>. Телефоны для связи указаны в разделе «Контакты» Сайта.</p>
<h2>2. Какие данные мы обрабатываем</h2>
<p>На Сайте нет форм регистрации и заявок. Оператор обрабатывает:</p>
<ul>
<li>данные, которые вы сообщаете сами, когда звоните или пишете нам по телефону, в WhatsApp, Telegram, ВКонтакте или MAX: имя, номер телефона, имя пользователя в мессенджере, текст сообщения и сведения, нужные для организации мероприятия (дата, число участников, пожелания);</li>
<li>технические данные, которые собираются автоматически при посещении Сайта: файлы cookie, IP-адрес, сведения о браузере и устройстве, адреса просмотренных страниц, дата и время посещения, источник перехода.</li>
</ul>
<p>Оператор не обрабатывает специальные категории персональных данных (о здоровье, политических взглядах, религиозных убеждениях и т. п.) и биометрические персональные данные.</p>
<h2>3. Цели обработки</h2>
<ul>
<li>ответ на обращения, консультация по услугам и расчёт стоимости;</li>
<li>бронирование и проведение мероприятий, заключение и исполнение договоров;</li>
<li>анализ посещаемости и улучшение работы Сайта.</li>
</ul>
<h2>4. Правовые основания</h2>
<ul>
<li>согласие субъекта персональных данных на их обработку;</li>
<li>заключение и исполнение договора, стороной которого является субъект персональных данных (п. 5 ч. 1 ст. 6 152-ФЗ).</li>
</ul>
<h2>5. Действия с данными и сроки хранения</h2>
<p>Оператор собирает, записывает, систематизирует, накапливает, хранит, уточняет, использует, удаляет и уничтожает персональные данные — с использованием средств автоматизации и без них.</p>
<p>Данные из обращений хранятся, пока это нужно для целей обработки, но не дольше 3 лет с последнего обращения, если более длительный срок не требует закон (например, для бухгалтерских документов). Затем данные уничтожаются или обезличиваются. При отзыве согласия обработка прекращается, а данные уничтожаются в течение 30 дней, если у Оператора нет других законных оснований для их обработки.</p>
<h2>6. Cookie и Яндекс Метрика</h2>
<p>Сайт использует файлы cookie и сервис веб-аналитики Яндекс Метрика (ООО «ЯНДЕКС», 119021, г. Москва, ул. Льва Толстого, д. 16). Метрика собирает сведения о посещениях: IP-адрес, данные cookie, сведения о браузере и устройстве, просмотренные страницы и действия на них, в том числе запись сеансов (Вебвизор). Эти сведения помогают понять, удобен ли Сайт, и не используются, чтобы установить вашу личность.</p>
<p>Вы можете отключить cookie в настройках браузера или установить блокировщик Яндекс Метрики (yandex.ru/support/metrica/general/opt-out.html) — Сайт продолжит работать.</p>
<h2>7. Передача данных</h2>
<p>Оператор не продаёт персональные данные и не передаёт их третьим лицам, кроме случаев, предусмотренных законом, и сервиса Яндекс Метрика (раздел 6).</p>
<p>WhatsApp, Telegram, ВКонтакте и MAX — самостоятельные сервисы: переписка в них подчиняется их собственным правилам. WhatsApp и Telegram принадлежат иностранным компаниям; выбирая их для связи, вы сами передаёте данные через их серверы. Оператор трансграничную передачу персональных данных не осуществляет.</p>
<p>Запись, систематизация, накопление, хранение, уточнение и извлечение персональных данных граждан Российской Федерации ведутся с использованием баз данных, находящихся на территории Российской Федерации.</p>
<h2>8. Защита данных</h2>
<p>Оператор принимает правовые, организационные и технические меры для защиты персональных данных от неправомерного доступа, изменения, распространения и уничтожения: ограничивает круг лиц, допущенных к данным, использует защищённое соединение (HTTPS), пароли и резервное копирование.</p>
<h2>9. Ваши права</h2>
<ul>
<li>получить сведения об обработке своих персональных данных;</li>
<li>потребовать уточнить, заблокировать или уничтожить данные, если они неполные, устаревшие, неточные, получены незаконно или не нужны для заявленной цели;</li>
<li>отозвать согласие на обработку персональных данных;</li>
<li>обжаловать действия или бездействие Оператора в Роскомнадзоре или в суде.</li>
</ul>
<p>Чтобы воспользоваться правами, напишите на <strong>[укажите e-mail]</strong> или позвоните по телефону из раздела «Контакты». Оператор ответит в течение 10 рабочих дней; срок может быть продлён не более чем на 5 рабочих дней с уведомлением о причинах.</p>
<h2>10. Изменение политики</h2>
<p>Оператор может обновлять политику. Новая редакция действует с момента публикации на этой странице; дата редакции указана в начале документа.</p>
"""


def ensure_privacy_page(info_page_model, site_model):
    """Создаёт политику (снятой с публикации), если её нет, и выбирает её в настройках, если там пусто."""
    page = info_page_model.objects.filter(slug=PRIVACY_SLUG).first()
    if page is None:
        page = info_page_model.objects.create(
            title=PRIVACY_TITLE, slug=PRIVACY_SLUG, body=sanitize_html(PRIVACY_HTML.strip()), is_published=False
        )
    site = site_model.objects.filter(pk=1).first()
    if site is not None and site.privacy_page_id is None:
        site.privacy_page = page
        site.save(update_fields=["privacy_page"])
    return page
```

`SiteSettings.save()` переопределён (ставит `pk=1`) — `update_fields` ему не мешает; в миграции используется историческая модель без переопределений.

- [ ] **Шаг 4: data-миграция**

Создать `src/apps/core/migrations/0014_privacy_policy.py`:

```python
from django.db import migrations

from apps.core.privacy_defaults import ensure_privacy_page


def forwards(apps, schema_editor):
    ensure_privacy_page(apps.get_model("core", "InfoPage"), apps.get_model("core", "SiteSettings"))


class Migration(migrations.Migration):
    dependencies = [("core", "0013_vk_label")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
```

Если задача 5 ещё не сделана, зависимость — от последней существующей миграции `core` (`0012_site_privacy_page`); при последующем `makemigrations` порядок поправить.

- [ ] **Шаг 5: импорт старой базы**

В `src/apps/core/legacy/site.py`:
- добавить импорт `from apps.core.privacy_defaults import PRIVACY_SLUG, ensure_privacy_page`;
- перед циклом `for row in info_rows:` добавить:

```python
    # Политику создаёт миграция; импорт кладёт инфо-страницы с исходными id — убираем её на время, чтобы не было конфликта.
    InfoPage.objects.filter(slug=PRIVACY_SLUG).delete()
```

- после цикла (после `report.add("Инфо-страницы")` в цикле, на уровне функции):

```python
    ensure_privacy_page(InfoPage, SiteSettings)
```

- [ ] **Шаг 6: тесты проходят**

Run: `cd src && uv run pytest tests/test_core_models.py tests/legacy/test_import_site.py`
Expected: PASS. Если `sanitize_html` изменил разметку так, что `page.body.count("<h2>") != 10`, — разобраться (не подгонять тест): все теги текста (`p`, `h2`, `ul`, `li`, `strong`) входят в `HTML_EXTENSIONS`.

- [ ] **Шаг 7: миграция на копии реальной БД**

Run (из `src/`, на копии `current_content/db.sqlite3` в scratchpad, не на оригинале): `DATABASE_PATH=<копия> uv run manage.py migrate` и `DATABASE_PATH=<копия> uv run manage.py shell -c "from apps.core.models import SiteSettings as S; p=S.load().privacy_page; print(p, p.is_published, p.slug)"`
Expected: `Политика конфиденциальности False privacy-policy` — либо уже выбранная владельцем страница, если она была (её миграция не меняет).

- [ ] **Шаг 8: CLAUDE.md**

В пункте про `apps/core` (рядом с `about_defaults`/`legacy/`) добавить:

```markdown
  - `privacy_defaults.py` — типовая политика конфиденциальности (152-ФЗ) с пометками «[укажите …]» для реквизитов: data-миграция `0014_privacy_policy` и импорт старой базы создают её снятой с публикации и выбирают в настройках (`privacy_page`);
```

- [ ] **Шаг 9: полный набор и коммит**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`

```bash
git add src/apps/core/privacy_defaults.py src/apps/core/migrations/0014_privacy_policy.py src/apps/core/legacy/site.py CLAUDE.md src/tests/test_core_models.py src/tests/legacy/test_import_site.py
git commit -m "Политика конфиденциальности: типовой текст (152-ФЗ) миграцией, снята с публикации до заполнения реквизитов"
```

---

## Итог

- [ ] `cd src && uv run pytest` — всё зелёное; `make e2e` — всё зелёное.
- [ ] Проверка глазами на копии реальной БД: галерея (375 px, прокрутка до конца), шапка на 1024 и 1280 px (наведение на «Услуги» и «Связаться»), подвал (иконки ВКонтакте и MAX), `/info/privacy-policy/` под админом не открывается (снята с публикации — 404 по правилам сайта), в админке «Инфо-страницы» → «Политика конфиденциальности» видны пометки «[укажите …]».
- [ ] В итоговом сообщении владельцу: какие пометки заполнить в политике и что публикация включает ссылки в подвале и баннере cookie; оговорка из Review Focus про юриста и отдельное согласие.
