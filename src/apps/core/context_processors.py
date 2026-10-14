from django.conf import settings
from django.templatetags.static import static

from apps.core.images import safe_spec_url
from apps.core.models import HEADER_LOGO_HEIGHT, InfoPage, SiteSettings
from apps.core.opening_hours import human_opening_hours
from apps.core.request_cache import cached_on_request
from apps.core.seo import SITE_DESCRIPTION, absolute_url, plaintext

# Стандартный логотип шапки: 3× от 119×44 (квантованный PNG, грузится вместе с LCP-фото). Снизу — прозрачное поле
# высотой с выступ солнца над буквами: надпись по центру картинки, а значит, на одной оси с кнопками шапки.
DEFAULT_HEADER_LOGO = ("img/logo-header.png", 119, HEADER_LOGO_HEIGHT)


def header_logo(site: SiteSettings) -> dict:
    """Логотип для шапки: из настроек, а если его нет или миниатюра не получилась — стандартный."""
    if site.header_logo and (url := safe_spec_url(site, "header_logo_img")) and site.header_logo_display_width:
        return {"url": url, "width": site.header_logo_display_width, "height": HEADER_LOGO_HEIGHT}
    path, width, height = DEFAULT_HEADER_LOGO
    return {"url": static(path), "width": width, "height": height}


def _site_context(request):
    settings_obj = SiteSettings.for_request(request)
    phones = list(settings_obj.phones.all())
    privacy_page, safety_page = (
        page if page and page.is_published else None for page in (settings_obj.privacy_page, settings_obj.safety_page)
    )
    return {
        "site": settings_obj,
        "header_logo": header_logo(settings_obj),
        "phones": phones,
        # Часы работы по-русски: для подвала, главной и страницы контактов.
        "hours": human_opening_hours(settings_obj.opening_hours),
        # Политика (баннер cookie) и правила (плашка на «О нас»): только опубликованные страницы.
        "privacy_page": privacy_page,
        "safety_page": safety_page,
        # Инфо-страницы с галочкой «В подвале»; запрос — только при выводе подвала (в админке его нет).
        "footer_pages": InfoPage.objects.published().filter(show_in_footer=True).only("title", "slug"),
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
