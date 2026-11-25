import uuid

import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import CookieConsentEvent, InfoPage, SiteSettings
from apps.texts.models import SiteText

pytestmark = pytest.mark.django_db
URL = "/cookie-consent/"


@pytest.fixture
def consent_site():
    site = SiteSettings.load()
    site.privacy_page = InfoPage.objects.create(title="Политика сайта", body="<p>Редакция один</p>")
    site.yandex_metrika_id = "12345"
    site.save()
    return site


def post(client, decision, **fields):
    token = client.get(URL).json()["csrfToken"]
    return client.post(URL, {"decision": decision, **fields}, content_type="application/json", HTTP_X_CSRFTOKEN=token)


def test_records_document_and_keeps_retry_and_revocation_idempotent(consent_site):
    client = Client(enforce_csrf_checks=True)
    state = client.get(URL)
    assert state.json()["allowed"] is False
    assert "no-store" in state["Cache-Control"]
    assert "metrika-consent" not in client.cookies
    inputs = {"document": state.json()["document"], "attempt": str(uuid.uuid4())}
    assert client.post(URL, {"decision": "allow", **inputs}, content_type="application/json").status_code == 403
    response = post(client, "allow", **inputs)
    assert response.status_code == 200
    assert response.cookies["metrika-consent"]["httponly"]
    assert client.get(URL).json()["allowed"] is True

    retry = Client(enforce_csrf_checks=True)
    assert post(retry, "allow", **inputs).status_code == 200
    assert CookieConsentEvent.objects.count() == 1
    consent = CookieConsentEvent.objects.get()
    assert consent.document.payload["policy"]["body"] == "<p>Редакция один</p>"
    assert consent.document.payload["webvisor"] is True
    assert "Принять" in consent.document.payload["notice"]

    withdrawal = post(client, "revoke")
    assert withdrawal.status_code == 200
    assert withdrawal.cookies["metrika-consent"]["max-age"] == 0
    assert post(client, "revoke").status_code == 200
    assert post(retry, "allow", **inputs).status_code == 409
    assert client.get(URL).json()["allowed"] is False
    assert list(CookieConsentEvent.objects.order_by("pk").values_list("action", "receipt")) == [
        ("allow", consent.receipt),
        ("revoke", consent.receipt),
    ]


def test_rejects_outdated_text_and_only_renewed_version_expires_consent(client, consent_site):
    document = client.get(URL).json()["document"]
    assert post(client, "allow", document=document, attempt=str(uuid.uuid4())).status_code == 200
    text = SiteText.objects.get(key="common.cookie_text")
    text.text = "Новый текст про необязательные cookie."
    text.save()
    assert client.get(URL).json()["document"] != document
    assert post(client, "allow", document=document, attempt=str(uuid.uuid4())).status_code == 409
    assert client.get(URL).json()["allowed"] is True

    consent_site.metrika_consent_version += 1
    consent_site.save()
    assert client.get(URL).json()["allowed"] is False


def test_can_record_withdrawal_while_analytics_disabled(client, consent_site, settings):
    document = client.get(URL).json()["document"]
    assert post(client, "allow", document=document, attempt=str(uuid.uuid4())).status_code == 200
    settings.DEBUG = True
    assert client.get(URL + "?check=withdrawal").json() == {"canRevoke": True}
    assert post(client, "revoke").status_code == 200
    assert client.get(URL + "?check=withdrawal").json() == {"canRevoke": False}
    assert CookieConsentEvent.objects.filter(action="revoke").count() == 1


def test_withdrawal_check_does_not_set_cookies_for_new_visitors(client):
    response = client.get(URL + "?check=withdrawal")
    assert response.json() == {"canRevoke": False}
    assert not response.cookies
    assert "no-store" in response["Cache-Control"]


def test_withdrawal_without_receipt_recovers_committed_grant_or_cancels_late_request(client, consent_site):
    document = client.get(URL).json()["document"]
    attempt = str(uuid.uuid4())
    assert post(client, "allow", document=document, attempt=attempt).status_code == 200
    client.cookies.pop("metrika-consent")
    assert post(client, "revoke", attempt=attempt).status_code == 200
    assert list(CookieConsentEvent.objects.order_by("pk").values_list("action", flat=True)) == ["allow", "revoke"]

    late_attempt = str(uuid.uuid4())
    assert post(client, "revoke", attempt=late_attempt).status_code == 200
    assert post(client, "allow", document=document, attempt=late_attempt).status_code == 409
    assert CookieConsentEvent.objects.count() == 2


def test_admin_can_read_but_cannot_change_journal(admin_client, consent_site):
    document = admin_client.get(URL).json()["document"]
    assert post(admin_client, "allow", document=document, attempt=str(uuid.uuid4())).status_code == 200
    event = CookieConsentEvent.objects.get()
    changelist = reverse("admin:core_cookieconsentevent_changelist")
    search = admin_client.get(changelist, {"q": str(event.receipt)})
    assert list(search.context["cl"].result_list) == [event]
    url = reverse("admin:core_cookieconsentevent_change", args=[event.pk])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert "Редакция один" in response.content.decode()
    assert admin_client.post(url, {"action": "revoke"}).status_code == 403
    event.refresh_from_db()
    assert event.action == CookieConsentEvent.Action.ALLOW
