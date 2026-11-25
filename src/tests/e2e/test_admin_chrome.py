"""Рамка админки в браузере: меню профиля и кнопка «Открыть сайт».

Запуск: `make e2e`.
"""

import pytest

pytest.importorskip("playwright")

from apps.core.models import ContactChannel

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


@pytest.mark.parametrize("width", [390, 1440])
def test_settings_format_column_help_opens(admin_page, live_server, width):
    page = admin_page
    page.set_viewport_size({"width": width, "height": 850})
    page.goto(f"{live_server.url}/admin/core/sitesettings/1/change/#park_formats")
    if width < 1024:
        page.get_by_text("Подсказки по полям", exact=True).click()
    else:
        button = page.get_by_role("button", name="Подсказка — Группа категорий")
        button.hover()
        tooltip = page.locator("#park-formats-help-category_group")
        tooltip.wait_for(state="visible", timeout=500)
        button.click()
        page.mouse.move(1, 1)
        assert button.get_attribute("aria-expanded") == "true"
    page.get_by_text("Плашка ведёт к этой группе на главной", exact=False).locator("visible=true").wait_for()


def test_settings_format_column_help_wraps_beside_sidebar(admin_page, live_server):
    page = admin_page
    page.set_viewport_size({"width": 1440, "height": 850})
    page.add_init_script("localStorage.setItem('sidebarWidth', '360')")
    page.goto(f"{live_server.url}/admin/core/sitesettings/1/change/#park_formats")
    sidebar = page.locator("#nav-sidebar").bounding_box()
    assert sidebar and sidebar["width"] == 360

    for field, label in [("name", "Название"), ("category_group", "Группа категорий"), ("logo", "Логотип")]:
        page.get_by_role("button", name=f"Подсказка — {label}", exact=True).hover()
        tooltip = page.locator(f"#park-formats-help-{field}")
        tooltip.wait_for()
        layout = tooltip.evaluate(
            """el => {
                const range = document.createRange();
                range.selectNodeContents(el);
                const {left, right} = el.getBoundingClientRect();
                return {left, right, lines: range.getClientRects().length};
            }"""
        )
        assert layout["lines"] > 1 and sidebar["x"] + sidebar["width"] <= layout["left"] < layout["right"] <= 1440, (
            field,
            layout,
        )


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


def test_contact_channels_reorder_by_drag(admin_page, live_server):
    page = admin_page
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{live_server.url}/admin/core/sitesettings/1/change/#contact_channels")
    rows = page.locator("#contact_channels-data tbody.form-group")
    rows.first.wait_for()
    assert rows.count() == len(ContactChannel.Kind.values)
    first, second = (rows.nth(i).get_by_text("drag_indicator").bounding_box() for i in (0, 1))
    page.mouse.move(first["x"] + 10, first["y"] + 10)
    page.mouse.down()
    # Перетаскивание срабатывает только на промежуточных движениях мыши.
    page.mouse.move(first["x"] + 10, second["y"], steps=5)
    page.mouse.move(first["x"] + 10, second["y"] + 30, steps=5)
    page.mouse.up()
    with page.expect_navigation():
        page.locator('button[name="_continue"]').click()
    assert list(ContactChannel.objects.values_list("kind", flat=True))[:2] == ["telegram", "whatsapp"]
