"""Корзина админки в браузере: кнопки плашки в просмотре записи из корзины.

Запуск: `make e2e`.
"""

import pytest

pytest.importorskip("playwright")

from apps.catalog.models import Service

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def admin_page(page, live_server, client, django_user_model):
    user = django_user_model.objects.create_superuser("admin", "admin@example.com", "pass")
    client.force_login(user)
    page.context.add_cookies(
        [{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}]
    )
    return page


@pytest.fixture
def trashed_service():
    service = Service.objects.create(name="Батут", is_published=True)
    service.move_to_trash()
    return service


def test_restore_from_read_only_view(admin_page, live_server, trashed_service):
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/trash/{trashed_service.pk}/")
    page.get_by_role("button", name="Восстановить").click()
    page.wait_for_url(f"**/admin/catalog/service/{trashed_service.pk}/change/")
    assert page.get_by_text("восстановлено черновиком — проверьте и опубликуйте").is_visible()
    trashed_service.refresh_from_db()
    assert not trashed_service.in_trash and not trashed_service.is_published


def test_purge_from_read_only_view(admin_page, live_server, trashed_service):
    page = admin_page
    page.goto(f"{live_server.url}/admin/catalog/service/trash/{trashed_service.pk}/")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Удалить навсегда").click()
    page.wait_for_url("**/admin/catalog/service/trash/")
    assert page.get_by_text("удалено навсегда").is_visible()
    assert not Service.objects.filter(pk=trashed_service.pk).exists()
