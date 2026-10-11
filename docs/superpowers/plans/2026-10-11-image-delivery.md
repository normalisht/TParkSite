# Доставка изображений: AVIF, честные srcset, лёгкий лайтбокс — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** сократить вес фото у посетителей примерно вдвое (на телефоне в галерее — втрое), исправить мыльные слайды и неверные `srcset`, сделать полноэкранный просмотр и превью в соцсетях лёгкими и надёжными.

**Architecture:** у каждой миниатюры витрины появляется AVIF-двойник (`<спека>_avif`), а разметку `<picture>` с `<source type="image/avif">` и запасным WebP строит один тег `{% picture %}`. Слайды режутся на сервере под 16:9 (размеры совпадают с `srcset`). Лайтбокс получает WebP-спеку `full` вместо JPEG-оригинала, соцсети — JPEG-спеку `og` 1200×630. Миниатюры создаются в фоне сразу после сохранения фото; устаревшие файлы удаляет команда `prune_image_cache`.

**Tech Stack:** Django 6.1, django-imagekit 6.1 (pilkit), Pillow 12.3 (AVIF есть и в macOS-, и в Linux-колесе — проверено в `python:3.14-slim`), GLightbox (понимает `.webp`), Swiper, Tailwind.

**Spec:** анализ в разговоре от 11 октября 2026 (итоги — ниже, «Замеры»); заменяет `docs/superpowers/plans/2026-10-09-avif-thumbnails.md` (удаляется в задаче 8).

## Замеры (основание для параметров)

На `current_content/media` (336 исходников, 574 миниатюры), выборки по 25–30 фото:

| | Сейчас | После |
|---|---|---|
| Миниатюра галереи 600² | WebP q80 62 КБ | AVIF q55 s6 36 КБ |
| Миниатюра галереи на телефоне | 600² 62 КБ | 400² AVIF 19 КБ |
| Слайд 1600×900 | WebP `fit` 150 КБ, у 4:3 и портретов реально 1200w/675w при `srcset` «1600w» | `fill` AVIF 106 КБ, честные 1600w/800w |
| Лайтбокс (вся галерея) | JPEG 177 КБ | WebP q75 `method=6` — 133 КБ |

- AVIF q50 `speed=4` (из старого плана) кодируется 330–460 мс на кадр; **q55 `speed=6`** — 50–70 мс (как WebP `method=6`) при почти том же размере. Глазами на самых «шумных» фото (листва, кора, мульча) отличий от WebP q80 нет.
- Рендер страниц не узкое место: галерея из 186 фото — 30 мс тёплая; заголовки кеширования `/media/` (1 год, `immutable`) уже верные; `image/avif` в `mime.types` образа `nginx:stable-alpine` (1.30.5) есть.

## Global Constraints

- Весь пользовательский текст — на русском; комментарии в шаблонах `{# … #}` — только однострочные.
- Миниатюры в шаблонах — только через `{% picture %}` или `spec_url` (`{% load site_tags %}`): ни то ни другое не падает на отсутствующем или битом файле.
- AVIF-двойник называется `<спека>_avif` и объявляется через `image_specs(...)`; WebP-спеки с прежними параметрами (q80) не меняются, чтобы не пересоздавать уже готовые файлы.
- AVIF: `{"quality": 55, "speed": 6}`; WebP: `{"quality": 80}`; `og`: JPEG 1200×630 `{"quality": 82, "progressive": True}`; `full`: WebP q75 `method=6`, вписать в 1920×1080 без увеличения (при q80 на всей галерее выигрыш был всего 10%, а 34 из 186 фото выходили тяжелее JPEG-оригинала).
- `og:image` и JSON-LD — без AVIF (соцсети его не понимают).
- Новых зависимостей, Node и CDN не добавлять; миграции не нужны (`ImageSpecField` — не поле БД) — проверяется `makemigrations --check`.

## Review Focus

1. Исходник фото удалён с диска или битый → страница отдаётся (200), у карточки — заглушка, у слайдера слайд пропущен; никаких пустых `<source>`/`<img src="">` (задачи 2, 3).
2. AVIF-спека падает (сборка Pillow без AVIF) → `<img>` с WebP без `<source type="image/avif">` (задача 2).
3. У модели нет AVIF-двойника (логотипы партнёров) → обычный `<img>` без `<picture>` (задача 2).
4. Подпись фото с кавычками и `<` → экранируется в `alt` (задача 2).
5. Фото только что загружено, фоновая генерация ещё не прошла → миниатюра создаётся при первом показе, как раньше; `prune_image_cache` не удаляет свежие файлы (задачи 6, 7).

---

## Файлы

- Modify: `src/apps/core/fields.py` — `image_spec(fmt=…)`, `image_specs`, `full_spec`, `og_spec`, константы опций.
- Modify: `src/apps/core/images.py` — `picture_html`, `lightbox_url`, стратегия `GenerateAfterCommit`, `run_in_background`.
- Modify: `src/apps/core/templatetags/site_tags.py` — тег `picture`, фильтр `lightbox_url`.
- Modify: модели `src/apps/catalog/models.py`, `src/apps/content/models.py`, `src/apps/core/models.py` — новые спеки.
- Modify: views `src/apps/catalog/views.py`, `src/apps/content/views.py` — шапка категории, `og`-картинки.
- Modify: шаблоны `catalog/home.html`, `catalog/category.html`, `catalog/partials/{category_card,service_card,slider}.html`, `content/{events,event,gallery,about}.html`, `content/partials/{event_card,review_card,photo_strip}.html`.
- Modify: `src/config/settings.py` — `IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY`.
- Create: `src/apps/core/management/commands/prune_image_cache.py`.
- Tests: Create `src/tests/test_images.py`; Modify `src/tests/conftest.py`, `src/tests/test_pages.py`, `src/tests/test_seo.py`.
- Docs: `CLAUDE.md`, `README.md`, `docs/decisions.md`; удалить `docs/superpowers/plans/2026-10-09-avif-thumbnails.md`.

