"""Плавное раскрытие длинного отзыва в настоящем браузере (make e2e)."""

import time
from itertools import pairwise

import pytest

pytest.importorskip("playwright")

from apps.content.models import Review

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

LONG = "<p>" + "Очень понравилось, обязательно приедем ещё. " * 60 + "</p>"
# Только анимация высоты: переход маски (--review-fade) — CSSTransition, он не доказывает, что высота меняется плавно.
ANIMATING = (
    "[...document.querySelectorAll('.review-text')]"
    ".some((el) => el.getAnimations().some((a) => !(a instanceof CSSTransition)))"
)
# Высота текста в каждом кадре — скачок к конечной высоте до старта анимации виден только так.
RECORD_HEIGHTS = """
() => {
  const el = document.querySelector('.review-text');
  window.heights = [];
  const tick = () => { window.heights.push(Math.round(el.getBoundingClientRect().height)); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
"""


def _open(browser, live_server, **context):
    page = browser.new_context(viewport={"width": 1280, "height": 900}, **context).new_page()
    page.goto(live_server.url + "/reviews/")
    page.wait_for_load_state("networkidle")
    return page


def _height(page):
    return page.locator(".review-text").bounding_box()["height"]


def _heights(page):
    """Высоты по кадрам; одинаковые подряд схлопнуты."""
    heights = page.evaluate("window.heights")
    return [h for i, h in enumerate(heights) if i == 0 or h != heights[i - 1]]


def _monotonic(values, rising):
    return all((b > a) if rising else (b < a) for a, b in pairwise(values))


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


def test_review_height_never_jumps(live_server, browser):
    """Настоящий клик мышью: ни одного кадра с конечной (или прежней) высотой до или посреди анимации."""
    Review.objects.create(text=LONG)
    page = _open(browser, live_server)
    button = page.locator(".review-text + button")
    for rising in (True, False):
        page.evaluate(RECORD_HEIGHTS)
        button.click(force=True)  # force: не ждать «стабильности» кнопки, она едет вместе с текстом
        page.wait_for_timeout(50)
        page.wait_for_function(f"!({ANIMATING})")
        heights = _heights(page)
        assert len(heights) > 3 and _monotonic(heights, rising), heights


def test_review_double_click_mid_animation(live_server, browser):
    Review.objects.create(text=LONG)
    page = _open(browser, live_server)
    collapsed = _height(page)
    button = page.locator(".review-text + button")
    page.evaluate(RECORD_HEIGHTS)
    button.click(force=True)
    page.wait_for_timeout(120)
    assert page.evaluate(ANIMATING)  # второй клик — действительно посреди раскрытия
    button.click(force=True)  # передумали
    page.wait_for_timeout(50)
    page.wait_for_function(f"!({ANIMATING})")
    heights = _heights(page)
    peak = heights.index(max(heights))
    assert _monotonic(heights[: peak + 1], True) and _monotonic(heights[peak:], False), heights  # без скачков
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


def _card_heights(page):
    return page.locator(".swiper-slide article").evaluate_all(
        "(els) => els.map((el) => el.getBoundingClientRect().height)"
    )


def test_home_carousel_neighbours_do_not_stretch(live_server, browser):
    """Карусель на главной: раскрытый отзыв не вытягивает соседей пустым местом — ни после, ни во время анимации."""
    Review.objects.bulk_create([Review(text=LONG) for _ in range(3)])
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    before = _card_heights(page)
    assert len(set(before)) == 1  # в покое — одной высоты
    button = page.locator(".swiper-slide").first.get_by_role("button")
    for label in ("Читать полностью", "Свернуть"):
        page.evaluate(
            """() => {
              const els = [...document.querySelectorAll('.swiper-slide article')].slice(1);
              window.neighbours = [];
              const tick = () => { window.neighbours.push(...els.map((el) => el.getBoundingClientRect().height)); requestAnimationFrame(tick); };
              requestAnimationFrame(tick);
            }"""
        )
        assert button.inner_text() == label
        button.click(force=True)
        page.wait_for_timeout(50)
        page.wait_for_function(f"!({ANIMATING})")
        page.wait_for_timeout(50)
        assert max(page.evaluate("window.neighbours")) == pytest.approx(before[1], abs=1), label
    assert _card_heights(page) == pytest.approx(before, abs=1)


def test_home_carousel_clamps_review_when_swiper_loads_late(live_server, browser):
    """Первый заход на главную: Swiper ещё грузится, когда Alpine меряет отзыв, — слайд пока во всю ширину и отзыв
    средней длины в нём помещается. После раскладки карусели (слайд — треть ширины) он должен свернуться."""
    Review.objects.bulk_create([Review(text="<p>" + "Очень понравилось, обязательно приедем ещё. " * 14 + "</p>")] * 3)
    context = browser.new_context(viewport={"width": 1280, "height": 900})

    def slow_swiper(route):
        time.sleep(0.5)  # первый заход: скрипт Swiper ещё не в кеше
        route.continue_()

    context.route("**/swiper-bundle.min.js", slow_swiper)
    page = context.new_page()
    page.goto(live_server.url + "/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(100)
    assert page.locator(".swiper-slide").first.get_by_role("button", name="Читать полностью").is_visible()
    assert "is-clamped" in page.locator(".review-text").first.get_attribute("class")
