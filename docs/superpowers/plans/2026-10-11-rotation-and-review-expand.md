# Ротация подборок и плавное раскрытие отзывов — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** отзывы раскрываются и сворачиваются плавно; полоса фото «Как это выглядит» и блок «Ещё в категории» перестают всегда показывать первые элементы по порядку.

**Architecture:** ротация — на сервере и «посуточная»: общий хелпер `daily_pick` выбирает подмножество детерминированно по дате (местное время) и ключу страницы. В течение дня HTML страницы не меняется от запроса к запросу и одинаков во всех процессах gunicorn, поэтому ETag/304 (`ConditionalGetMiddleware`) продолжают работать, а поисковики видят стабильную страницу; на следующий день набор другой. Порядок выбранного — как в админке. Раскрытие отзыва — Alpine-компонент `reviewCard`: высота анимируется через Web Animations API (`max-height`), затухание низа — CSS-переход зарегистрированного свойства `--review-fade`.

**Tech Stack:** Django 6.1, pytest/pytest-django, Alpine.js (vendored), Tailwind v4 (`django-tailwind-cli`), Playwright (e2e, `make e2e`).

**Spec:** запрос пользователя от 2026-10-11 (три пункта: плавное «Читать полностью»; ротация фото «Как это выглядит» на главной/«О нас»; ротация «Ещё в категории» на странице услуги). Почему ротация посуточная, а не на каждый запрос, — см. «Принятые решения».

## Принятые решения

- **Ротация раз в сутки, а не случайная на каждый запрос.** Случайный набор на каждый запрос меняет HTML → новый ETag → 304 больше не отдаются (CLAUDE.md прямо запрещает менять HTML от запроса к запросу). Перемешивание в браузере (JS) требует отдавать в HTML лишние фото и даёт «перескок» картинок после загрузки. Посуточная ротация — без JS, без лишнего веса, с рабочими 304.
- **Свой набор на каждой странице:** ключи `"home"`, `"about"`, `"reviews"` для полосы фото, `"service:<pk>"` для «Ещё в категории». На главной и «О нас» в один день — разные фото; у разных услуг — разные соседи, поэтому ссылки равномерно получают все услуги категории (полезно и для перелинковки).
- **Порядок выбранного сохраняется** (как в админке) — меняется только состав.
- **Сид — строка** `"<YYYY-MM-DD>:<key>"` в `random.Random(...)`: для `str` сид считается через SHA-512 и не зависит от `PYTHONHASHSEED`, т. е. одинаков во всех воркерах gunicorn. `hash()` использовать нельзя.

## Global Constraints

- Python 3.14, Django 6.1; команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Весь пользовательский текст и комментарии — на русском, в стиле окружающего кода.
- Публичные шаблоны не должны меняться от запроса к запросу (ETag/304 через `ConditionalGetMiddleware`).
- Фронт без Node и CDN; Alpine-компоненты регистрируются в `alpine:init` в скрипте, подключённом в `<head>` **до** `vendor/alpine.min.js` (как `hover_menu.js`).
- Анимации отключаются при `prefers-reduced-motion: reduce`.
- Комментарии `{# … #}` в шаблонах — только однострочные.

## Review Focus

1. **Два запроса в один день → одинаковый ETag и 304.** Любая недетерминированность (сид через `hash()`, `order_by("?")`, `random.sample` без сида) молча убьёт 304 — тесты `test_photo_strip_stable_within_day_keeps_304` и `test_related_services_stable_within_day` (Task 2, 3).
2. **В галерее/категории элементов меньше лимита или нет совсем** — показать всё, что есть, без ошибок — `test_daily_pick_returns_all_when_short` (Task 1), `test_reviews_page_photo_strip` (уже есть).
3. **Двойной клик по «Читать полностью» посреди анимации** — карточка не «прыгает» и не остаётся с `overflow: hidden` — `test_review_double_click_mid_animation` (Task 4).
4. **Короткий отзыв** — без кнопки и без затухания низа текста (маска при `--review-fade: 100%` не должна ничего прятать) — `test_short_review_not_clamped` (Task 4).
5. **Текущая услуга и её одноимённые варианты** никогда не попадают в «Ещё в категории», сколько бы дней ни прошло — `test_related_services_rotate_daily` (Task 3).