---

### Task 1: Спеки — AVIF-двойники, слайды 16:9, `full`, `og`

**Files:**
- Modify: `src/apps/core/fields.py`
- Modify: `src/apps/catalog/models.py`, `src/apps/content/models.py`, `src/apps/core/models.py`
- Test: `src/tests/test_images.py` (новый)

**Interfaces:**
- Produces: `image_spec(source, w, h, *, crop=True, fmt="WEBP") -> ImageSpecField`; `image_specs(source, w, h, *, crop=True) -> tuple[ImageSpecField, ImageSpecField]` (WebP, AVIF); `full_spec(source)`; `og_spec(source)`.
- Produces (спеки моделей):
  - `Category`: `preview_card`/`_avif` 640×427, `preview_large`/`_avif` 1080×720, `og`;
  - `CategoryPhoto`: `slide`/`_avif` 1600×900, `slide_small`/`_avif` 800×450 (обе `fill`), `thumb` (админка), `full`, `og`;
  - `ServicePhoto`: то же + `card`/`_avif` 640×480, `row`/`_avif` 336×336;
  - `Event`: `card`/`_avif` 800×600, `card_small`/`_avif` 640×480, `og`;
  - `Review`: `avatar`/`_avif`;
  - `GalleryPhoto`: `thumb`/`_avif` 600², `thumb_small`/`_avif` 400², `full`;
  - `SiteSettings`: `about_card`/`_avif`, `founder_card`/`_avif`, `about_og`, `og_card` (теперь JPEG через `og_spec`);
  - `Partner.logo_small` — без изменений (логотипы с текстом, AVIF не нужен).

- [ ] **Step 1: Failing tests** — `src/tests/test_images.py`:

```python
from PIL import Image

from apps.catalog.models import Category, CategoryPhoto
from apps.content.models import GalleryPhoto
from apps.core.models import SiteSettings


def _open(spec):
    return Image.open(spec.path)


def test_slide_is_cut_to_16_9_so_srcset_widths_are_true(make_image):
    photo = CategoryPhoto.objects.create(
        category=Category.objects.create(name="Сплавы"), image=make_image(size=(1200, 900))
    )
    assert _open(photo.slide).size == (1600, 900)
    assert _open(photo.slide_small).size == (800, 450)
    assert _open(photo.slide_avif).format == "AVIF"


def test_gallery_photo_specs(make_image):
    photo = GalleryPhoto.objects.create(image=make_image(size=(1200, 800)))
    assert (_open(photo.thumb).format, _open(photo.thumb).size) == ("WEBP", (600, 600))
    assert (_open(photo.thumb_small_avif).format, _open(photo.thumb_small_avif).size) == ("AVIF", (400, 400))
    assert (_open(photo.full).format, _open(photo.full).size) == ("WEBP", (1200, 800))  # без увеличения


def test_og_images_are_jpeg_1200x630(make_image):
    site = SiteSettings.load()
    site.og_image = make_image(size=(1300, 700))
    site.save()
    assert (_open(site.og_card).format, _open(site.og_card).size) == ("JPEG", (1200, 630))
    category = Category.objects.create(name="Байдарки", preview=make_image(size=(1080, 720)))
    assert _open(category.og).format == "JPEG"
```

- [ ] **Step 2:** `cd src && uv run pytest tests/test_images.py -v` → FAIL (`slide` 1200×900, нет `slide_avif`/`thumb_small_avif`/`full`/`og`).

- [ ] **Step 3: Implement** — в `src/apps/core/fields.py` заменить `image_spec`:

```python
WEBP_OPTIONS = {"quality": 80}
# AVIF q55 при speed=6 почти вдвое легче WebP q80 при том же виде и кодируется так же быстро
# (speed=4 — в 5–6 раз дольше при выигрыше в пару килобайт). Замеры — docs/superpowers/plans/2026-10-11-image-delivery.md.
AVIF_OPTIONS = {"quality": 55, "speed": 6}


def image_spec(source: str, width: int, height: int, *, crop: bool = True, fmt: str = "WEBP") -> ImageSpecField:
    processor = ResizeToFill(width, height) if crop else ResizeToFit(width, height, upscale=False)
    options = AVIF_OPTIONS if fmt == "AVIF" else WEBP_OPTIONS
    return ImageSpecField(source=source, processors=[processor], format=fmt, options=options)


def image_specs(source: str, width: int, height: int, *, crop: bool = True) -> tuple[ImageSpecField, ImageSpecField]:
    """Миниатюра в WebP и её AVIF-двойник: `card, card_avif = image_specs(...)`.

    `{% picture %}` находит двойник по суффиксу `_avif` и отдаёт его через `<source type="image/avif">`.
    """
    return image_spec(source, width, height, crop=crop), image_spec(source, width, height, crop=crop, fmt="AVIF")


def full_spec(source: str) -> ImageSpecField:
    """Фото во весь экран (GLightbox): WebP на четверть легче JPEG-оригинала; AVIF лайтбокс выбрать не умеет."""
    return image_spec(source, 1920, 1080, crop=False)


def og_spec(source: str) -> ImageSpecField:
    """Картинка для соцсетей (og:image) — JPEG 1200×630: WebP и AVIF понимают не все соцсети и мессенджеры."""
    return ImageSpecField(
        source=source,
        processors=[ResizeToFill(1200, 630)],
        format="JPEG",
        options={"quality": 82, "progressive": True},
    )
```

Модели (импорты — `image_spec, image_specs, full_spec, og_spec` по необходимости):

