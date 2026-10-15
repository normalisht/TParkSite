from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.catalog.admin import ServiceAdmin
from apps.catalog.models import Category, CategoryService, Service
from apps.content.models import Event
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db


@pytest.fixture
def draft_category():
    return Category.objects.create(name="Черновая", is_published=False)


def test_visitor_gets_404(client, draft_category):
    assert client.get(draft_category.get_absolute_url()).status_code == 404


def test_staff_sees_draft_with_banner(admin_client, draft_category):
    response = admin_client.get(draft_category.get_absolute_url())
    assert response.status_code == 200
    page = response.content.decode()
    assert "Черновик" in page and '<meta name="robots" content="noindex">' in page
    assert reverse("admin:catalog_category_change", args=[draft_category.pk]) in page
    assert "no-cache" in response["Cache-Control"]


def test_staff_without_view_permission_gets_404(client, django_user_model, draft_category):
    user = django_user_model.objects.create_user("editor", password="x", is_staff=True)
    client.force_login(user)
    assert client.get(draft_category.get_absolute_url()).status_code == 404
    user.user_permissions.add(Permission.objects.get(codename="view_category"))
    assert client.get(draft_category.get_absolute_url()).status_code == 200


def test_trashed_not_previewed(admin_client, draft_category):
    draft_category.move_to_trash()
    assert admin_client.get(draft_category.get_absolute_url()).status_code == 404


def test_published_page_same_for_visitor_and_staff(client, admin_client):
    category = Category.objects.create(name="Открытая", is_published=True)
    anon = client.get(category.get_absolute_url())
    staff = admin_client.get(category.get_absolute_url())
    assert "Черновик" not in staff.content.decode()
    assert anon["ETag"] == staff["ETag"]


def test_draft_service_event_info_previewed(admin_client):
    service = Service.objects.create(name="Услуга", has_page=True, is_published=False)
    event = Event.objects.create(title="Событие", date=timezone.localdate() + timedelta(days=3), is_published=False)
    info = InfoPage.objects.create(title="Инфо", body="<p>Текст</p>", is_published=False)
    for obj in (service, event, info):
        response = admin_client.get(obj.get_absolute_url())
        assert response.status_code == 200, obj
        assert "Черновик" in response.content.decode()


def test_service_without_page_view_on_site(draft_category):
    service = Service.objects.create(name="Без страницы", has_page=False)
    model_admin = ServiceAdmin(Service, admin.site)
    assert model_admin.view_on_site(service) is None
    CategoryService.objects.create(category=draft_category, service=service, order=1)
    assert model_admin.view_on_site(service) == draft_category.get_absolute_url()