---

### Task 1: Хелпер `daily_pick`

**Files:**
- Create: `src/apps/core/rotation.py`
- Test: `src/tests/test_core_helpers.py` (дописать в конец)
- Modify: `CLAUDE.md` (раздел `apps/core`)

**Interfaces:**
- Produces: `apps.core.rotation.daily_pick(items: Sequence[T], k: int, key: object = "", today: date | None = None) -> list[T]` — до `k` элементов `items` в исходном порядке; одинаковые для одной даты и ключа.

- [ ] **Step 1: Написать падающие тесты** — в конец `src/tests/test_core_helpers.py` (импорт `from datetime import date, timedelta` и `from apps.core.rotation import daily_pick` — к остальным импортам вверху файла):

```python
DAY = date(2026, 10, 11)


def test_daily_pick_stable_for_day_and_key():
    items = list(range(20))
    assert daily_pick(items, 6, "home", DAY) == daily_pick(items, 6, "home", DAY)
    assert len(daily_pick(items, 6, "home", DAY)) == 6


def test_daily_pick_keeps_original_order():
    items = list(range(20))
    picked = daily_pick(items, 6, "home", DAY)
    assert picked == sorted(picked)


def test_daily_pick_returns_all_when_short():
    assert daily_pick([3, 1, 2], 6, "home", DAY) == [3, 1, 2]
    assert daily_pick([], 6, "home", DAY) == []


def test_daily_pick_rotates_over_days():
    items = list(range(20))
    seen = set()
    for shift in range(30):
        seen.update(daily_pick(items, 6, "home", DAY + timedelta(days=shift)))
    assert seen == set(items)  # за месяц показан каждый


def test_daily_pick_differs_between_keys():
    items = list(range(20))
    days = [DAY + timedelta(days=shift) for shift in range(5)]
    assert any(daily_pick(items, 6, "home", day) != daily_pick(items, 6, "about", day) for day in days)


def test_daily_pick_defaults_to_local_date(monkeypatch):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: DAY)
    assert daily_pick(list(range(20)), 6, "home") == daily_pick(list(range(20)), 6, "home", DAY)
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `cd src && uv run pytest tests/test_core_helpers.py -k daily_pick -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.core.rotation'`.

- [ ] **Step 3: Реализация** — `src/apps/core/rotation.py`:

```python
"""Ротация подборок витрины: состав меняется раз в сутки, а в течение дня одинаков."""

import random
from collections.abc import Sequence
from datetime import date

from django.utils import timezone


def daily_pick[T](items: Sequence[T], k: int, key: object = "", today: date | None = None) -> list[T]:
    """До k элементов items, выбранных на день today (по умолчанию — сегодня по местному времени) для ключа key.

    Порядок — как в items. Один день и ключ — один и тот же набор во всех процессах gunicorn (сид — строка,
    не hash()): HTML не меняется от запроса к запросу, и ETag/304 продолжают работать. Разные ключи — разные наборы.
    """
    if len(items) <= k:
        return list(items)
    today = today or timezone.localdate()
    rng = random.Random(f"{today.isoformat()}:{key}")
    return [items[i] for i in sorted(rng.sample(range(len(items)), k))]
```

- [ ] **Step 4: Запустить — должны пройти**

Run: `cd src && uv run pytest tests/test_core_helpers.py -k daily_pick -v`
Expected: 6 passed.

- [ ] **Step 5: CLAUDE.md** — в список `apps/core` после пункта `request_cache.py` добавить:

```markdown
  - `rotation.py` — `daily_pick(items, k, key)`: подборка витрины, которая меняется раз в сутки (сид — дата + ключ страницы), а в течение дня одинакова во всех воркерах — ETag/304 не ломаются; порядок — как в исходном списке. Через него — полоса фото «Как это выглядит» (`GalleryPhoto.strip`) и «Ещё в категории» на странице услуги;
```

- [ ] **Step 6: Commit**

```bash
git add src/apps/core/rotation.py src/tests/test_core_helpers.py CLAUDE.md
git commit -m "Ротация подборок: хелпер daily_pick (раз в сутки, без поломки ETag)"
```