```python
# catalog/models.py, Category
    preview_card, preview_card_avif = image_specs("preview", 640, 427)
    preview_large, preview_large_avif = image_specs("preview", 1080, 720)  # шапка страницы категории: srcset с preview_card
    og = og_spec("preview")

# CategoryPhoto
    # Слайдер — рамка 16:9 с object-cover: режем так же на сервере, чтобы ширины в srcset были настоящими.
    slide, slide_avif = image_specs("image", 1600, 900)
    slide_small, slide_small_avif = image_specs("image", 800, 450)  # слайдер на телефоне: srcset со slide
    thumb = image_spec("image", 320, 240)
    full = full_spec("image")
    og = og_spec("image")

# ServicePhoto — как CategoryPhoto, плюс
    card, card_avif = image_specs("image", 640, 480)
    row, row_avif = image_specs("image", 336, 336)  # квадрат в строке услуги на телефоне (112 px × 3)

# content/models.py, Event
    card, card_avif = image_specs("image", 800, 600)
    card_small, card_small_avif = image_specs("image", 640, 480)  # карточки в сетке и на телефоне: srcset с card
    og = og_spec("image")

# Review
    avatar, avatar_avif = image_specs("photo", 160, 160)

# GalleryPhoto
    thumb, thumb_avif = image_specs("image", 600, 600)
    thumb_small, thumb_small_avif = image_specs("image", 400, 400)  # сетка на телефоне: srcset с thumb
    full = full_spec("image")

# core/models.py, SiteSettings
    about_card, about_card_avif = image_specs("about_photo", 960, 720)
    about_og = og_spec("about_photo")
    founder_card, founder_card_avif = image_specs("founder_photo", 600, 750)
    og_card = og_spec("og_image")
```

- [ ] **Step 4:** `uv run pytest tests/test_images.py -v` → PASS; `uv run manage.py makemigrations --check --dry-run` → «No changes detected»; `uv run pytest` — остальные тесты зелёные (шаблоны пока на `spec_url`).

- [ ] **Step 5: Commit** — `git commit -m "Миниатюры: AVIF-двойники, слайды 16:9, спеки full и og"`.

---

### Task 2: Тег `{% picture %}` и `lightbox_url`

**Files:**
- Modify: `src/apps/core/images.py`, `src/apps/core/templatetags/site_tags.py`
- Test: `src/tests/test_images.py`

**Interfaces:**
- Consumes: `safe_spec_url(obj, name) -> str`.
- Produces: `picture_html(obj, srcset: str, *, sizes="", wide="", media="", **attrs) -> str` (SafeString или `""`); тег `{% picture obj "спека" | "спека 640w, спека 800w" sizes=… wide=… media=… alt=… class=… [as var] %}`; `lightbox_url(photo) -> str`; фильтр `{{ photo|lightbox_url }}`.
- Правила: `src` — WebP последней спеки списка; `srcset`/`sizes` у `<img>` и `<source>` — только если в списке есть дескрипторы; атрибут с пустым значением не выводится (кроме `alt`); нет ни одного WebP-URL → `""`; нет AVIF-источников → голый `<img>`.

- [ ] **Step 1: Failing tests** — дописать в `src/tests/test_images.py`:

```python
import pytest
from django.template import Context, Template

from apps.core.images import lightbox_url, picture_html


class _Spec:
    def __init__(self, url):
        self.url = url


class Photo:
    card_small = _Spec("/m/card_small.webp")
    card = _Spec("/m/card.webp")
    card_small_avif = _Spec("/m/card_small.avif")
    card_avif = _Spec("/m/card.avif")
    row = _Spec("/m/row.webp")
    row_avif = _Spec("/m/row.avif")


class NoAvif:
    logo = _Spec("/m/logo.webp")


class BrokenAvif:
    card = _Spec("/m/card.webp")

    @property
    def card_avif(self):
        raise OSError("нет кодировщика AVIF")


def test_picture_with_srcset():
    html = picture_html(Photo(), "card_small 640w, card 800w", sizes="50vw", alt="", width=800, loading="lazy")
    assert html == (
        '<picture><source type="image/avif" srcset="/m/card_small.avif 640w, /m/card.avif 800w" sizes="50vw">'
        '<img src="/m/card.webp" srcset="/m/card_small.webp 640w, /m/card.webp 800w" sizes="50vw"'
        ' alt="" width="800" loading="lazy"></picture>'
    )


def test_picture_single_spec_has_no_sizes():
    assert picture_html(Photo(), "card", alt="x") == (
        '<picture><source type="image/avif" srcset="/m/card.avif"><img src="/m/card.webp" alt="x"></picture>'
    )


def test_picture_art_direction():
    html = picture_html(Photo(), "row", wide="card", media="(min-width: 640px)", alt="")
    assert html == (
        '<picture><source media="(min-width: 640px)" type="image/avif" srcset="/m/card.avif">'
        '<source media="(min-width: 640px)" type="image/webp" srcset="/m/card.webp">'
        '<source type="image/avif" srcset="/m/row.avif"><img src="/m/row.webp" alt=""></picture>'
    )


def test_picture_without_avif_twin_is_plain_img():
    assert picture_html(NoAvif(), "logo", alt="Партнёр") == '<img src="/m/logo.webp" alt="Партнёр">'


def test_picture_survives_broken_avif():
    assert picture_html(BrokenAvif(), "card", alt="") == '<img src="/m/card.webp" alt="">'


def test_picture_empty_without_source():
    assert picture_html(None, "card") == ""
    assert picture_html(object(), "card") == ""


def test_picture_drops_empty_attrs_but_keeps_alt_and_escapes():
    html = picture_html(NoAvif(), "logo", alt='«Т-Парк» <b>"', loading="", fetchpriority="high")
    assert html == '<img src="/m/logo.webp" alt="«Т-Парк» &lt;b&gt;&quot;" fetchpriority="high">'


def test_picture_rejects_mixed_srcset():
    with pytest.raises(ValueError):
        picture_html(Photo(), "card_small 640w, card")


def test_picture_tag_as_variable():
    html = Template(
        '{% load site_tags %}{% picture obj "card" alt="" as pic %}{% if pic %}[{{ pic }}]{% else %}нет{% endif %}'
    ).render(Context({"obj": Photo()}))
    assert html.startswith("[<picture>") and html.endswith("</picture>]")
    assert Template('{% load site_tags %}{% picture obj "card" as pic %}{% if pic %}да{% else %}нет{% endif %}').render(
        Context({"obj": None})
    ) == "нет"


def test_lightbox_url_prefers_full_spec(make_image):
    photo = GalleryPhoto.objects.create(image=make_image())
    assert lightbox_url(photo) == photo.full.url and photo.full.url.endswith(".webp")
```

