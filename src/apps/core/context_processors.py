from django.conf import settings

from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.opening_hours import human_opening_hours
from apps.core.request_cache import cached_on_request
from apps.core.seo import SITE_DESCRIPTION, absolute_url, plaintext


def _site_context(request):
    settings_obj = SiteSettings.for_request(request)
    phones = list(settings_obj.phones.all())
    privacy_page, safety_page = (
        page if page and page.is_published else None for page in (settings_obj.privacy_page, settings_obj.safety_page)
    )
    return {
        "site": settings_obj,
        "phones": phones,
        # Часы работы по-русски: для подвала, главной и страницы контактов.
        "hours": human_opening_hours(settings_obj.opening_hours),
        # Ссылки в подвале: только опубликованные страницы.
        "privacy_page": privacy_page,
        "safety_page": safety_page,
        "whatsapp_phone": next((p for p in phones if p.is_whatsapp), None),
        "telegram_phone": next((p for p in phones if p.is_telegram), None),
        "default_description": plaintext(settings_obj.home_intro) or SITE_DESCRIPTION,
        "default_og_image": absolute_url(request, safe_spec_url(settings_obj, "og_card")),
        # Адрес страницы без параметров (utm и т. п.): канонический для поисковиков.
        "canonical_url": request.build_absolute_uri(request.path),
        "metrika_enabled": bool(settings_obj.yandex_metrika_id) and not settings.DEBUG,
        # Тема первого сообщения в WhatsApp; страницы услуг, категорий и мероприятий задают свою.
        "contact_topic": "",
    }


def site(request):
    return cached_on_request(request, "site_context", lambda: _site_context(request))