---

### Task 2: Ротация полосы фото «Как это выглядит»

**Files:**
- Modify: `src/apps/content/models.py:205-217` (`GalleryPhoto`)
- Modify: `src/apps/content/views.py:74,88,102` (`about`, `reviews`)
- Modify: `src/apps/catalog/views.py:13,28` (`home`)
- Test: `src/tests/test_pages.py` (рядом с `test_reviews_page_photo_strip`)
- Modify: `docs/decisions.md` (решение 42)

**Interfaces:**
- Consumes: `daily_pick` из Task 1.
- Produces: `GalleryPhoto.STRIP_SIZE = 6`, `GalleryPhoto.strip(key: str, size: int = STRIP_SIZE) -> list[GalleryPhoto]`.

- [ ] **Step 1: Написать падающие тесты** — в `src/tests/test_pages.py` после `test_reviews_page_photo_strip` (нужны импорты `from datetime import date, timedelta` — `date` уже импортирован, `timedelta` добавить):

```python
def _strip_gallery(make_image, count):
    """count фото с подписями «Фото 0…»: по alt видно, какие попали в полосу."""
    first = GalleryPhoto.objects.create(image=make_image(), caption="Фото 0")
    GalleryPhoto.objects.bulk_create(
        [GalleryPhoto(image=first.image.name, caption=f"Фото {i}", order=i) for i in range(1, count)]
    )


def _strip_alts(html):
    strip = html.split("Как это выглядит")[1].split("</section>")[0]
    return re.findall(r'alt="(Фото \d+)"', strip)


@pytest.mark.parametrize("url", ["/", "/about/", "/reviews/"])
def test_photo_strip_rotates_daily(client, make_image, monkeypatch, url):
    _strip_gallery(make_image, 15)
    seen = set()
    for shift in range(10):
        monkeypatch.setattr("django.utils.timezone.localdate", lambda shift=shift: date(2026, 10, 1) + timedelta(days=shift))
        alts = _strip_alts(client.get(url).content.decode())
        assert len(alts) == GalleryPhoto.STRIP_SIZE
        assert alts == sorted(alts, key=lambda alt: int(alt.split()[1]))  # порядок — как в галерее
        seen.update(alts)
    assert len(seen) > GalleryPhoto.STRIP_SIZE  # не всегда первые шесть


def test_photo_strip_differs_between_pages(client, make_image, monkeypatch):
    _strip_gallery(make_image, 15)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 10, 11))
    home, about = (_strip_alts(client.get(url).content.decode()) for url in ("/", "/about/"))
    assert home != about


def test_photo_strip_stable_within_day_keeps_304(client, make_image):
    _strip_gallery(make_image, 15)
    first = client.get("/")
    assert first.has_header("ETag")
    assert client.get("/", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304
```

- [ ] **Step 2: Запустить — должны упасть**

Run: `cd src && uv run pytest tests/test_pages.py -k photo_strip -v`
Expected: FAIL — `AttributeError: type object 'GalleryPhoto' has no attribute 'STRIP_SIZE'` (и `assert len(seen) > 6` у `test_photo_strip_rotates_daily`). `test_photo_strip_stable_within_day_keeps_304` и `test_reviews_page_photo_strip` проходят уже сейчас — это страховка.

- [ ] **Step 3: Модель** — в `src/apps/content/models.py` импорт `from apps.core.rotation import daily_pick`, в `GalleryPhoto`:

```python
class GalleryPhoto(OrderedModel):
    STRIP_SIZE = 6  # фото в полосе «Как это выглядит» (главная, «О нас», отзывы)

    image = photo_field("Фото", "gallery", blank=False)
    ...

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"

    @classmethod
    def strip(cls, key: str, size: int = STRIP_SIZE) -> list["GalleryPhoto"]:
        """Фото для полосы «Как это выглядит»: на каждой странице (key) свои, меняются раз в сутки."""
        ids = daily_pick(list(cls.objects.values_list("pk", flat=True)), size, key)
        photos = cls.objects.in_bulk(ids)
        return [photos[pk] for pk in ids]
```

