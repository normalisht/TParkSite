"""Сезонное оформление в браузере: декор не перехватывает клики, уважает «уменьшить движение», не распирает экран."""

from datetime import date

import pytest

pytest.importorskip("playwright")

from apps.core.models import Season, SiteSettings
from tests.e2e.test_mobile_layout import FIND_OVERFLOW

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

ANIMATION = "(sel) => getComputedStyle(document.querySelector(sel), '::before').animationName"


@pytest.fixture
def new_year(monkeypatch):
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 12, 31))
    Season.ensure_for(SiteSettings.load())  # transaction=True очищает базу — записи из миграции пропадают
    Season.objects.filter(kind=Season.Kind.NEW_YEAR).update(
        banner_text="Новогодние корпоративы в Т-Парке — бронируйте даты заранее", banner_link="/events/"
    )


def test_decor_is_inert_and_animated(live_server, page, new_year):
    page.goto(live_server.url + "/")
    for sel in (".season-snow", ".season-garland"):
        assert page.eval_on_selector(sel, "el => getComputedStyle(el).pointerEvents") == "none"
    assert page.evaluate(ANIMATION, ".season-snow") == "season-snow"
    hero_bg = page.eval_on_selector(".page-hero", "el => getComputedStyle(el).backgroundImage")
    assert "linear-gradient" in hero_bg and "226, 238, 248" in hero_bg  # frost-100 #e2eef8
    page.click(".season-banner a")
    assert page.url.endswith("/events/")


def test_reduced_motion_stops_snow(live_server, browser, new_year):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(live_server.url + "/")
    assert page.evaluate(ANIMATION, ".season-snow") == "none"
    context.close()


@pytest.mark.parametrize("width", [320, 375])
def test_banner_fits_narrow_screen_and_menu_still_fits(live_server, browser, new_year, width):
    context = browser.new_context(viewport={"width": width, "height": 700}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(live_server.url + "/")
    assert page.evaluate(FIND_OVERFLOW) == []
    page.click("header button.md\\:hidden")
    # Панель меню (partials/header.html): absolute top-full, высота 100dvh минус шапка.
    panel = page.locator('header div.overflow-y-auto[x-show="open"]')
    panel.wait_for(state="visible")
    box = panel.bounding_box()
    assert box["y"] + box["height"] <= 700 + 1  # меню не уходит за низ экрана
    context.close()
