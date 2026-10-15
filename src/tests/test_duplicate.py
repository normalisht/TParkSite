from datetime import date

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.catalog.models import Category, CategoryService, Service, ServicePhoto
from apps.content.models import Event

pytestmark = pytest.mark.django_db


@pytest.fixture
def service(make_image):
    category = Category.objects.create(name="Парк")
    CategoryService.objects.create(category=category, service=Service.objects.create(name="Другая"), order=4)
    service = Service.objects.create(
        name="Фрироуп",
        price="1500",
        price_unit="час",
        short_description="<p>Час</p>",
        has_page=True,
        seo_title="SEO",
        seo_description="Описание",
    )
    CategoryService.objects.create(category=category, service=service, order=1)
    ServicePhoto.objects.create(service=service, image=make_image("a.jpg"), order=1)
    return service


def test_service_duplicate(service, django_capture_on_commit_callbacks):
    copy = service.duplicate()
    assert copy.pk != service.pk and copy.slug != service.slug
    assert copy.name == "Фрироуп (копия)"
    assert (copy.price, copy.price_unit, copy.short_description, copy.has_page) == ("1500", "час", "<p>Час</p>", True)
    assert not copy.is_published
    assert (copy.seo_title, copy.seo_description) == ("", "")
    assert CategoryService.objects.get(service=copy).order == 5  # в конец категории
    original_photo, copied_photo = service.photos.get(), copy.photos.get()
    assert copied_photo.image.name != original_photo.image.name
    with django_capture_on_commit_callbacks(execute=True):
        copy.delete()
    assert original_photo.image.storage.exists(original_photo.image.name)


def test_duplicate_skips_missing_file(service):
    photo = service.photos.get()
    photo.image.storage.delete(photo.image.name)
    copy = service.duplicate()
    assert copy.photos.count() == 0


def test_service_duplicate_skips_trashed_categories(service):
    trashed = Category.objects.create(name="Старая")
    CategoryService.objects.create(category=trashed, service=service, order=1)
    trashed.move_to_trash()
    copy = service.duplicate()
    assert list(copy.category_links.values_list("category__name", flat=True)) == ["Парк"]


def test_event_duplicate(make_image):
    event = Event.objects.create(title="Клубная встреча", date=date(2026, 11, 1), image=make_image(), price="500")
    copy = event.duplicate()
    assert copy.title == "Клубная встреча (копия)" and copy.date == event.date and copy.price == "500"
    assert not copy.is_published and copy.slug != event.slug
    assert copy.image.name != event.image.name


def test_duplicate_get_only_asks_for_confirmation(admin_client, service):
    response = admin_client.get(reverse("admin:catalog_service_duplicate", args=[service.pk]))
    assert response.status_code == 200
    assert "Создать черновик-копию" in response.content.decode()
    assert Service.objects.count() == 2


def test_duplicate_post_creates_copy_and_redirects(admin_client, service):
    response = admin_client.post(reverse("admin:catalog_service_duplicate", args=[service.pk]))
    copy = Service.objects.exclude(pk=service.pk).get(name__endswith="(копия)")
    assert response.status_code == 302
    assert response.url == reverse("admin:catalog_service_change", args=[copy.pk])


def test_event_duplicate_get_asks_post_creates(admin_client):
    event = Event.objects.create(title="Встреча", date=date(2026, 11, 1))
    url = reverse("admin:content_event_duplicate", args=[event.pk])
    assert admin_client.get(url).status_code == 200
    assert Event.objects.count() == 1
    response = admin_client.post(url)
    copy = Event.objects.exclude(pk=event.pk).get()
    assert response.status_code == 302
    assert response.url == reverse("admin:content_event_change", args=[copy.pk])
    assert not copy.is_published


def test_duplicate_post_without_csrf_token_is_rejected(admin_user, service):
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    response = client.post(reverse("admin:catalog_service_duplicate", args=[service.pk]))
    assert response.status_code == 403
    assert Service.objects.count() == 2


@pytest.mark.parametrize("method", ["get", "post"])
def test_duplicate_requires_add_permission(client, django_user_model, service, method):
    staff = django_user_model.objects.create_user("editor", password="x", is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="change_service"))
    client.force_login(staff)
    response = getattr(client, method)(reverse("admin:catalog_service_duplicate", args=[service.pk]))
    assert response.status_code == 403
    assert Service.objects.count() == 2


def test_duplicate_button_is_on_the_form(admin_client, service):
    url = reverse("admin:catalog_service_duplicate", args=[service.pk])
    response = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk]))
    assert url in response.content.decode()


def test_trashed_service_has_no_duplicate(admin_client, service):
    service.move_to_trash()
    url = reverse("admin:catalog_service_duplicate", args=[service.pk])
    assert admin_client.get(url).status_code == 404
    preview = admin_client.get(reverse("admin:catalog_service_trash_detail", args=[service.pk]))
    assert preview.status_code == 200
    assert url not in preview.content.decode()
    assert Service.objects.count() == 2


def test_trashed_event_has_no_duplicate(admin_client):
    event = Event.objects.create(title="Встреча", date=date(2026, 11, 1))
    event.move_to_trash()
    url = reverse("admin:content_event_duplicate", args=[event.pk])
    assert admin_client.get(url).status_code == 404
    preview = admin_client.get(reverse("admin:content_event_trash_detail", args=[event.pk]))
    assert preview.status_code == 200
    assert url not in preview.content.decode()
    assert Event.objects.count() == 1