- [ ] **Step 4: Вьюхи**
  - `src/apps/catalog/views.py`: удалить `HOME_PHOTOS = 6`; в `home` — `"photos": GalleryPhoto.strip("home"),`.
  - `src/apps/content/views.py`: удалить `GALLERY_STRIP_SIZE = 6`; в `about` — `"photos": GalleryPhoto.strip("about"),`; в `reviews` — `"photos": GalleryPhoto.strip("reviews"),`.

- [ ] **Step 5: Запустить тесты**

Run: `cd src && uv run pytest tests/test_pages.py tests/test_pages_home.py tests/test_query_counts.py -v`
Expected: всё зелёное.

- [ ] **Step 6: Решение в журнал** — в `docs/decisions.md` строка в таблицу после 41:

```markdown
| 42 | **Ротация подборок витрины — раз в сутки** (`apps/core/rotation.py`, `daily_pick`): полоса «Как это выглядит» (свой набор на главной, «О нас» и отзывах) и «Ещё в категории» (свой у каждой услуги); сид — дата + ключ страницы, порядок — как в админке | Не всегда первые фото и услуги, ссылки получают все услуги категории; случайный набор на каждый запрос менял бы HTML и убил ETag/304, перемешивание в браузере — лишний вес и «перескок» фото |
```

- [ ] **Step 7: Commit**

```bash
git add src/apps/content/models.py src/apps/content/views.py src/apps/catalog/views.py src/tests/test_pages.py docs/decisions.md
git commit -m "Полоса «Как это выглядит»: фото меняются раз в сутки, на каждой странице свои"
```

---

### Task 3: Ротация «Ещё в категории» на странице услуги

**Files:**
- Modify: `src/apps/catalog/views.py:83-96` (`related_services`)
- Test: `src/tests/test_pages.py` (после `test_service_related_skips_same_name_variants`)

**Interfaces:**
- Consumes: `daily_pick` из Task 1.
- Produces: `related_services(category, service, limit: int = RELATED_SERVICES) -> list[Service]` — сигнатура прежняя.

- [ ] **Step 1: Написать падающие тесты**

```python
def _category_with_services(count):
    category = Category.objects.create(name="Высота", is_published=True)
    services = [Service.objects.create(name=f"Услуга {i}", has_page=True) for i in range(count)]
    for order, service in enumerate(services):
        CategoryService.objects.create(category=category, service=service, order=order)
    return services


def _related_urls(html):
    return re.findall(r'<a href="(/services/[^"]+)" class="card', html.split("Ещё в категории")[1])


def test_related_services_rotate_daily(client, monkeypatch):
    services = _category_with_services(8)
    current = services[0]
    seen = set()
    for shift in range(20):
        monkeypatch.setattr("django.utils.timezone.localdate", lambda shift=shift: date(2026, 10, 1) + timedelta(days=shift))
        urls = _related_urls(client.get(current.get_absolute_url()).content.decode())
        assert len(urls) == 3
        assert current.get_absolute_url() not in urls
        positions = [next(i for i, s in enumerate(services) if s.get_absolute_url() == url) for url in urls]
        assert positions == sorted(positions)  # порядок — как в категории
        seen.update(urls)
    assert seen == {s.get_absolute_url() for s in services[1:]}  # ссылки получают все, не только первые три


def test_related_services_differ_between_services(client, monkeypatch):
    services = _category_with_services(8)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 10, 11))
    others = [set(_related_urls(client.get(s.get_absolute_url()).content.decode())) - {s.get_absolute_url()} for s in services[:4]]
    assert len({frozenset(o) for o in others}) > 1


def test_related_services_stable_within_day(client):
    services = _category_with_services(8)
    first = client.get(services[0].get_absolute_url())
    assert client.get(services[0].get_absolute_url(), HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304
```

Перед запуском проверить регулярку `_related_urls` на реальном HTML карточки (`catalog/partials/service_card.html`: `<a href="{{ service.get_absolute_url }}" class="card card-link …">`) и префикс URL услуги (`Service.get_absolute_url`); при расхождении — поправить регулярку, не шаблон.

- [ ] **Step 2: Запустить — должны упасть**

