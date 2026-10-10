"""Вёрстка в настоящем браузере: на узких экранах ничего не вылезает за правый край.

Запуск: `make e2e` (один раз: `uv sync --group e2e` и `uv run --group e2e playwright install chromium`).
В обычном `pytest` не участвует (маркер e2e исключён в addopts).
"""

import os
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

pytest.importorskip("playwright")

from apps.catalog.models import Category, CategoryGroup, CategoryService, Service
from apps.content.models import Event, Review
from apps.core.models import Phone, SiteSettings

# Playwright держит в потоке теста event loop — без этого ORM в фикстурах падает с SynchronousOnlyOperation.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

WIDTHS = [320, 375]

# Элементы, правый край которых за экраном, кроме лежащих внутри прокручиваемых/обрезанных контейнеров.
# Ищем по координатам, а не по scrollWidth: overflow-x: clip на body прячет прокрутку, но не сам вылезший элемент.
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
    """Худший случай для узкого экрана: длинные заголовки, адрес, ссылка в отзыве, цена с единицей."""
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
    report = "\n".join(f"{url}: {item}" for url, items in problems.items() for item in items)
    assert not problems, f"За правым краем экрана {width} px:\n{report}"
