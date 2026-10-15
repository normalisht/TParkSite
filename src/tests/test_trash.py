from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import TrashAdminMixin
from apps.core.models import InfoPage, SiteSettings

pytestmark = pytest.mark.django_db


@pytest.fixture
def service(make_image):
    category = Category.objects.create(name="Аквазона", is_published=True)
    service = Service.objects.create(name="Батут", has_page=True)
    CategoryService.objects.create(category=category, service=service, order=1)
    ServicePhoto.objects.create(service=service, image=make_image())
    return service


def test_delete_moves_to_trash(admin_client, client, service):
    url = reverse("admin:catalog_service_delete", args=[service.pk])
    assert "корзин" in admin_client.get(url).content.decode()
    response = admin_client.post(url, {"post": "yes"})
    assert response.status_code == 302
    service.refresh_from_db()
    assert service.in_trash and not service.is_published
    photo = service.photos.get()
    assert photo.image.storage.exists(photo.image.name)  # фото и файл на месте
    assert service.category_links.exists()
    listed = admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list
    assert service not in listed
    assert admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).status_code == 302
    assert client.get(service.get_absolute_url()).status_code == 404


def test_restore_returns_draft(admin_client, service):
    service.move_to_trash()
    response = admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "restore": "1"})
    assert response.status_code == 302
    service.refresh_from_db()
    assert not service.in_trash and not service.is_published
    assert service in admin_client.get(reverse("admin:catalog_service_changelist")).context["cl"].result_list


def test_purge_deletes_forever(admin_client, service, django_capture_on_commit_callbacks):
    service.move_to_trash()
    photo = service.photos.get()
    storage, name = photo.image.storage, photo.image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(reverse("admin:catalog_service_trash"), {"pk": service.pk, "purge": "1"})
    assert not Service.objects.filter(pk=service.pk).exists()
    assert not storage.exists(name)


def test_expired_items_purged_on_open(admin_client, service):
    service.move_to_trash()
    Service.objects.filter(pk=service.pk).update(deleted_at=timezone.now() - timedelta(days=31))
    assert admin_client.get(reverse("admin:catalog_service_trash")).status_code == 200
    assert not Service.objects.filter(pk=service.pk).exists()


def test_bulk_action_moves_to_trash(admin_client, service):
    url = reverse("admin:catalog_service_changelist")
    actions = dict(admin_client.get(url).context["action_form"].fields["action"].choices)
    assert "delete_selected" not in actions and "move_selected_to_trash" in actions
    admin_client.post(url, {"action": "move_selected_to_trash", "_selected_action": [service.pk]})
    service.refresh_from_db()
    assert service.in_trash


def test_trashed_hidden_from_autocomplete_and_inlines(admin_client, service):
    category = Category.objects.get()
    category.move_to_trash()
    response = admin_client.get(
        reverse("admin:autocomplete"),
        {"term": "Аква", "app_label": "catalog", "model_name": "categoryservice", "field_name": "category"},
    )
    assert response.json()["results"] == []
    page = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    assert "Аквазона" not in page  # не «Парк»: он есть в заголовке «Т-Парк»


def test_trashed_privacy_page_disappears_from_site(client):
    page = InfoPage.objects.create(title="Политика", body="<p>Текст</p>", is_published=True)
    site = SiteSettings.load()
    site.privacy_page = page
    site.save()
    page.move_to_trash()
    response = client.get("/")
    assert response.status_code == 200
    assert page.get_absolute_url() not in response.content.decode()


def test_every_trash_admin_has_trash_button():
    for model, model_admin in admin.site._registry.items():
        if isinstance(model_admin, TrashAdminMixin):
            assert "trash" in model_admin.actions_list, model