Run: `cd src && uv run pytest tests/test_pages.py -k related_services -v`
Expected: FAIL у `test_related_services_rotate_daily` (видны только услуги 1–3) и у `test_related_services_differ_between_services`.

- [ ] **Step 3: Реализация** — в `src/apps/catalog/views.py` импорт `from apps.core.rotation import daily_pick` и:

```python
def related_services(category, service, limit: int = RELATED_SERVICES) -> list:
    """Другие услуги категории со своей страницей: у каждой услуги свой набор, меняется раз в сутки — иначе ссылки
    получали бы только первые услуги категории. Варианты с тем же названием (в т. ч. текущей услуги) — один раз.
    """
    seen = {service.name.casefold()}
    candidates = []
    for item in category.published_services():
        name = item.name.casefold()
        if item.has_page and name not in seen:
            seen.add(name)
            candidates.append(item)
    return daily_pick(candidates, limit, key=f"service:{service.pk}")
```

- [ ] **Step 4: Запустить тесты**

Run: `cd src && uv run pytest tests/test_pages.py -k "related or service" -v`
Expected: всё зелёное, включая старые `test_service_page_booking_card_and_related` и `test_service_related_skips_same_name_variants`.

- [ ] **Step 5: Commit**

```bash
git add src/apps/catalog/views.py src/tests/test_pages.py
git commit -m "«Ещё в категории»: у каждой услуги свои соседи, меняются раз в сутки"
```

---

### Task 4: Плавное раскрытие отзыва

**Files:**
- Create: `src/static/js/review_card.js`
- Modify: `src/templates/content/partials/review_card.html:3-8`
- Modify: `src/templates/base.html:30` (подключение скрипта до Alpine)
- Modify: `src/tailwind/source.css:151-156` (+ `@property` на верхнем уровне)
- Create: `src/tests/e2e/conftest.py` (перенос фикстур из `test_mobile_layout.py`)
- Modify: `src/tests/e2e/test_mobile_layout.py` (удалить перенесённые фикстуры)
- Create: `src/tests/e2e/test_review_expand.py`
- Test: `src/tests/test_pages.py` (разметка карточки)
- Modify: `CLAUDE.md` (пункт про Alpine-компоненты)

**Interfaces:**
- Produces: Alpine-компонент `reviewCard` (состояние `open`, `long`; метод `toggle()`), CSS-свойство `--review-fade`.

- [ ] **Step 1: Падающий тест разметки** — в `src/tests/test_pages.py` рядом с тестами отзывов:

```python
def test_review_card_uses_animated_component(client):
    Review.objects.create(text="<p>Отзыв</p>")
    html = client.get("/reviews/").content.decode()
    assert 'x-data="reviewCard"' in html and '@click="toggle()"' in html and ':aria-expanded="open"' in html
    head = html.split("</head>")[0]
    assert head.index("js/review_card") < head.index("vendor/alpine")  # компонент регистрируется до старта Alpine
```

Run: `cd src && uv run pytest tests/test_pages.py::test_review_card_uses_animated_component -v` → FAIL.

- [ ] **Step 2: Компонент** — `src/static/js/review_card.js`:

```js
// Карточка отзыва (Alpine-компонент reviewCard): длинный текст свёрнут, «Читать полностью» плавно раскрывает его,
// «Свернуть» — плавно сворачивает. Анимируется max-height (он же ограничивает свёрнутый текст), затухание низа —
// CSS-переход --review-fade. Подключается до Alpine: регистрация — в событии alpine:init.
document.addEventListener("alpine:init", () => {
  const DURATION = 300; // мс, как у раскрытия <details data-smooth> в site.js
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  window.Alpine.data("reviewCard", () => ({
    open: false,
    long: true,
    animation: null,
    init() {
      this.$nextTick(() => (this.long = this.$refs.text.scrollHeight > this.$refs.text.clientHeight + 4));
    },
    async toggle() {
      const text = this.$refs.text;
      // Посреди анимации это текущая (анимированная) высота — повторный клик разворачивает без скачка.
      const from = text.getBoundingClientRect().height;
      this.animation?.cancel();
      this.open = !this.open;
      await this.$nextTick(); // класс is-clamped снят или возвращён — можно мерить конечную высоту
      text.style.overflow = "";
      if (reducedMotion.matches) return;
      const to = this.open ? text.scrollHeight : text.getBoundingClientRect().height;
      text.style.overflow = "hidden"; // пока высота меняется, хвост текста не вылезает из карточки
      const animation = text.animate({ maxHeight: [`${from}px`, `${to}px`] }, { duration: DURATION, easing: "ease-out" });
      this.animation = animation;
      // cancel приходит событием позже — проверяем, что это всё ещё наша анимация, иначе снимем обрезку у следующей.
      animation.onfinish = () => {
        if (this.animation !== animation) return;
        this.animation = null;
        text.style.overflow = "";
      };
    },
  }));
});
```

