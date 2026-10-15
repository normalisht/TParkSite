"""Рамка админки в браузере: меню профиля и кнопка «Открыть сайт».

Запуск: `make e2e`.
"""

import pytest

pytest.importorskip("playwright")

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin_page(page, live_server, client, django_user_model):
    user = django_user_model.objects.create_superuser("admin", "admin@example.com", "pass")
    client.force_login(user)
    page.context.add_cookies(
        [{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}]
    )
    return page


# Подписи сегментов, вылезающие за свою кнопку (scrollWidth больше видимой ширины — обрезаны).
CLIPPED_LABELS = """
() => [...document.querySelectorAll('[role=group] button span:last-child')]
  .filter(s => getComputedStyle(s).display !== 'none' && s.scrollWidth > s.clientWidth + 1)
  .map(s => s.textContent.trim())
"""


# 220 px — самая узкая боковая панель (её ширину можно тянуть мышью), там подписи прячутся.
@pytest.mark.parametrize(("width", "sidebar"), [(375, None), (1440, None), (1440, 220)])
def test_theme_switch_fits_user_menu(admin_page, live_server, width, sidebar):
    page = admin_page
    page.set_viewport_size({"width": width, "height": 800})
    page.goto(f"{live_server.url}/admin/")
    if sidebar:
        page.evaluate(f"localStorage.setItem('sidebarWidth', {sidebar})")
        page.reload()
    profile = page.get_by_text("admin@example.com")
    if not profile.is_visible():
        page.get_by_text("dock_to_right").click()
    profile.click()
    group = page.get_by_role("group", name="Тема")
    group.wait_for()
    assert page.evaluate(CLIPPED_LABELS) == []
    for label in ("Светлая", "Тёмная", "Системная"):
        assert group.get_by_text(label).is_visible() == (sidebar is None)

    group.get_by_title("Тёмная тема").click()
    assert "dark" in (page.locator("html").get_attribute("class") or "")


@pytest.mark.parametrize("width", [375, 1280])
def test_header_open_site_button(admin_page, live_server, width):
    page = admin_page
    page.set_viewport_size({"width": width, "height": 800})
    page.goto(f"{live_server.url}/admin/catalog/category/")
    button = page.get_by_title("Открыть сайт в новой вкладке")
    assert button.is_visible()
    assert button.get_attribute("href") == "/"
    assert button.get_by_text("Открыть сайт").is_visible() == (width >= 768)


# Вкладки полей (fieldsets_tabs Unfold), правый край которых за пределами экрана.
CLIPPED_TABS = """
() => [...document.querySelectorAll('[x-data*="activeFieldsetTab"] > div > nav > a')]
  .filter(a => a.getBoundingClientRect().right > window.innerWidth + 1)
  .map(a => a.textContent.trim())
"""


def test_settings_tabs_fit_phone(admin_page, live_server):
    page = admin_page
    page.set_viewport_size({"width": 390, "height": 800})
    page.goto(f"{live_server.url}/admin/core/sitesettings/")
    page.locator('[x-data*="activeFieldsetTab"]').first.wait_for()
    assert page.evaluate(CLIPPED_TABS) == []


def test_seo_tab_switches_and_survives_save(admin_page, live_server):
    from apps.catalog.models import Service

    service = Service.objects.create(name="Зиплайн")
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/{service.pk}/change/")
    nav = page.locator("#tabs-items")
    assert nav.locator("a").all_inner_texts() == ["Основное", "Фото", "Категории", "SEO"]
    assert page.locator("#id_name").is_visible()
    assert not page.locator("#id_seo_title").is_visible()

    nav.get_by_text("SEO", exact=True).click()
    page.locator("#id_seo_title").wait_for(state="visible")
    page.locator("#id_name").wait_for(state="hidden")

    page.fill("#id_seo_title", "Прыжок над лесом")
    page.get_by_role("button", name="Сохранить и продолжить редактирование").click()
    page.wait_for_url("**/change/#seo")  # форма отправляется на адрес с #<вкладка>
    page.locator("#id_seo_title").wait_for(state="visible")
    assert page.input_value("#id_seo_title") == "Прыжок над лесом"
    page.locator("#id_name").wait_for(state="hidden")
