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


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("url_name", ["admin:catalog_service_duplicate", "admin:content_event_duplicate"])
def test_duplicate_bad_id_is_404(admin_client, url_name, method):
    for object_id in ("abc", "999"):
        response = getattr(admin_client, method)(reverse(url_name, args=[object_id]))
        assert response.status_code == 404


def _event_data(event, **changes):
    data = {
        "title": event.title,
        "slug": event.slug,
        "date": event.date.isoformat(),
        "price": event.price,
        "description": event.description,
        **({"is_published": "on"} if event.is_published else {}),
    }
    return {**data, **changes}


def _service_data(service, **changes):
    data = {"name": service.name, "slug": service.slug, "price": service.price, "price_unit": service.price_unit}
    for prefix in ("photos", "category_links"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"})
    return {**data, **({"is_published": "on"} if service.is_published else {}), **changes}


def _save(admin_client, obj, data):
    opts = obj._meta
    url = reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])
    response = admin_client.post(url, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    obj.refresh_from_db()
    return obj


def _copy(admin_client, obj):
    opts = obj._meta
    admin_client.post(reverse(f"admin:{opts.app_label}_{opts.model_name}_duplicate", args=[obj.pk]))
    return type(obj).objects.latest("pk")


def test_event_copy_slug_follows_title_and_year(admin_client):
    from apps.core.models import Redirect

    event = Event.objects.create(title="Клубная встреча", date=date(2026, 11, 1))
    copy = _copy(admin_client, event)
    assert copy.slug == "klubnaia-vstrecha-kopiia-2026"
    copy = _save(admin_client, copy, _event_data(copy, title="Клубная встреча", date="2027-11-07"))
    assert copy.slug == "klubnaia-vstrecha-2027"
    copy = _save(admin_client, copy, _event_data(copy, title="Клубная встреча летом", is_published="on"))
    assert copy.slug == "klubnaia-vstrecha-letom-2027"  # публикуют вместе с переименованием — адрес новый
    # С адреса копии («…-kopiia-…») редиректа нет. Промежуточный адрес черновика остаётся: без поля «был
    # опубликован» его не отличить от адреса записи, которую сняли с публикации, а редирект срабатывает только на 404.
    assert not Redirect.objects.filter(old_path__contains="kopiia").exists()


def test_service_copy_slug_follows_name(admin_client, service):
    from apps.core.models import Redirect

    copy = _copy(admin_client, service)
    copy = _save(admin_client, copy, _service_data(copy, name="Фрироуп на день"))
    assert copy.slug == "friroup-na-den"
    assert not Redirect.objects.exists()


def test_published_slug_stays_on_rename(admin_client, service):
    event = Event.objects.create(title="Клубная встреча", date=date(2026, 11, 1))
    _save(admin_client, event, _event_data(event, title="Клубный вечер", date="2027-01-10"))
    assert event.slug == "klubnaia-vstrecha-2026"
    _save(admin_client, service, _service_data(service, name="Фрироуп на день"))
    assert service.slug == "friroup"


def test_hand_edited_draft_slug_stays(admin_client, service):
    copy = _copy(admin_client, service)
    copy = _save(admin_client, copy, _service_data(copy, name="Фрироуп на день", slug="den"))
    assert copy.slug == "den"
    copy = _save(admin_client, copy, _service_data(copy, name="Фрироуп на сутки"))  # адрес задан руками раньше
    assert copy.slug == "den"


def test_once_public_draft_keeps_redirect_on_rename(admin_client, client, service):
    """Опубликованную услугу убрали в корзину и восстановили (или просто сняли с публикации), потом переименовали:
    адрес следует за названием, но старый — возможно, уже в поиске — ведёт на новый."""
    service.move_to_trash()
    service.restore()
    old_url = service.get_absolute_url()
    service = _save(admin_client, service, _service_data(service, name="Фрироуп на сутки"))
    assert service.slug == "friroup-na-sutki"
    service.is_published = True
    service.save()
    response = client.get(old_url)
    assert response.status_code == 301
    assert response["Location"].endswith(service.get_absolute_url())