- [ ] **Step 3: Шаблон** — `src/templates/content/partials/review_card.html`, строки 3–8:

```html
<article class="flex h-full flex-col rounded-3xl bg-(--rv-bg) p-5 sm:p-6" x-data="reviewCard">
  <span class="icon icon-fill h-8 w-8 text-(--rv-quote)" aria-hidden="true">{% include "icons/quote.svg" %}</span>
  <div x-ref="text" class="review-text is-clamped rich-text mt-3" :class="{ 'is-clamped': long && !open }">{{ review.text|safe }}</div>
  <button type="button" x-show="long" @click="toggle()" :aria-expanded="open" class="-mb-2 cursor-pointer self-start py-2 text-sm font-semibold text-brand-700 underline-offset-2 hover:text-brand-600 hover:underline"
          x-text="open ? 'Свернуть' : 'Читать полностью'">Читать полностью</button>
```

- [ ] **Step 4: Подключение** — `src/templates/base.html`, между `hover_menu.js` и `alpine.min.js`:

```html
  <script defer src="{% static 'js/hover_menu.js' %}"></script>
  <script defer src="{% static 'js/review_card.js' %}"></script>
  <script defer src="{% static 'vendor/alpine.min.js' %}"></script>
```

(Подключаем в `base.html`, а не только на главной и в отзывах: Alpine стартует сразу после выполнения своего скрипта, поэтому компонент обязан быть в `<head>` раньше него; файл < 1 КБ и кешируется навсегда через манифест.)

- [ ] **Step 5: CSS** — `src/tailwind/source.css`. На верхнем уровне (не внутри `@layer`, например перед `@utility review-tone-warm`):

```css
/* Граница затухания низа отзыва (.review-text): зарегистрирована, чтобы переход анимировал её вместе с высотой. */
@property --review-fade {
  syntax: "<percentage>";
  inherits: false;
  initial-value: 100%;
}
```

В `@layer components` заменить блок `.review-text.is-clamped`:

```css
  /* Длинный отзыв свёрнут до ~8 строк с плавным затуханием; «Читать полностью» снимает класс, высоту анимирует
     компонент reviewCard (static/js/review_card.js), затухание — переход --review-fade (100% — затухания нет). */
  .review-text {
    mask-image: linear-gradient(to bottom, #000 var(--review-fade), transparent);
    transition: --review-fade 300ms ease-out;
  }
  .review-text.is-clamped {
    --review-fade: 65%;
    max-height: 13rem;
    overflow: hidden;
  }
  @media (prefers-reduced-motion: reduce) {
    .review-text { transition: none; }
  }
```

Run: `cd src && uv run manage.py tailwind build && uv run pytest tests/test_pages.py::test_review_card_uses_animated_component tests/test_static.py -v` → PASS.

- [ ] **Step 6: Общие e2e-фикстуры** — перенести `allow_orm_next_to_playwright` и `built_css` из `src/tests/e2e/test_mobile_layout.py` в новый `src/tests/e2e/conftest.py` без изменений (вместе с их импортами: `Path`, `pytest`, `settings`), из `test_mobile_layout.py` удалить. Проверить из корня: `make e2e ARGS="-k overflow"` — зелёное.

- [ ] **Step 7: e2e-тесты** — `src/tests/e2e/test_review_expand.py`:

```python
"""Плавное раскрытие длинного отзыва в настоящем браузере (make e2e)."""

import pytest

pytest.importorskip("playwright")

from apps.content.models import Review

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

LONG = "<p>" + "Очень понравилось, обязательно приедем ещё. " * 60 + "</p>"
ANIMATING = "[...document.querySelectorAll('.review-text')].some((el) => el.getAnimations().length)"


def _open(browser, live_server, **context):
    page = browser.new_context(viewport={"width": 1280, "height": 900}, **context).new_page()
    page.goto(live_server.url + "/reviews/")
    page.wait_for_load_state("networkidle")
    return page


def _height(page):
    return page.locator(".review-text").bounding_box()["height"]


def test_long_review_expands_and_collapses_smoothly(live_server, browser):
    Review.objects.create(text=LONG)
    page = _open(browser, live_server)
    collapsed = _height(page)
    page.get_by_role("button", name="Читать полностью").click()
    assert page.evaluate(ANIMATING)  # высота меняется анимацией, а не скачком
    page.wait_for_function(f"!({ANIMATING})")
    assert _height(page) > collapsed * 2
    assert page.locator(".review-text").evaluate("(el) => getComputedStyle(el).overflow") == "visible"
    page.get_by_role("button", name="Свернуть").click()
    assert page.evaluate(ANIMATING)
    page.wait_for_function(f"!({ANIMATING})")
    assert _height(page) == pytest.approx(collapsed, abs=1)


def test_review_double_click_mid_animation(live_server, browser):
    Review.objects.create(text=LONG)
    page = _open(browser, live_server)
    collapsed = _height(page)
    button = page.locator(".review-text + button")
    button.click()
    page.wait_for_timeout(100)
    button.click()  # передумали посреди раскрытия
    page.wait_for_function(f"!({ANIMATING})")
    assert _height(page) == pytest.approx(collapsed, abs=1)
    assert button.inner_text() == "Читать полностью"


def test_short_review_not_clamped(live_server, browser):
    Review.objects.create(text="<p>Коротко и ясно.</p>")
    page = _open(browser, live_server)
    assert not page.locator(".review-text + button").is_visible()
    fade = page.locator(".review-text").evaluate("(el) => getComputedStyle(el).getPropertyValue('--review-fade')")
    assert fade.strip() == "100%"  # маска ничего не прячет


def test_reduced_motion_expands_instantly(live_server, browser):
    Review.objects.create(text=LONG)
    page = _open(browser, live_server, reduced_motion="reduce")
    page.get_by_role("button", name="Читать полностью").click()
    assert not page.evaluate(ANIMATING)
    assert "is-clamped" not in page.locator(".review-text").get_attribute("class")
```

Run: `make e2e ARGS="tests/e2e/test_review_expand.py"` (из корня; один раз — `cd src && uv sync --group e2e && uv run --group e2e playwright install chromium`)
Expected: 4 passed. Если `test_long_review_expands_and_collapses_smoothly` ловит конец анимации раньше `evaluate` — не увеличивать `DURATION`, а проверить, что `toggle()` вызывается (кнопка с `@click="toggle()"`).

- [ ] **Step 8: Ручная проверка** — `make run`, открыть `/` (карусель отзывов) и `/reviews/` (кирпичная раскладка): раскрытие/сворачивание плавное, соседние карточки карусели растягиваются вместе с раскрытой без рывка, в раскладке отзывы ниже плавно сдвигаются; в DevTools → Rendering → «prefers-reduced-motion: reduce» — мгновенно.

- [ ] **Step 9: CLAUDE.md** — в абзац про `hoverMenu` («Выпадающие меню шапки…») дописать предложение:

```markdown
Карточка отзыва — Alpine-компонент `reviewCard` (`static/js/review_card.js`, тоже до Alpine): «Читать полностью» плавно анимирует `max-height`, затухание низа — переход зарегистрированного свойства `--review-fade` (`tailwind/source.css`).
```

- [ ] **Step 10: Полный прогон и commit**

Run: `cd src && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: всё зелёное.

```bash
git add src/static/js/review_card.js src/templates/content/partials/review_card.html src/templates/base.html src/tailwind/source.css src/tests/e2e/ src/tests/test_pages.py CLAUDE.md
git commit -m "Отзывы: плавное раскрытие и сворачивание «Читать полностью»"
```
