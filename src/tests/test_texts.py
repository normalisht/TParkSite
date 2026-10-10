import pytest
from django.urls import reverse

from apps.texts.models import SiteText
from apps.texts.registry import BY_KEY, TEXTS, Page, sync_texts

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


def test_registry_keys_unique_and_pages_known():
    assert len(TEXTS) == len(BY_KEY) == 48
    assert {item.page for item in TEXTS} <= set(Page.values)


def test_migration_created_all_texts_with_initial_version():
    assert dict(SiteText.objects.values_list("key", "text")) == {item.key: item.default for item in TEXTS}
    initial = SiteText.history.filter(history_type="+")
    assert initial.count() == len(TEXTS)
    assert set(initial.values_list("history_change_reason", flat=True)) == {"Начальный текст"}


def test_sync_keeps_edits_restores_labels_and_missing_rows():
    edited = SiteText.objects.get(key="service.booking_hint")
    edited.text, edited.label = "Свой текст", "Старое название"
    edited.save()
    SiteText.objects.filter(key="gallery.empty").delete()
    history = SiteText.history.model

    assert sync_texts(SiteText, history) == 1
    edited.refresh_from_db()
    assert edited.text == "Свой текст" and edited.label == BY_KEY["service.booking_hint"].label
    restored = SiteText.objects.get(key="gallery.empty")
    assert restored.text == BY_KEY["gallery.empty"].default and restored.page == "gallery"
    assert history.objects.filter(id=restored.pk, history_type="+").count() == 1
    assert sync_texts(SiteText, history) == 0