(тестам с моделями нужен `pytestmark = pytest.mark.django_db` в начале модуля — модели создаются в задаче 1.)

- [ ] **Step 2:** `uv run pytest tests/test_images.py -v` → FAIL (`ImportError: picture_html`).

- [ ] **Step 3: Implement** — `src/apps/core/images.py`:

```python
import logging

from django.forms.utils import flatatt
from django.utils.html import format_html
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

AVIF_SUFFIX = "_avif"


def safe_spec_url(obj, spec_name: str) -> str: ...  # без изменений


def lightbox_url(photo) -> str:
    """Фото для просмотра во весь экран: WebP-спека `full`, без неё — оригинал."""
    if url := safe_spec_url(photo, "full"):
        return url
    try:
        return photo.image.url
    except (AttributeError, ValueError):
        return ""


def _entries(srcset: str) -> list[tuple[str, str]]:
    entries = [item.split() for item in srcset.split(",") if item.strip()]
    if not entries or any(len(e) > 2 for e in entries) or (len(entries) > 1 and any(len(e) != 2 for e in entries)):
        raise ValueError(f"Неверный список спек {srcset!r}: нужно «спека» или «спека 640w, спека 800w».")
    return [(e[0], e[1] if len(e) == 2 else "") for e in entries]


def _candidates(obj, entries, suffix: str = "") -> list[tuple[str, str]]:
    """[(url, дескриптор)] по объявленным у модели спекам; битые и отсутствующие пропускаются."""
    found = []
    for name, descriptor in entries:
        name += suffix
        if suffix and not hasattr(type(obj), name):
            continue
        if url := safe_spec_url(obj, name):
            found.append((url, descriptor))
    return found


def _srcset(candidates) -> str:
    return ", ".join(f"{url} {descriptor}".rstrip() for url, descriptor in candidates)


def _tag(name: str, **attrs) -> str:
    return format_html("<{}{}>", name, flatatt({k: v for k, v in attrs.items() if v is not None and v is not False}))


def picture_html(obj, srcset: str, *, sizes: str = "", wide: str = "", media: str = "", **attrs) -> str:
    """`<picture>`: AVIF-двойники спек (`<спека>_avif`) в `<source>`, WebP — в `<img>`.

    srcset — «спека» или «спека 640w, спека 800w» (src — последняя); wide + media — другой кадр
    для широких экранов (<source media>). Атрибуты `<img>` с пустым значением не выводятся, кроме alt.
    Пустая строка, если ни одной миниатюры нет (исходника нет или он битый).
    """
    if obj is None:
        return ""
    entries = _entries(srcset)
    webp = _candidates(obj, entries)
    if not webp:
        return ""
    multi = any(descriptor for _, descriptor in entries)
    sources = []
    if wide:
        wide_entries = _entries(wide)
        wide_sizes = sizes if any(d for _, d in wide_entries) else None
        for suffix, mime in ((AVIF_SUFFIX, "image/avif"), ("", "image/webp")):
            if found := _candidates(obj, wide_entries, suffix):
                sources.append(_tag("source", media=media, type=mime, srcset=_srcset(found), sizes=wide_sizes))
    if avif := _candidates(obj, entries, AVIF_SUFFIX):
        sources.append(_tag("source", type="image/avif", srcset=_srcset(avif), sizes=sizes if multi else None))
    img_attrs = {"src": webp[-1][0]}
    if multi:
        img_attrs |= {"srcset": _srcset(webp), "sizes": sizes or None}
    img_attrs |= {k: v for k, v in attrs.items() if k == "alt" or v != ""}
    img = _tag("img", **img_attrs)
    return mark_safe(f"<picture>{''.join(sources)}{img}</picture>") if sources else img
```

`src/apps/core/templatetags/site_tags.py`:

```python
from apps.core.images import lightbox_url as _lightbox_url
from apps.core.images import picture_html, safe_spec_url


@register.simple_tag
def picture(obj, srcset: str, **kwargs) -> str:
    """`{% picture photo "card_small 640w, card 800w" sizes="…" alt="" class="…" %}` — см. picture_html."""
    return picture_html(obj, srcset, **kwargs)


@register.filter
def lightbox_url(photo) -> str:
    return _lightbox_url(photo)
```

- [ ] **Step 4:** `uv run pytest tests/test_images.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "Тег {% picture %}: AVIF с запасным WebP, srcset и sizes"`.

---

### Task 3: Шаблоны витрины на `{% picture %}`, лайтбокс на `full`

**Files:**
- Modify: `catalog/home.html`, `catalog/category.html` (лента «Другие направления» и скрытые ссылки лайтбокса), `catalog/partials/{category_card,service_card,slider}.html`, `content/{events,event,gallery,about}.html`, `content/partials/{event_card,review_card,photo_strip}.html`
- Test: `src/tests/test_pages.py`, `src/tests/test_pages_home.py`

**Interfaces:**
- Consumes: `{% picture %}`, `|lightbox_url` (задача 2); спеки задачи 1.
- `category_card.html` теперь требует переменную `sizes` от подключающего шаблона.

`sizes` (контейнер `max-w-6xl` = 1152 px, поля `px-4`):

