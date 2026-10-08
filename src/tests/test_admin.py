import re

import pytest
from django.contrib import admin
from django.urls import reverse

from apps.catalog.models import Category, CategoryPhoto, Service
from apps.content.models import GalleryPhoto
from apps.core.models import InfoPage, Phone, SiteSettings

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


def test_editing_address_keeps_messenger_flags(admin_client):
    site = SiteSettings.load()
    phone = Phone.objects.create(settings=site, number="9000000001", order=0, is_whatsapp=True, is_telegram=True)
    url = reverse("admin:core_sitesettings_change", args=[1])
    data = _settings_post(
        [{"id": phone.id, "number": "9000000001", "order": 0, "is_whatsapp": True, "is_telegram": True}]
    )
    data["address"] = "новый адрес"
    response = admin_client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:2000]
    phone.refresh_from_db()
    assert phone.is_whatsapp and phone.is_telegram


def test_editing_other_phone_keeps_messenger_flags(admin_client):
    site = SiteSettings.load()
    owner = Phone.objects.create(settings=site, number="9000000001", order=0, is_whatsapp=True)
    other = Phone.objects.create(settings=site, number="9000000002", order=1)
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(
        url,
        _settings_post(
            [
                {"id": owner.id, "number": "9000000001", "order": 0, "is_whatsapp": True},
                {"id": other.id, "number": "9000000003", "order": 1},
            ]
        ),
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    owner.refresh_from_db()
    assert owner.is_whatsapp


def test_gallery_bulk_upload_requires_add_permission(client, django_user_model, make_image):
    staff = django_user_model.objects.create_user("staff", password="p", is_staff=True)
    client.force_login(staff)
    url = reverse("admin:content_galleryphoto_bulk_upload")
    assert client.get(url).status_code == 403
    client.post(url, {"photos": [make_image("1.jpg")]})
    assert GalleryPhoto.objects.count() == 0


def test_info_page_admin_shows_copy_url_button(admin_client):
    page = InfoPage.objects.create(title="Правила", slug="pravila", body="<p>Текст</p>")
    url = page.get_absolute_url()
    for admin_url in (
        reverse("admin:core_infopage_changelist"),
        reverse("admin:core_infopage_change", args=[page.pk]),
    ):
        content = admin_client.get(admin_url).content.decode()
        assert f'data-copy-url="{url}"' in content
        assert "content_copy" in content
        assert "js/admin_copy.js" in content


def test_admin_uses_site_favicon(admin_client):
    content = admin_client.get(reverse("admin:index")).content.decode()
    assert "img/favicon.svg" in content


def test_every_admin_warns_about_unsaved_changes(admin_client):
    for model, model_admin in admin.site._registry.items():
        assert "js/admin_unsaved.js" in str(model_admin.media), model
    assert "js/admin_unsaved.js" in admin_client.get(reverse("admin:catalog_category_changelist")).content.decode()
    # Собственный Media у наследника дополняет базовый, а не заменяет его.
    content = admin_client.get(reverse("admin:core_infopage_add")).content.decode()
    assert "js/admin_unsaved.js" in content and "js/admin_copy.js" in content


@pytest.mark.parametrize(
    ("model", "create_kwargs"),
    [
        (Service, {"name": "Баня", "slug": "banya"}),
        (InfoPage, {"title": "Правила", "slug": "pravila", "body": "<p>Текст</p>"}),
    ],
)
def test_is_published_editable_in_changelist(admin_client, model, create_kwargs):
    obj = model.objects.create(is_published=True, **create_kwargs)
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    response = admin_client.post(
        url,
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-id": str(obj.pk),
            "_save": "Сохранить",
        },
    )
    assert response.status_code == 302
    obj.refresh_from_db()
    assert obj.is_published is False


def test_general_tab_is_translated(admin_client):
    category = Category.objects.create(name="Сплавы")
    html = admin_client.get(f"/admin/catalog/category/{category.pk}/change/").content.decode()
    tab = re.search(r'<a href="#general"[^>]*>\s*(\S+)', html)
    assert tab and tab.group(1) == "Основное"


MAP_CODE = (
    '<iframe src="https://yandex.ru/map-widget/v1/?um=constructor%3Aabc&amp;source=constructor"'
    ' width="500" height="400" frameborder="0"></iframe>'
)


def test_map_embed_accepts_pasted_iframe_code(admin_client):
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(url, {**_settings_post([]), "map_embed_url": MAP_CODE})
    assert response.status_code == 302
    assert (
        SiteSettings.load().map_embed_url == "https://yandex.ru/map-widget/v1/?um=constructor%3Aabc&source=constructor"
    )


def test_map_embed_rejects_foreign_url(admin_client):
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(url, {**_settings_post([]), "map_embed_url": '<iframe src="https://evil.example/x">'})
    assert response.status_code == 200
    assert "Нужна ссылка виджета Яндекс Карт" in response.content.decode()
    assert SiteSettings.load().map_embed_url == ""


def test_file_fields_support_drag_and_drop(admin_client):
    """Скрипт перетаскивания подключён ко всем страницам админки; поле «пачкой» — виджет Unfold с multiple."""
    html = admin_client.get(reverse("admin:content_galleryphoto_bulk_upload")).content.decode()
    assert "js/admin_dropzone" in html
    assert re.search(r'<input type="file" name="photos"[^>]*\smultiple', html)
    assert "material-symbols-outlined" in html  # разметка Unfold, а не голый <input type=file>
    html = admin_client.get(reverse("admin:content_partner_add")).content.decode()
    assert "js/admin_dropzone" in html
