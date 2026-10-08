import pytest
from django.contrib import admin
from django.urls import reverse

from apps.catalog.models import Category, CategoryPhoto
from apps.content.models import GalleryPhoto
from apps.core.models import Phone, SiteSettings

pytestmark = pytest.mark.django_db


def test_every_registered_model_list_and_add_open(admin_client):
    for model, model_admin in admin.site._registry.items():
        info = (model._meta.app_label, model._meta.model_name)
        response = admin_client.get(reverse("admin:{}_{}_changelist".format(*info)), follow=True)
        assert response.status_code == 200, model
        if model_admin.has_add_permission(response.wsgi_request):
            assert admin_client.get(reverse("admin:{}_{}_add".format(*info))).status_code == 200, model


def test_site_settings_changelist_redirects_to_form(admin_client):
    response = admin_client.get(reverse("admin:core_sitesettings_changelist"))
    assert response.status_code == 302
    assert response.url == reverse("admin:core_sitesettings_change", args=[1])


def _settings_post(phones):
    """Данные формы настроек сайта с inline-телефонами."""
    data = {
        "address": "село Восход",
        "map_url": "",
        "vk_url": "",
        "phones-TOTAL_FORMS": str(len(phones)),
        "phones-INITIAL_FORMS": str(sum(1 for p in phones if p.get("id"))),
        "phones-MIN_NUM_FORMS": "0",
        "phones-MAX_NUM_FORMS": "1000",
    }
    for i, phone in enumerate(phones):
        for key, value in phone.items():
            if value is True:
                data[f"phones-{i}-{key}"] = "on"
            elif value is not False and value is not None:
                data[f"phones-{i}-{key}"] = str(value)
        data[f"phones-{i}-settings"] = "1"
    return data


def test_two_whatsapp_flags_rejected(admin_client):
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(
        url,
        _settings_post(
            [
                {"number": "9000000001", "order": 0, "is_whatsapp": True},
                {"number": "9000000002", "order": 1, "is_whatsapp": True},
            ]
        ),
    )
    assert response.status_code == 200
    assert "WhatsApp можно отметить только у одного номера" in response.content.decode()
    assert Phone.objects.count() == 0


def test_phone_flag_can_move_between_numbers(admin_client):
    site = SiteSettings.load()
    first = Phone.objects.create(settings=site, number="9000000001", order=0, is_whatsapp=True)
    second = Phone.objects.create(settings=site, number="9000000002", order=1)
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(
        url,
        _settings_post(
            [
                {"id": first.id, "number": "9000000001", "order": 0, "is_whatsapp": False},
                {"id": second.id, "number": "9000000002", "order": 1, "is_whatsapp": True},
            ]
        ),
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    second.refresh_from_db()
    first.refresh_from_db()
    assert second.is_whatsapp and not first.is_whatsapp


def _category_post(category, **extra):
    data = {
        "name": category.name,
        "slug": category.slug,
        "description": "",
        "order": "0",
        "photos-TOTAL_FORMS": "0",
        "photos-INITIAL_FORMS": "0",
        "photos-MIN_NUM_FORMS": "0",
        "photos-MAX_NUM_FORMS": "1000",
        "service_links-TOTAL_FORMS": "0",
        "service_links-INITIAL_FORMS": "0",
        "service_links-MIN_NUM_FORMS": "0",
        "service_links-MAX_NUM_FORMS": "1000",
    }
    data.update(extra)
    return data


def test_bulk_upload_appends_photos_to_category(admin_client, make_image):
    category = Category.objects.create(name="Сплавы")
    CategoryPhoto.objects.create(category=category, image=make_image(), order=7)
    url = reverse("admin:catalog_category_change", args=[category.pk])
    response = admin_client.post(
        url, _category_post(category, bulk_photos=[make_image("a.jpg"), make_image("b.png", fmt="PNG")])
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert list(category.photos.values_list("order", flat=True)) == [7, 8, 9]


def test_bulk_upload_rejects_whole_batch_on_bad_file(admin_client, make_image):
    category = Category.objects.create(name="Сплавы")
    url = reverse("admin:catalog_category_change", args=[category.pk])
    response = admin_client.post(
        url, _category_post(category, bulk_photos=[make_image("a.jpg"), make_image("c.gif", fmt="GIF")])
    )
    assert response.status_code == 200
    assert category.photos.count() == 0


def test_gallery_bulk_upload_view(admin_client, make_image):
    url = reverse("admin:content_galleryphoto_bulk_upload")
    assert admin_client.get(url).status_code == 200
    response = admin_client.post(url, {"photos": [make_image("1.jpg"), make_image("2.jpg")]})
    assert response.status_code == 302
    assert list(GalleryPhoto.objects.values_list("order", flat=True)) == [1, 2]
