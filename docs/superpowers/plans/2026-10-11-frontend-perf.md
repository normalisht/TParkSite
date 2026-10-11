# Скорость витрины и карта по клику — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- LCP-фото галереи грузится сразу;
- у категории высокий приоритет только у фото шапки;
- Яндекс Карта на контактах загружается по кнопке: нет пустого белого блока и сторонних cookie до клика;
- HTML отдаётся с ETag и ответом 304;
- статика — с brotli.

**Architecture:**
- **Фото:** порядок загрузки задаётся атрибутами тега `{% picture %}`. Для читаемых условий — два фильтра в `apps/core/templatetags/site_tags.py`: `lazy_after` и `eager_first`.
- **Карта:** Alpine-заглушка `x-data="{ map: false }"`, iframe внутри `<template x-if>`.
- **Сжатие:** `whitenoise[brotli]` и `ConditionalGetMiddleware`.

**Tech Stack:** Django-шаблоны, Alpine.js (vendored), WhiteNoise, pytest-django, pytest-playwright (`make e2e`).

**Spec:** `docs/site-audit-2026-10-11.md`. Этот план закрывает:
- P3 — п. 31 (карта);
- п. 39 (порядок загрузки фото);
- п. 40, третья строка (сжатие и ETag). Запросы к БД из п. 40 закрывает план `2026-10-11-catalog-seo-admin.md`, задача 1.

**Ветка:** `perf/frontend` от `main`.

## Global Constraints

- Фронт без Node и CDN: только vendored Alpine. Атрибут с пустым значением тег `{% picture %}` не выводит, кроме `alt`.
- Комментарии `{# … #}` — только однострочные; длинные — `{% comment %}`.
- Цвета: оранжевый (brand) — только кликабельное, зелёный (pine) — «место», серый текст — только `ink/75` и `ink/65`.
- Пользовательский текст — на русском. Python-команды — из `src/`.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Карта без JavaScript** (Alpine не загрузился).
   - Ожидание: видна ссылка «Открыть на Яндекс Картах», а не пустой блок с неработающей кнопкой.
   - Тест: задача 2, `test_contacts_map_has_no_js_fallback`.
2. **Карта не задана в настройках** (`map_embed_url` пуст).
   - Ожидание: блока карты нет, сетка контактов как раньше (`md:max-w-xl`).
   - Тест: задача 2, `test_contacts_without_map`.
3. **Галерея, где фото меньше четырёх.**
   - Ожидание: все фото без `lazy`, `fetchpriority="high"` ровно у первого.
   - Тест: задача 1, `test_gallery_short_list`.
4. **Страница с CSRF-формой и ETag** (админка, вход).
   - Ожидание: `ConditionalGetMiddleware` не мешает входу: у формы каждый раз новый токен, 304 не отдаётся.
   - Тест: задача 3, `test_admin_login_still_works_with_conditional_get`.
5. **Слайдер на странице услуги** — он на первом экране.
   - Ожидание: у первого слайда остаётся `fetchpriority="high"` и нет `lazy`, как сейчас.
   - Тест: задача 1, `test_service_slider_first_photo_stays_eager`.

---

### Task 1: Порядок загрузки фото — галерея и слайдер категории

**Files:**
- Modify: `src/apps/core/templatetags/site_tags.py` (фильтры `lazy_after`, `eager_first`)
- Modify: `src/templates/content/gallery.html:20`
- Modify: `src/templates/catalog/partials/slider.html:6`
- Modify: `src/templates/catalog/category.html:42`
- Test: `src/tests/test_images.py`

**Interfaces:**
- Produces:
  - фильтр `{{ forloop.counter|lazy_after:4 }}` → `""` для первых 4, иначе `"lazy"`;
  - фильтр `{{ forloop.first|eager_first:below_fold }}` → `True` только у первого фото слайдера, который не ниже первого экрана;
  - параметр `below_fold=1` у `catalog/partials/slider.html`.

- [ ] **Step 1: Падающие тесты** — в `src/tests/test_images.py` (импорты `re`, `GalleryPhoto`, `Category`, `CategoryPhoto`, `Service`, `ServicePhoto`, если их нет):

