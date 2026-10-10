"""Вёрстка в настоящем браузере: на узких экранах ничего не вылезает за правый край.

Запуск: `make e2e` (один раз: `uv sync --group e2e` и `uv run --group e2e playwright install chromium`).
В обычном `pytest` не участвует (маркер e2e исключён в addopts).
"""

from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

pytest.importorskip("playwright")

from apps.catalog.models import Category, CategoryGroup, CategoryService, Service
from apps.content.models import Event, GalleryPhoto, Review
from apps.core.models import Phone, SiteSettings

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


# Текст, срезанный краем блока: длинное слово не влезает в ширину, а предок с overflow: hidden прячет хвост.
# FIND_OVERFLOW такое не видит — обрезанный контейнер для него «норма».
FIND_CLIPPED_TEXT = """
() => {
  const found = [];
  for (const el of document.body.querySelectorAll("h1, h2, h3, p, a, li, span")) {
    if (el.clientWidth <= 1 || getComputedStyle(el).display === "inline") continue;
    if (getComputedStyle(el).overflowX !== "visible") continue;
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (hasText && el.scrollWidth > el.clientWidth + 1) found.push(`${el.tagName.toLowerCase()} «${el.textContent.trim().slice(0, 40)}» +${el.scrollWidth - el.clientWidth}px`);
  }
  return found;
}
"""


@pytest.fixture(scope="session", autouse=True)
def allow_orm_next_to_playwright():
    """Playwright держит в потоке теста event loop — без этого ORM (в т. ч. в сессионных фикстурах БД) падает
    с SynchronousOnlyOperation. Фикстура создаётся, только когда e2e-тесты выбраны, и снимает переменную после них:
    на уровне модуля она отключила бы проверку для всего прогона pytest.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        yield


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
    # Длинное слово в заголовке страницы и в карточке «Ещё в категории».
    long = Service.objects.create(name="Тренинг командообразования «Веревочный курс»", price="3500", has_page=True)
    for order, item in enumerate([service, other, long]):
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
    return {"category": category, "service": service, "long_service": long, "event": events[0]}


@pytest.mark.parametrize("width", WIDTHS)
def test_no_horizontal_overflow(live_server, browser, content, width):
    pages = [
        "/",
        "/contacts/",
        "/reviews/",
        "/events/",
        content["category"].get_absolute_url(),
        content["service"].get_absolute_url(),
        content["long_service"].get_absolute_url(),
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
        if found := page.evaluate(FIND_OVERFLOW) + page.evaluate(FIND_CLIPPED_TEXT):
            problems[url] = found
    context.close()
    report = "\n".join(f"{url}: {item}" for url, items in problems.items() for item in items)
    assert not problems, f"За правым краем экрана {width} px:\n{report}"


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


def test_services_menu_survives_click_on_empty_space(live_server, browser, content):
    """Клик по подписи группы внутри панели (focusout без relatedTarget) не закрывает меню; Tab за пределы и клик снаружи — закрывают."""
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    menu = page.locator("#services-menu")
    trigger = page.get_by_role("button", name="Услуги")

    def settle():
        # Alpine обновляет x-show в микрозадаче: ждём пару кадров, иначе проверка «ещё виден» ничего не докажет.
        page.evaluate("() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))")

    trigger.click()
    menu.wait_for(state="visible")

    menu.get_by_role("link").first.focus()
    menu.get_by_text("Групповые приключения").click()
    settle()
    assert menu.is_visible()

    menu.get_by_role("link", name="Все услуги").focus()
    page.keyboard.press("Tab")
    menu.wait_for(state="hidden")

    trigger.click()
    menu.wait_for(state="visible")
    page.mouse.click(5, 400)
    menu.wait_for(state="hidden")
    context.close()


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