| Где | Набор | sizes |
|---|---|---|
| Карточка категории, сетка 3 | `preview_card 640w, preview_large 1080w` | `(min-width: 1152px) 357px, (min-width: 1024px) calc((100vw - 80px) / 3), (min-width: 640px) calc(50vw - 28px), calc(50vw - 22px)` |
| Карточка категории, wide | то же | `(min-width: 1152px) 548px, (min-width: 640px) calc(50vw - 28px), calc(50vw - 22px)` |
| Карточка категории, лента «Другие» | то же | `(min-width: 1152px) 268px, (min-width: 1024px) calc((100vw - 80px) / 4), (min-width: 640px) calc(50vw - 24px), 44vw` |
| Галерея (2/3/4 колонки, gap 12) | `thumb_small 400w, thumb 600w` | `(min-width: 1152px) 271px, (min-width: 1024px) calc((100vw - 68px) / 4), (min-width: 768px) calc((100vw - 56px) / 3), calc((100vw - 44px) / 2)` |
| Полоса фото (2/3/6 колонок) | то же | `(min-width: 1152px) 177px, (min-width: 1024px) calc((100vw - 92px) / 6), (min-width: 768px) calc((100vw - 56px) / 3), calc((100vw - 44px) / 2)` |
| Страница мероприятия | `card_small 640w, card 800w` | `(min-width: 1152px) 752px, (min-width: 1024px) calc(100vw - 400px), calc(100vw - 32px)` |
| Слайдер, карточки мероприятий | без изменений | без изменений |

- [ ] **Step 1: Failing tests** — в `tests/test_pages.py`:
  - `test_category_page_lists_services`: `assert f'data-full="{category.photos.get().full.url}"' in html`.
  - `test_service_card_picture_and_slider_srcset`: ожидать `'<picture><source media="(min-width: 640px)" type="image/avif" srcset="'` в карточке; в слайдере — `srcset="[^"]+\.avif 800w, [^"]+\.avif 1600w" sizes="(min-width: 1152px) 1120px, calc(100vw - 32px)"` у `<source>` и тот же `sizes` у `<img>` с `.webp`.
  - новые:

```python
def test_gallery_thumbs_avif_srcset_and_light_lightbox(client, make_image):
    photo = GalleryPhoto.objects.create(image=make_image(), caption='Закат "у реки"')
    html = client.get("/gallery/").content.decode()
    assert f'<a href="{photo.full.url}" class="glightbox' in html
    assert re.search(r'<source type="image/avif" srcset="[^"]+\.avif 400w, [^"]+\.avif 600w" sizes="\(min-width: 1152px\) 271px', html)
    assert 'alt="Закат &quot;у реки&quot;"' in html


def test_category_page_survives_missing_photo_file(client, category, media_root):
    photo = category.photos.get()
    (media_root / photo.image.name).unlink()
    response = client.get(category.get_absolute_url())
    assert response.status_code == 200
    assert 'src=""' not in response.content.decode()
```

  - `tests/test_pages_home.py::test_home_first_screen_cards_load_eagerly` оставить как есть (проверяет `<img>` с `catalog/previews`), добавить: `assert all("preview_large" not in t for t in imgs)` не нужно — вместо этого `assert '<source type="image/avif"' in html` для карточек.

- [ ] **Step 2:** `uv run pytest tests/test_pages.py tests/test_pages_home.py tests/test_seo.py -v` → новые/изменённые FAIL.

- [ ] **Step 3: Implement** (ключевые фрагменты):

`catalog/partials/category_card.html`:

```django
{% load static site_tags %}
{# … прежний комментарий; sizes передаёт подключающий шаблон (сетка или лента). #}
<a href="…" class="…">
  {% if lcp and category in first_screen %}{% if category == first_screen.0 %}{% firstof "high" as card_priority %}{% else %}{% firstof "async" as card_decoding %}{% endif %}{% else %}{% firstof "lazy" as card_loading %}{% endif %}
  {% picture category "preview_card 640w, preview_large 1080w" sizes=sizes alt="" width=640 height=427 fetchpriority=card_priority decoding=card_decoding loading=card_loading class="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" as image %}
  {% if image %}{{ image }}{% else %}<img src="{% static 'img/logo.png' %}" alt="" class="absolute inset-0 m-auto w-1/2 opacity-30">{% endif %}
  …
```

`catalog/home.html` — в обоих `include` добавить `sizes="…"` из таблицы; `catalog/category.html` — `{% include "catalog/partials/category_card.html" with sizes="…лента…" %}`.

`catalog/partials/service_card.html`:

```django
    {% picture service.cover "row" wide="card" media="(min-width: 640px)" alt="" width=640 height=480 loading="lazy" class="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105" as image %}
    {% if image %}{{ image }}{% else %}<img src="{% static 'img/logo.png' %}" alt="" class="absolute inset-0 m-auto w-2/3 opacity-30">{% endif %}
```

`catalog/partials/slider.html`:

```django
    {% for photo in photos %}{% with n=forloop.counter|stringformat:"s" %}{% with photo_alt=alt|add:" — фото "|add:n %}
    {% picture photo "slide_small 800w, slide 1600w" sizes=sizes alt=photo_alt width=1600 height=900 fetchpriority=forloop.first|yesno:"high," loading=forloop.first|yesno:",lazy" class="aspect-[16/9] w-full cursor-zoom-in object-cover" as image %}
    {% if image %}<div class="swiper-slide" data-full="{{ photo|lightbox_url }}">{{ image }}</div>{% endif %}
    {% endwith %}{% endwith %}{% endfor %}
```

`content/gallery.html` (ссылка — на `full`):

```django
    {% for photo in photos %}{% with n=forloop.counter|stringformat:"s" %}{% with fallback="Т-Парк, Калужская область — фото "|add:n %}
    {% picture photo "thumb_small 400w, thumb 600w" sizes="…галерея…" alt=photo.caption|default:fallback width=600 height=600 loading="lazy" class="h-full w-full object-cover transition duration-500 group-hover:scale-105" as image %}{% if image %}
    <a href="{{ photo|lightbox_url }}" class="glightbox group block aspect-square overflow-hidden rounded-xl bg-sand-200" data-gallery="gallery"…>{{ image }}</a>
    {% endif %}{% endwith %}{% endwith %}{% endfor %}
```

