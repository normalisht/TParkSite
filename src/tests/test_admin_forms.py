import re
from datetime import date

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


CHANGE_FORMS = [
    ("admin:catalog_service_change", Service, "category_links"),
    ("admin:catalog_category_change", Category, "service_links"),
]


@pytest.mark.parametrize(("url_name", "model", "next_inline"), CHANGE_FORMS)
def test_one_row_of_tabs_bulk_upload_in_photos_tab_and_seo_tab(admin_client, url_name, model, next_inline):
    obj = model.objects.create(name="Тест")
    page = admin_client.get(reverse(url_name, args=[obj.pk])).content.decode()
    assert "activeFieldsetTab" not in page  # нет второй строки вкладок
    assert re.search(r'<a href="#seo"[^>]*>\s*SEO\s*</a>', page)  # вкладка SEO — в том же ряду, что и остальные
    photos_group, next_group = page.index('id="photos-group"'), page.index(f'id="{next_inline}-group"')
    assert photos_group < page.index('name="bulk_photos"') < next_group  # поле пачки — только во вкладке фото
    assert 'id="seo-group"' in page  # по нему Unfold открывает вкладку из #seo
    seo_pane = page.index("x-show=\"activeTab == 'seo'\"")
    assert page.index('id="id_name"') < seo_pane < page.index('name="seo_title"')  # SEO-поля — в своей вкладке
    assert page.index('name="seo_title"') < page.index('name="seo_description"')
    assert page.index('name="seo_description"') < photos_group  # а сама вкладка — до inline-вкладок в разметке


@pytest.mark.parametrize(("url_name", "model", "next_inline"), CHANGE_FORMS)
def test_seo_error_is_shown_on_seo_tab_badge(admin_client, url_name, model, next_inline):
    obj = model.objects.create(name="Тест")
    url = reverse(url_name, args=[obj.pk])
    form = admin_client.get(url).context["adminform"].form
    data = {name: form[name].value() for name in form.fields if name != "bulk_photos" and form[name].value()}
    data["seo_title"] = "я" * 400
    data.update(
        {f"{prefix}-{key}": "0" for prefix in ("photos", next_inline) for key in ("TOTAL_FORMS", "INITIAL_FORMS")}
    )
    response = admin_client.post(url, data)
    assert response.status_code == 200
    page = response.content.decode()
    assert re.search(r'<a href="#seo"[^>]*>\s*SEO\s*<span class="bg-red-500[^>]*>\s*1\s*</span>', page)
    assert not re.search(r'<a href="#general"[^>]*>\s*Основное\s*<span class="bg-red-500', page)  # не засчитано дважды


def test_bulk_upload_still_saves(admin_client, make_image):
    service = Service.objects.create(name="Тест")
    url = reverse("admin:catalog_service_change", args=[service.pk])
    form = admin_client.get(url).context["adminform"].form
    data = {name: form[name].value() or "" for name in form.fields if name != "bulk_photos"}
    for prefix in ("photos", "category_links"):
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0"})
    data["bulk_photos"] = [make_image("a.jpg"), make_image("b.jpg")]
    response = admin_client.post(url, data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert service.photos.count() == 2


def test_phones_have_own_tab(admin_client):
    SiteSettings.load()
    page = admin_client.get(reverse("admin:core_sitesettings_change", args=[1])).content.decode()
    assert "activeTab == 'phones'" in page


def test_site_settings_name():
    assert str(SiteSettings()) == "Основные"


def test_change_form_wording(admin_client):
    service = Service.objects.create(name="Батут")
    page = admin_client.get(reverse("admin:catalog_service_change", args=[service.pk])).content.decode()
    for awkward in (
        "Удалить Услуга",
        "Добавить еще один",
        "Сохранить и добавить другой объект",
        "Choose file to upload",
    ):
        assert awkward not in page
    # Positive assertions: delete button is just "Удалить" and add button is "Добавить ещё"
    assert "Добавить ещё" in page  # inline add button with neutral wording


def test_saved_message_wording(admin_client):
    response = admin_client.post(
        reverse("admin:content_review_add"),
        {"text": "<p>Отлично</p>", "date": date(2026, 7, 14).strftime("%d.%m.%Y"), "is_published": "on", "link": ""},
    )
    assert response.status_code == 302
    texts = [str(m) for m in get_messages(response.wsgi_request)]
    assert any(t.endswith("— добавлено.") for t in texts), texts


def test_changelist_total_wording(admin_client):
    Category.objects.create(name="А")
    Category.objects.create(name="Б")
    page = admin_client.get(reverse("admin:catalog_category_changelist")).content.decode()
    assert "Всего: 2" in page


def test_saved_message_wording_continue_editing(admin_client):
    response = admin_client.post(
        reverse("admin:content_review_add"),
        {
            "text": "<p>Отлично</p>",
            "date": date(2026, 7, 14).strftime("%d.%m.%Y"),
            "is_published": "on",
            "link": "",
            "_continue": "Save and continue editing",
        },
    )
    assert response.status_code == 302
    # Follow the redirect to get the messages
    response = admin_client.get(response.url)
    texts = [str(m) for m in get_messages(response.wsgi_request)]
    # Message format: my custom translation of the main part + Django's Russian translation of "You may edit it again below"
    assert any("— добавлено." in t for t in texts), texts


def test_saved_message_wording_add_another(admin_client):
    response = admin_client.post(
        reverse("admin:content_review_add"),
        {
            "text": "<p>Отлично</p>",
            "date": date(2026, 7, 14).strftime("%d.%m.%Y"),
            "is_published": "on",
            "link": "",
            "_addanother": "Save and add another",
        },
    )
    assert response.status_code == 302
    texts = [str(m) for m in get_messages(response.wsgi_request)]
    assert any(t.endswith("— добавлено. Ниже можно добавить ещё.") for t in texts), texts