```python
def _imgs(html: str, path_part: str) -> list[str]:
    return [tag for tag in re.findall(r"<img [^>]*>", html) if path_part in tag]


@pytest.mark.django_db
def test_gallery_first_row_loads_eagerly(client, make_image):
    for i in range(6):
        GalleryPhoto.objects.create(image=make_image(f"{i}.jpg"))
    imgs = _imgs(client.get("/gallery/").content.decode(), "/gallery/")
    assert len(imgs) == 6
    assert 'fetchpriority="high"' in imgs[0]
    assert all('loading="lazy"' not in tag for tag in imgs[:4])
    assert all('loading="lazy"' in tag for tag in imgs[4:])
    assert sum('fetchpriority="high"' in tag for tag in imgs) == 1


@pytest.mark.django_db
def test_gallery_short_list(client, make_image):
    for i in range(2):
        GalleryPhoto.objects.create(image=make_image(f"{i}.jpg"))
    imgs = _imgs(client.get("/gallery/").content.decode(), "/gallery/")
    assert [('fetchpriority="high"' in t, 'loading="lazy"' in t) for t in imgs] == [(True, False), (False, False)]


@pytest.mark.django_db
def test_category_has_single_high_priority_photo(client, make_image):
    category = Category.objects.create(name="Парк", is_published=True, preview=make_image("preview.jpg"))
    for i in range(3):
        CategoryPhoto.objects.create(category=category, image=make_image(f"{i}.jpg"))
    html = client.get(category.get_absolute_url()).content.decode()
    assert html.count('fetchpriority="high"') == 1
    slides = _imgs(html, "/catalog/categories/")
    assert slides and all('loading="lazy"' in tag for tag in slides)


@pytest.mark.django_db
def test_service_slider_first_photo_stays_eager(client, make_image):
    service = Service.objects.create(name="Троллей", has_page=True)
    for i in range(2):
        ServicePhoto.objects.create(service=service, image=make_image(f"{i}.jpg"))
    slides = _imgs(client.get(service.get_absolute_url()).content.decode(), "/catalog/services/")
    assert 'fetchpriority="high"' in slides[0] and 'loading="lazy"' not in slides[0]
    assert 'loading="lazy"' in slides[1]
```

Пути миниатюр: imagekit кладёт их в `CACHE/images/<путь оригинала>/…`. Оригиналы галереи — в `gallery/`, фото категорий — в `catalog/categories/`, услуг — в `catalog/services/`, поэтому подстрока пути есть и в URL миниатюры. Если у категории фото шапки (`preview` — `catalog/previews/`) попадёт в `_imgs(..., "/catalog/categories/")`, сузить подстроку. Проверить фактический HTML через `print`.

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_images.py -k "gallery_first or gallery_short or single_high or stays_eager" -v`
Expected:
- `test_gallery_first_row_loads_eagerly` — FAIL (у всех `lazy`);
- `test_category_has_single_high_priority_photo` — FAIL (2 × high);
- `test_service_slider…` — PASS (поведение уже такое, тест его закрепляет).

- [ ] **Step 3: Фильтры** — в `apps/core/templatetags/site_tags.py`:

```python
@register.filter
def lazy_after(counter, eager: int) -> str:
    """`loading` для N-го фото списка: первые `eager` — сразу (первый экран), остальные — лениво."""
    return "" if int(counter) <= int(eager) else "lazy"


@register.filter
def eager_first(is_first, below_fold) -> bool:
    """Первое фото слайдера грузится сразу и с высоким приоритетом — если сам слайдер на первом экране."""
    return bool(is_first) and not below_fold