`content/partials/photo_strip.html` — так же, `fallback="Т-Парк — фото "|add:n`, sizes «полоса».

`content/partials/event_card.html` / `content/events.html` — `{% picture event "card_small 640w, card 800w" sizes="(прежние)" alt="" width=800 height=600 loading="lazy"|fetchpriority="high" class="(прежние)" as image %}` + заглушка-логотип в `{% else %}`.

`content/event.html` — `{% picture event "card_small 640w, card 800w" sizes="…мероприятие…" alt=event.title width=800 height=600 fetchpriority="high" class="aspect-[4/3] w-full rounded-2xl object-cover" %}`.

`content/partials/review_card.html` — `{% picture review "avatar" alt="" width=160 height=160 loading="lazy" class="h-11 w-11 shrink-0 rounded-full object-cover" as avatar %}{% if avatar %}{{ avatar }}{% else %}(иконка){% endif %}`.

`content/about.html` — вместо `{% with hero=… founder_photo=… %}` (и парного `{% endwith %}`) в начале блока:

```django
{% picture site "about_card" alt="Т-Парк" width=960 height=720 fetchpriority="high" class="aspect-[4/3] w-full rounded-2xl object-cover shadow-lg" as hero %}
{% picture site "founder_card" alt=site.founder_name width=600 height=750 loading="lazy" class="aspect-[4/5] w-full max-w-sm rounded-2xl object-cover shadow-lg" as founder_photo %}
```

и в разметке `{% if hero %}{{ hero }}{% endif %}`, `{% if founder_photo %}{{ founder_photo }}{% endif %}`; логотипы партнёров — `{% picture partner "logo_small" alt=… loading="lazy" class="h-auto w-full" as logo %}` (без AVIF-двойника получится обычный `<img>`).

`catalog/home.html` (шапка) — `{% picture site "about_card" alt="Т-Парк" width=960 height=720 fetchpriority="high" class="aspect-[4/3] w-full rounded-2xl object-cover shadow-lg" %}` в `{% if hero %}`.

- [ ] **Step 4:** `uv run pytest` → PASS; `uv run manage.py tailwind build` и глазами (dev-сервер, `current_content`): главная (карточки, шапка), категория (слайдер, карточки услуг на телефоне и ПК), галерея (лайтбокс открывает `.webp`), «О нас», мероприятия. В DevTools → Network: грузятся `.avif`.
- [ ] **Step 5: Commit** — `git commit -m "Витрина: фото через {% picture %} (AVIF + WebP), лайтбокс — WebP вместо JPEG"`.

---

### Task 4: Шапка категории — `srcset` до 1080 px

**Files:**
- Modify: `src/apps/catalog/views.py` (`category_detail`), `src/templates/catalog/category.html`
- Test: `src/tests/test_pages.py`

**Interfaces:**
- Consumes: `lightbox_url`, `picture_html` через тег; спеки `preview_card`/`preview_large`, `slide_small`/`slide`, `og`.
- Produces: контекст `hero` (объект — категория или первое фото, либо `None`), `hero_srcset` (str), `hero_full` (URL для лайтбокса).

- [ ] **Step 1: Failing tests** — в `test_category_hero_opens_full_photo` заменить `photo.image.url`/`second.image.url` на `photo.full.url`/`second.full.url` (превью категории остаётся `category.preview.url`), и добавить:

```python
def test_category_hero_srcset_up_to_1080(client, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True, preview=make_image(size=(1080, 720)))
    html = client.get(category.get_absolute_url()).content.decode()
    hero = html.split('data-gallery="category">')[1].split("</a>")[0]
    assert re.search(r'srcset="[^"]+\.avif 640w, [^"]+\.avif 1080w" sizes="\(min-width: 1152px\) 536px', hero)
    assert 'fetchpriority="high"' in hero and 'width="1080" height="720"' in hero
```

- [ ] **Step 2:** `uv run pytest tests/test_pages.py -k category_hero -v` → FAIL.

- [ ] **Step 3: Implement** — `category_detail`:

```python
    # Шапка: превью категории, без него — первое фото. Полноразмерное — для просмотра на весь экран.
    if safe_spec_url(category, "preview_card"):
        hero, hero_srcset, hero_full = category, "preview_card 640w, preview_large 1080w", category.preview.url
    elif photos and safe_spec_url(photos[0], "slide"):
        hero, hero_srcset, hero_full = photos[0], "slide_small 800w, slide 1600w", lightbox_url(photos[0])
    else:
        hero, hero_srcset, hero_full = None, "", ""
```

в контексте `"hero": hero, "hero_srcset": hero_srcset, "hero_full": hero_full`, `make_seo(..., absolute_url(request, safe_spec_url(hero, "og")), ...)`.

`category.html`:

```django
    <a href="{{ hero_full }}" class="glightbox block cursor-zoom-in" data-gallery="category">{% picture hero hero_srcset sizes="(min-width: 1152px) 536px, (min-width: 1024px) calc(50vw - 40px), calc(100vw - 32px)" alt=category.name width=1080 height=720 fetchpriority="high" class="aspect-[16/9] w-full lg:aspect-[3/2] rounded-2xl object-cover shadow-lg" %}</a>
    {% for photo in photos %}{% with full=photo|lightbox_url %}{% if full and full != hero_full %}<a href="{{ full }}" class="glightbox" data-gallery="category" hidden></a>{% endif %}{% endwith %}{% endfor %}
```

