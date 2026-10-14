"""Сезонное оформление в браузере: декор не перехватывает клики, уважает «уменьшить движение», не распирает экран."""

from datetime import date

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

from apps.core.models import Announcement, InfoPage, Season, SiteSettings
from tests.e2e.test_admin_chrome import admin_page  # noqa: F401
from tests.e2e.test_mobile_layout import FIND_OVERFLOW

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

ANIMATION = "(sel) => getComputedStyle(document.querySelector(sel), '::before').animationName"


@pytest.fixture
def new_year(monkeypatch):
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 12, 31))
    Season.ensure_for(SiteSettings.load())  # transaction=True очищает базу — записи из миграции пропадают
    Announcement.objects.create(text="Новогодние корпоративы в Т-Парке — бронируйте даты заранее", link="/events/")


def test_decor_is_inert_and_animated(live_server, page, new_year):
    page.goto(live_server.url + "/")
    for sel in (".season-particles", ".season-garland"):
        assert page.eval_on_selector(sel, "el => getComputedStyle(el).pointerEvents") == "none"
    assert page.evaluate(ANIMATION, ".season-particles") == "season-fall"
    hero_bg = page.eval_on_selector(".page-hero", "el => getComputedStyle(el).backgroundImage")
    assert "linear-gradient" in hero_bg and "226, 238, 248" in hero_bg  # frost-100 #e2eef8
    page.click(".site-banner a")
    assert page.url.endswith("/events/")


def test_reduced_motion_stops_snow(live_server, browser, new_year):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.goto(live_server.url + "/")
    assert page.evaluate(ANIMATION, ".season-particles") == "none"
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


def test_garland_clears_breadcrumbs_on_phone(live_server, browser, new_year):
    """У инфо-страниц, услуг и мероприятий шапка с py-6: крошки начинаются в 24 px от верха — гирлянда выше них."""
    info = InfoPage.objects.create(title="Правила посещения парка", body="<p>Текст</p>", is_published=True)
    context = browser.new_context(viewport={"width": 390, "height": 800}, is_mobile=True, has_touch=True)
    page = context.new_page()
    page.goto(live_server.url + info.get_absolute_url())
    garland = page.locator(".season-garland").bounding_box()
    first = page.locator(".page-hero nav, .page-hero h1").first.bounding_box()
    assert garland["y"] + garland["height"] <= first["y"] + 1
    context.close()


def test_autumn_leaves_drift(live_server, page, monkeypatch):
    """Осень: тёплый фон шапки и листья — плитка с картинкой, сдвигается не только вниз, но и вбок."""
    monkeypatch.setattr("apps.core.seasons.today", lambda: date(2026, 10, 14))
    Season.ensure_for(SiteSettings.load())
    page.goto(live_server.url + "/")
    assert page.evaluate("() => document.documentElement.dataset.season") == "autumn"
    leaves = page.evaluate(
        "() => getComputedStyle(document.querySelector('.season-particles'), '::before').backgroundImage"
    )
    assert "data:image/svg+xml" in leaves
    assert page.evaluate(ANIMATION, ".season-particles") == "season-fall"
    drift = page.evaluate(
        "() => getComputedStyle(document.querySelector('.season-particles'), '::before').getPropertyValue('--drift')"
    )
    assert drift.strip() not in ("", "0", "0px")
    hero_bg = page.eval_on_selector(".page-hero", "el => getComputedStyle(el).backgroundImage")
    assert "251, 233, 210" in hero_bg  # maple-100 #fbe9d2


def test_admin_season_tabs_show_one_form(admin_page, live_server):  # noqa: F811
    Season.ensure_for(SiteSettings.load())
    page = admin_page
    page.goto(f"{live_server.url}/admin/core/sitesettings/1/change/")
    page.get_by_role("link", name="Сезонное оформление").first.click()
    forms = page.locator("#seasons-data > .form-group")
    # expect ждёт, пока Alpine переключит вкладку и табы; is_visible проверил бы мгновенно и иногда раньше времени.
    for i, visible in enumerate([True, False, False]):
        (expect(forms.nth(i)).to_be_visible if visible else expect(forms.nth(i)).to_be_hidden)()
    page.locator("[data-season-tab]", has_text="Зима").click()
    for i, visible in enumerate([False, True, False]):
        (expect(forms.nth(i)).to_be_visible if visible else expect(forms.nth(i)).to_be_hidden)()
    # На других вкладках формы настроек табов сезонов не видно.
    page.get_by_role("link", name="Основное").first.click()
    page.locator("[data-season-tabs]").wait_for(state="hidden")
