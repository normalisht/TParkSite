from apps.core.models import SiteSettings
from apps.core.seo import plaintext


def site(request):
    settings_obj = SiteSettings.load()
    phones = list(settings_obj.phones.all())
    return {
        "site": settings_obj,
        "phones": phones,
        "whatsapp_phone": next((p for p in phones if p.is_whatsapp), None),
        "telegram_phone": next((p for p in phones if p.is_telegram), None),
        "default_description": plaintext(settings_obj.home_intro) or "Т-Парк — активный отдых в Калужской области.",
    }