- [ ] **Step 4:** `uv run pytest` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "Шапка категории: srcset 640/1080 вместо одной миниатюры 640"`.

---

### Task 5: `og:image` — JPEG 1200×630

**Files:**
- Modify: `src/apps/catalog/views.py` (`service_detail`), `src/apps/content/views.py` (`event_detail`, `about`); `context_processors.py` и `structured_data.py` уже берут `og_card` (теперь JPEG).
- Test: `src/tests/test_seo.py`

- [ ] **Step 1: Failing tests** — в `test_category_meta` и `test_default_og_image` заменить проверку на
  `assert re.search(r'property="og:image" content="http://testserver/media/CACHE/images/[^"]+\.jpg"', html)`; добавить такую же для страницы услуги с фото, мероприятия с фото и «О нас» с `about_photo`.
- [ ] **Step 2:** `uv run pytest tests/test_seo.py -v` → FAIL (`.webp`).
- [ ] **Step 3: Implement** — `service_detail`: `image = safe_spec_url(photos[0], "og") if photos else ""`; `event_detail`: `safe_spec_url(event, "og")`; `about`: `safe_spec_url(site, "about_og")`. (Категория — в задаче 4.)
- [ ] **Step 4:** `uv run pytest` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "og:image — JPEG 1200×630 для всех страниц"`.

---

### Task 6: Миниатюры создаются в фоне сразу после сохранения фото

**Files:**
- Modify: `src/apps/core/images.py`, `src/config/settings.py`, `src/tests/conftest.py`
- Test: `src/tests/test_images.py`

**Interfaces:**
- Produces: `run_in_background(fn) -> None` (один фоновый поток на процесс); `GenerateAfterCommit` — стратегия imagekit; настройка `IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "apps.core.images.GenerateAfterCommit"`.

Почему: у галерейного фото теперь 5 спек (~0,25 с пережатия), у фото услуги — 11. С ленивой генерацией первый посетитель галереи после загрузки пачки из 20 фото ждал бы ~5 с; генерация прямо при сохранении упёрлась бы в таймаут gunicorn (30 с) на пачке.

- [ ] **Step 1: Failing test** — в `conftest.py` autouse-фикстура (фоновые потоки в тестах не нужны):

```python
@pytest.fixture(autouse=True)
def no_background_thumbnails(monkeypatch):
    """Миниатюры после сохранения создаются в фоновом потоке; в тестах — нет (по требованию тест подменяет сам)."""
    monkeypatch.setattr("apps.core.images.run_in_background", lambda fn: None)
```

в `test_images.py`:

```python
from apps.core import images


def test_thumbnails_generated_after_commit(monkeypatch, django_capture_on_commit_callbacks, make_image):
    monkeypatch.setattr(images, "run_in_background", lambda fn: fn())
    with django_capture_on_commit_callbacks(execute=True):
        photo = GalleryPhoto.objects.create(image=make_image())
    storage = photo.image.storage
    assert all(storage.exists(getattr(photo, name).name) for name in ("thumb", "thumb_avif", "thumb_small_avif", "full"))


def test_missing_thumbnail_still_generated_on_view(make_image):
    photo = GalleryPhoto.objects.create(image=make_image())  # on_commit в тесте не выполняется
    storage = photo.image.storage
    assert not storage.exists(photo.thumb_avif.name)
    assert photo.thumb_avif.url and storage.exists(photo.thumb_avif.name)
```

- [ ] **Step 2:** `uv run pytest tests/test_images.py -k "after_commit or on_view" -v` → FAIL (первый).
- [ ] **Step 3: Implement** — `images.py`:

```python
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from django.db import transaction
from imagekit.cachefiles.strategies import JustInTime

_executor: ThreadPoolExecutor | None = None


def run_in_background(fn) -> None:
    """Один фоновый поток на процесс: пережатие не отнимает все ядра у запросов."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="thumbnails")
    _executor.submit(fn)


def _generate(file) -> None:
    try:
        file.generate()
    except Exception:
        logger.warning("Не удалось создать миниатюру %s", file.name, exc_info=True)


class GenerateAfterCommit(JustInTime):
    """Как JustInTime (недостающая миниатюра создаётся при показе), но после сохранения фото все его миниатюры
    сразу создаются в фоне: первый посетитель не ждёт пережатия, а загрузка пачкой не упирается в таймаут gunicorn."""

    def on_source_saved(self, file):
        transaction.on_commit(lambda: run_in_background(partial(_generate, file)))
```

`settings.py` (рядом с `MEDIA_*`):

```python
# Миниатюры: недостающие создаются при показе, после сохранения фото — сразу в фоне (apps.core.images).
IMAGEKIT_DEFAULT_CACHEFILE_STRATEGY = "apps.core.images.GenerateAfterCommit"
```

- [ ] **Step 4:** `uv run pytest` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "Миниатюры создаются в фоне сразу после сохранения фото"`.

---

### Task 7: Команда `prune_image_cache`

**Files:**
- Create: `src/apps/core/management/commands/prune_image_cache.py`
- Modify: `README.md` (раздел «Продакшен»)
- Test: `src/tests/test_images.py`

После смены размеров/качества у спек старые файлы в `media/CACHE/images` больше не нужны (после этого плана — слайды и `og_card`). Удалять всю папку нельзя: imagekit в процессе помнит «файл есть» без срока, и до перезапуска сайт отдавал бы битые картинки. Команда удаляет только файлы, которых нет ни у одной текущей спеки, и не трогает свежие (`--min-age`, по умолчанию 60 минут).

- [ ] **Step 1: Failing test:**

```python
import os
import time

from django.core.management import call_command


def test_prune_image_cache(make_image, media_root):
    photo = GalleryPhoto.objects.create(image=make_image())
    kept = media_root / photo.thumb.url.removeprefix("/media/")  # url создаёт файл
    stale = media_root / "CACHE/images/gallery/old/stale.webp"
    fresh = media_root / "CACHE/images/gallery/old/fresh.webp"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"x")
    fresh.write_bytes(b"x")
    hour_ago = time.time() - 2 * 3600
    os.utime(stale, (hour_ago, hour_ago))

    call_command("prune_image_cache", "--dry-run")
    assert stale.exists()

    call_command("prune_image_cache")
    assert not stale.exists() and fresh.exists() and kept.exists()
