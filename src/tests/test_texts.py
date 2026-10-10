import pytest
from django.urls import reverse

from apps.texts.models import SiteText

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_text():
    return SiteText.objects.create(key="test.sample", page="common", label="Проба", text="Было", order=0)


def test_admin_edit_records_version_with_author(admin_client, admin_user, site_text):
    response = admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    assert response.status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Стало"
    latest = site_text.history.first()
    assert latest.history_type == "~" and latest.history_user == admin_user and latest.text == "Стало"


def test_revert_restores_old_version_as_new_one(admin_client, site_text):
    admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    first = site_text.history.earliest("history_date")
    url = reverse("admin:texts_sitetext_simple_history", args=[site_text.pk, first.history_id])
    assert admin_client.get(url).status_code == 200
    assert admin_client.post(url, {"text": first.text}).status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Было"
    assert site_text.history.count() == 3


def test_history_page_opens(admin_client, site_text):
    assert admin_client.get(reverse("admin:texts_sitetext_history", args=[site_text.pk])).status_code == 200
