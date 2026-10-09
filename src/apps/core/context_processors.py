from django.conf import settings

from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.seo import SITE_DESCRIPTION, absolute_url, plaintext


def site(request):
    settings_obj = SiteSettings.load()
    phones = list(settings_obj.phones.all())
    return {
        "site": settings_obj,
        "phones": phones,
        "whatsapp_phone": next((p for p in phones if p.is_whatsapp), None),
        "telegram_phone": next((p for p in phones if p.is_telegram), None),
        "default_description": plaintext(settings_obj.home_intro) or SITE_DESCRIPTION,
        "default_og_image": absolute_url(request, safe_spec_url(settings_obj, "og_card")),
        # Адрес страницы без параметров (utm и т. п.): канонический для поисковиков.
        "canonical_url": request.build_absolute_uri(request.path),
        "metrika_enabled": bool(settings_obj.yandex_metrika_id) and not settings.DEBUG,
    }