```

- [ ] **Step 2:** `uv run pytest tests/test_images.py -k prune -v` → FAIL (`Unknown command`).
- [ ] **Step 3: Implement:**

```python
"""Удаляет миниатюры imagekit, которые не нужны ни одной текущей спеке."""

import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from imagekit.registry import cachefile_registry, generator_registry


def expected_cache_files() -> set[str]:
    """Имена (относительно MEDIA_ROOT) всех миниатюр текущих спек для всех фото в базе."""
    names = set()
    for generator_id in generator_registry.get_ids():
        for file in cachefile_registry.get(generator_id):
            if file.name:
                names.add(file.name)
    return names


class Command(BaseCommand):
    help = "Удаляет из CACHE/images миниатюры, не нужные ни одной текущей спеке (остаются после смены размеров или качества)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Только показать, сколько будет удалено.")
        parser.add_argument(
            "--min-age", type=int, default=60,
            help="Не трогать файлы моложе стольких минут (по умолчанию 60): их могли создать для только что загруженного фото.",
        )

    def handle(self, *args, dry_run=False, min_age=60, **options):
        media = Path(settings.MEDIA_ROOT)
        cache_dir = media / settings.IMAGEKIT_CACHEFILE_DIR
        if not cache_dir.is_dir():
            self.stdout.write("Папки миниатюр нет — удалять нечего.")
            return
        keep = expected_cache_files()
        cutoff = time.time() - min_age * 60
        count = size = 0
        for path in sorted(p for p in cache_dir.rglob("*") if p.is_file()):
            stat = path.stat()
            if path.relative_to(media).as_posix() in keep or stat.st_mtime > cutoff:
                continue
            count += 1
            size += stat.st_size
            if not dry_run:
                path.unlink()
        if not dry_run:
            for folder in sorted((p for p in cache_dir.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                if not any(folder.iterdir()):
                    folder.rmdir()
        verb = "Будет удалено" if dry_run else "Удалено"
        self.stdout.write(f"{verb}: {count} файлов, {size / 1024 / 1024:.1f} МБ. Нужных миниатюр: {len(keep)}.")
```

README, после пункта 5 «Бэкап»:

```markdown
6. Миниатюры фото создаются в фоне при старте контейнера и после загрузки фото. Если поменялись размеры или качество миниатюр (`apps/core/fields.py`, модели), после деплоя и генерации удалить ненужные: `docker compose exec tpark-web python manage.py prune_image_cache --dry-run`, затем без `--dry-run`. Папку `media/CACHE` целиком не удалять: до перезапуска сайт будет отдавать битые картинки.
```

- [ ] **Step 4:** `uv run pytest` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "Команда prune_image_cache: удаление устаревших миниатюр"`.

---

### Task 8: Документация и финальная проверка

**Files:**
- Modify: `CLAUDE.md`, `docs/decisions.md`; Delete: `docs/superpowers/plans/2026-10-09-avif-thumbnails.md`.

- [ ] **Step 1:** `CLAUDE.md`:
  - строку про `fields.py` дополнить: `image_specs` (WebP + AVIF-двойник `<спека>_avif`), `full_spec` (лайтбокс, WebP), `og_spec` (JPEG 1200×630);
  - заменить пункт «Миниатюры в шаблонах — только через фильтр `obj|spec_url:"spec"`» на: «Фото витрины — тегом `{% picture obj "спека" | "спека 640w, спека 800w" sizes=… alt=… %}` (`<picture>` с AVIF и запасным WebP; пустой атрибут не выводится, кроме `alt`; `as var` — для заглушки); отдельные URL — `obj|spec_url:"spec"`, лайтбокс — `photo|lightbox_url`. Всё не падает на отсутствующем файле»;
  - упомянуть стратегию `GenerateAfterCommit` (миниатюры в фоне после сохранения) и `prune_image_cache`;
  - убрать ссылку на план AVIF, поправить описание LCP-фото (у карточек мероприятий `srcset` — без изменений).
- [ ] **Step 2:** `docs/decisions.md` — строка 39 в таблицу технических решений:
  `| 39 | **Доставка фото:** AVIF q55/speed 6 с запасным WebP через тег {% picture %}; слайды режутся на сервере под 16:9; лайтбокс — WebP 1920, og:image — JPEG 1200×630; миниатюры — в фоне после сохранения | Вес фото на страницах примерно вдвое меньше, честные srcset, превью в соцсетях работает везде |`.
- [ ] **Step 3:** удалить старый план AVIF.
- [ ] **Step 4: Проверки:**
  - `cd src && uv run pytest` — всё зелёное;
  - `uv run ruff check . && uv run ruff format --check .`;
  - `uv run manage.py makemigrations --check --dry-run`;
  - из корня `uv run --project src pre-commit run --all-files`;
  - вручную на копии `current_content` (`DATABASE_PATH`/`MEDIA_ROOT` во временной папке): `generateimages` (оценить время), главная/категория/галерея — `.avif` в Network, лайтбокс открывает `.webp`, `prune_image_cache --dry-run` показывает старые слайды.
- [ ] **Step 5: Commit** — `git commit -m "Документация: доставка фото (AVIF, picture, prune_image_cache)"`.

## Что не делаем

- `width`/`height` у логотипов партнёров: пропорции у всех разные, а чтобы узнать размеры, нужно открывать файлы при каждом показе. Логотипы ниже первого экрана и с `lazy`, сдвиг вёрстки на глаз не виден.
- Прогрессивный JPEG у загружаемых оригиналов: после перехода лайтбокса на `full` оригиналы посетителям почти не отдаются (кроме превью категории в лайтбоксе, ~1080 px).
- Отдельная миниатюра лайтбокса для телефонов: при 1280 px WebP весит всего на 8% меньше, чем при 1920.
- Lighthouse после деплоя (главная, категория, галерея, «О нас») — ручная проверка, ожидаемо мобильный LCP главной ~2,2–2,4 с.
