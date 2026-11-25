import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.models import CancelledCookieConsentAttempt, CookieConsentDocument, CookieConsentEvent, SiteSettings
from apps.texts.context_processors import get_site_texts

COOKIE_NAME = "metrika-consent"
COOKIE_AGE = int(timedelta(days=365).total_seconds())
WEBVISOR = True


@dataclass(frozen=True)
class ConsentDocument:
    version: str
    fingerprint: str
    archive: str


def published_privacy_page(site):
    page = site.privacy_page
    return page if page and page.is_published and page.deleted_at is None else None


def current_document(request):
    site = SiteSettings.for_request(request)
    page = published_privacy_page(site)
    if settings.DEBUG or not site.yandex_metrika_id or page is None:
        return None

    version = f"{page.pk}:{site.metrika_consent_version}:{site.yandex_metrika_id}"
    payload = {
        "notice": render_to_string(
            "partials/cookie_notice.html",
            {"privacy_page": page, "site_texts": get_site_texts(request)},
        ).strip(),
        "policy": {"url": page.get_absolute_url(), "title": page.title, "lead": page.lead, "body": page.body},
        "counter": site.yandex_metrika_id,
        "webvisor": WEBVISOR,
    }
    archive = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(f"{version}\n{archive}".encode()).hexdigest()
    return ConsentDocument(version, fingerprint, archive)


def _receipt(request):
    signed = request.get_signed_cookie(COOKIE_NAME, default="", max_age=COOKIE_AGE)
    return uuid.UUID(signed) if signed else None


def _latest_event(receipt):
    if receipt:
        return CookieConsentEvent.objects.filter(receipt=receipt).select_related("document").first()
    return None


def _attempt(value):
    try:
        attempt = uuid.UUID(value)
    except ValueError, TypeError, AttributeError:
        return None
    return attempt if attempt.version == 4 else None


def _state(request):
    document = current_document(request)
    latest = _latest_event(_receipt(request))
    return JsonResponse(
        {
            "csrfToken": get_token(request),
            "document": document.fingerprint if document else None,
            "version": document.version if document else None,
            "allowed": bool(
                document
                and latest
                and latest.action == CookieConsentEvent.Action.ALLOW
                and latest.document.version == document.version
            ),
        }
    )


def _withdrawal_state(request):
    latest = _latest_event(_receipt(request))
    return JsonResponse({"canRevoke": bool(latest and latest.action == CookieConsentEvent.Action.ALLOW)})


def _allow(request, data):
    document = current_document(request)
    if document is None or data.get("document") != document.fingerprint:
        return JsonResponse({}, status=409)
    attempt = _attempt(data.get("attempt"))
    if attempt is None:
        return JsonResponse({}, status=400)
    if CancelledCookieConsentAttempt.objects.filter(pk=attempt).exists():
        return JsonResponse({}, status=409)
    # Повтор запроса до получения cookie должен вернуть ту же квитанцию.
    fallback = uuid.UUID(bytes=salted_hmac("cookie-consent-receipt", attempt.hex, algorithm="sha256").digest()[:16])
    receipt = _receipt(request) or fallback
    existing = CookieConsentEvent.objects.filter(attempt=attempt).first()
    if existing:
        latest = _latest_event(receipt)
        if latest is None or latest.pk != existing.pk or existing.document_id != document.fingerprint:
            return JsonResponse({}, status=409)
    else:
        archived, _ = CookieConsentDocument.objects.get_or_create(
            fingerprint=document.fingerprint, defaults={"version": document.version, "archive": document.archive}
        )
        CookieConsentEvent.objects.create(
            receipt=receipt, document=archived, action=CookieConsentEvent.Action.ALLOW, attempt=attempt
        )
    response = JsonResponse({"allowed": True})
    response.set_signed_cookie(
        COOKIE_NAME, str(receipt), max_age=COOKIE_AGE, httponly=True, secure=settings.CSRF_COOKIE_SECURE, samesite="Lax"
    )
    return response


def _revoke(request, data):
    receipts = {_receipt(request)}
    if data.get("attempt") is not None:
        attempt = _attempt(data["attempt"])
        if attempt is None:
            return JsonResponse({}, status=400)
        event = CookieConsentEvent.objects.filter(attempt=attempt).first()
        if event:
            receipts.add(event.receipt)
        else:
            # Отказ может прийти раньше запроса согласия, ответ на который браузер потерял.
            CancelledCookieConsentAttempt.objects.get_or_create(pk=attempt)
    for receipt in receipts - {None}:
        latest = _latest_event(receipt)
        if latest and latest.action == CookieConsentEvent.Action.ALLOW:
            CookieConsentEvent.objects.create(
                receipt=receipt, document_id=latest.document_id, action=CookieConsentEvent.Action.REVOKE
            )
    response = JsonResponse({"allowed": False})
    response.delete_cookie(COOKIE_NAME, samesite="Lax")
    return response


@transaction.atomic
def _record(request, data):
    decision = data.get("decision")
    if decision == CookieConsentEvent.Action.ALLOW:
        return _allow(request, data)
    if decision == CookieConsentEvent.Action.REVOKE:
        return _revoke(request, data)
    return JsonResponse({}, status=400)


@never_cache
@require_http_methods(["GET", "POST"])
def cookie_consent(request):
    if request.method == "GET":
        return _withdrawal_state(request) if request.GET.get("check") == "withdrawal" else _state(request)
    try:
        data = json.loads(request.body)
    except ValueError, UnicodeError:
        return JsonResponse({}, status=400)
    return _record(request, data) if isinstance(data, dict) else JsonResponse({}, status=400)
