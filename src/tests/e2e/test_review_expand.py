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