```

- [ ] **Step 4: Шаблоны**

`templates/content/gallery.html`, тег `{% picture photo … %}` — заменить `loading="lazy"` на:

```django
loading=forloop.counter|lazy_after:4 fetchpriority=forloop.first|yesno:"high,"
```

`templates/catalog/partials/slider.html`, строка с `{% picture %}`: обернуть в `{% with eager=forloop.first|eager_first:below_fold %}` … `{% endwith %}` и заменить атрибуты:

```django
fetchpriority=eager|yesno:"high," loading=eager|yesno:",lazy"
```

Первой строкой файла после `{% load site_tags %}`:

```django
{# below_fold=1 — слайдер ниже первого экрана (категория): все фото лениво, без высокого приоритета. #}
```

`templates/catalog/category.html:42` — в include добавить `below_fold=1`:

```django
  {% include "catalog/partials/slider.html" with alt=category.name below_fold=1 sizes="(min-width: 1152px) 1120px, calc(100vw - 32px)" %}
```

- [ ] **Step 5: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

- [ ] **Step 6: CLAUDE.md** — в абзац «Фото первого экрана…» дописать:

```markdown
В галерее первые 4 превью — без `lazy` (`forloop.counter|lazy_after:4`), первое — `fetchpriority="high"`; слайдер ниже первого экрана подключается с `below_fold=1` (категория), у страницы услуги он на первом экране.
```

- [ ] **Step 7: Коммит**

```bash
git add src/apps/core/templatetags/site_tags.py src/templates/content/gallery.html src/templates/catalog src/tests/test_images.py CLAUDE.md
git commit -m "Фото: первый ряд галереи грузится сразу, у категории высокий приоритет только у шапки"
```

---

### Task 2: Яндекс Карта по кнопке

**Files:**
- Modify: `src/templates/content/contacts.html:45-48`
- Test: `src/tests/test_pages.py`
- Test (e2e): `src/tests/e2e/test_mobile_layout.py`

- [ ] **Step 1: Падающие тесты** — в `src/tests/test_pages.py` (импорт `SiteSettings`, если нет):

```python
MAP_URL = "https://yandex.ru/map-widget/v1/org/t_park/17031236197/"


def _set_map(url: str, yandex_maps_url: str = "") -> None:
    site = SiteSettings.load()
    site.map_embed_url, site.yandex_maps_url = url, yandex_maps_url
    site.save()


@pytest.mark.django_db
def test_contacts_map_loads_on_click(client):
    _set_map(MAP_URL)
    html = client.get("/contacts/").content.decode()
    assert "Показать карту" in html
    template_at = html.index('<template x-if="map">')
    assert html.index("<iframe") > template_at  # iframe только внутри <template>: до клика браузер его не грузит
    assert html.count("<iframe") == 1


@pytest.mark.django_db
def test_contacts_map_has_no_js_fallback(client):
    _set_map(MAP_URL, "https://yandex.ru/maps/org/t_park/17031236197/")
    html = client.get("/contacts/").content.decode()
    noscript = html.split("<noscript>", 1)[1].split("</noscript>", 1)[0]
    assert 'href="https://yandex.ru/maps/org/t_park/17031236197/"' in noscript


@pytest.mark.django_db
def test_contacts_without_map(client):
    _set_map("")
    html = client.get("/contacts/").content.decode()
    assert "Показать карту" not in html and "<iframe" not in html
    assert "md:max-w-xl" in html
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_pages.py -k contacts_map -v`
Expected: FAIL («Показать карту» нет).

- [ ] **Step 3: Шаблон** — в `templates/content/contacts.html` заменить блок `{% if site.map_embed_url %}<iframe …>{% endif %}`:

```django
      {% if site.map_embed_url %}
      {% comment %}
        Карта по кнопке: iframe Яндекса тяжёлый, ставит сторонние cookie и до загрузки показывает пустой белый блок.
        Без JS — ссылка на карточку в Яндекс Картах.
      {% endcomment %}
      <div x-data="{ map: false }" class="card relative h-96 w-full overflow-hidden lg:h-full lg:min-h-[28rem]">
        <template x-if="map">
          <iframe src="{{ site.map_embed_url }}" title="Т-Парк на Яндекс Картах" allowfullscreen
                  class="absolute inset-0 h-full w-full"></iframe>
        </template>
        <div x-show="!map" class="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-pine-50 p-6 text-center">
          <span class="icon h-10 w-10 text-pine-700">{% include "icons/map-pin.svg" %}</span>
          <p class="max-w-xs text-ink/75">{{ site.address }}</p>
          <button type="button" class="btn btn-primary" x-cloak @click="map = true">Показать карту</button>
          <noscript><a href="{% firstof site.yandex_maps_url site.map_embed_url %}" class="btn btn-primary" target="_blank" rel="noopener">Открыть на Яндекс Картах</a></noscript>
        </div>
      </div>
      {% endif %}
```

Кнопка с `x-cloak`, поэтому без JS её не видно, и остаётся только ссылка из `<noscript>`. Проверить, что `[x-cloak]{display:none}` есть в `tailwind/source.css`: `grep -n "x-cloak" src/tailwind/source.css`. Если нет — добавить в `@layer base`.

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: e2e** — в `src/tests/e2e/test_mobile_layout.py` (по образцу соседних тестов: фикстуры `live_server`, `page`):

```python
def test_contacts_map_appears_after_click(live_server, page, map_settings):
    page.goto(f"{live_server.url}/contacts/")
    assert page.locator("iframe").count() == 0
    page.get_by_role("button", name="Показать карту").click()
    page.wait_for_selector("iframe[title='Т-Парк на Яндекс Картах']", state="attached")
```

Фикстуру `map_settings` (заполняет `SiteSettings.map_embed_url`) сделать по образцу настройки данных в соседних e2e-тестах этого файла.

Run: `make e2e ARGS="-k map"`
Expected: PASS.

- [ ] **Step 6: Коммит**

```bash
git add src/templates/content/contacts.html src/tests/test_pages.py src/tests/e2e/test_mobile_layout.py src/tailwind/source.css
git commit -m "Контакты: Яндекс Карта по кнопке — без пустого блока и сторонних cookie до клика"
```

---

### Task 3: ETag для HTML и brotli для статики

**Files:**
- Modify: `src/pyproject.toml`, `src/uv.lock` (`whitenoise[brotli]`)
- Modify: `src/config/settings.py` (MIDDLEWARE)
- Test: `src/tests/test_settings.py`, `src/tests/test_static.py`

- [ ] **Step 1: Падающие тесты**

`src/tests/test_settings.py`:

```python
import pytest


@pytest.mark.django_db
def test_html_pages_support_conditional_get(client):
    first = client.get("/contacts/")
    assert first.has_header("ETag")
    assert client.get("/contacts/", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


@pytest.mark.django_db
def test_admin_login_still_works_with_conditional_get(client, django_user_model):
    django_user_model.objects.create_superuser("boss", password="right-pass-123")
    first = client.get("/admin/login/")
    response = client.post(
        "/admin/login/", {"username": "boss", "password": "right-pass-123"}, HTTP_IF_NONE_MATCH=first.get("ETag", "")
    )
    assert response.status_code == 302
```

`src/tests/test_static.py` — в конец существующего `test_collectstatic_with_production_storage` (после `call_command`):

```python
    assert list(tmp_path.rglob("*.css.br")), "WhiteNoise не создал .br — нет пакета brotli"
```

(Проверить, что в этом тесте `STATIC_ROOT` = `tmp_path`; если другая папка — искать в ней.)

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_settings.py tests/test_static.py -v`
Expected: FAIL (нет ETag; нет `.br`).

- [ ] **Step 3: Реализация**

Run: `cd src && uv remove whitenoise && uv add "whitenoise[brotli]>=6.12.0"`

`config/settings.py`, MIDDLEWARE — сразу после `"django.middleware.security.SecurityMiddleware",`:

```python
    # ETag для HTML: повторный заход на неизменённую страницу — 304 без тела.
    "django.middleware.http.ConditionalGetMiddleware",
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

Если `test_html_pages_support_conditional_get` получает 200: страница меняется между запросами. Найти отличие (`difflib` двух ответов) — например, случайное значение в шаблоне. Сделать вывод детерминированным; не отключать тест.

- [ ] **Step 5: Сжатие HTML в варианте с общим прокси** — в задаче 3 плана `2026-10-11-launch-hardening.md` в README уже есть требование `gzip on` к прокси. Если этот план выполняется раньше, добавить в README строку:

```markdown
Общий прокси должен сжимать HTML (`gzip on`; `text/html` nginx сжимает по умолчанию): галерея без сжатия — 288 КБ, со сжатием — около 35 КБ.
```

- [ ] **Step 6: Коммит**

```bash
git add src/pyproject.toml src/uv.lock src/config/settings.py src/tests/test_settings.py src/tests/test_static.py README.md
git commit -m "HTML с ETag и 304 (ConditionalGetMiddleware), статика с brotli (whitenoise[brotli])"
```

---

## После плана

```bash
cd src && uv run pytest -q && uv run ruff check . && cd .. && make e2e
```

Проверить Lighthouse:
- `/contacts/` — Best Practices больше не 77: до клика нет сторонних cookie;
- `/gallery/` — LCP без задержки `lazy`.
