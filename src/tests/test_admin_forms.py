import pytest
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("url_name", "model"), [("admin:catalog_service_change", Service), ("admin:catalog_category_change", Category)]
)
def test_one_row_of_tabs_and_bulk_upload_in_photos_tab(admin_client, url_name, model):
    obj = model.objects.create(name="Тест")
    page = admin_client.get(reverse(url_name, args=[obj.pk])).content.decode()
    assert "activeFieldsetTab" not in page  # нет второй строки вкладок
    photos_group = page.index('id="photos-group"')
    assert page.index('name="bulk_photos"') > photos_group  # поле пачки — во вкладке фото


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
