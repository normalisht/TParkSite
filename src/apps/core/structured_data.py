"""Структурированные данные schema.org (JSON-LD). Узлы собираются в `@graph` фильтром `ld_json`.

Услуги и мероприятия ссылаются на организацию по `@id`, поэтому узел `organization()` кладём в граф
каждой страницы, где есть такие ссылки.
"""

import re

from django.templatetags.static import static
from django.urls import reverse

from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.seo import plaintext

SITE_NAME = "Т-Парк"
ALTERNATE_NAME = "Тренинг-парк Дмитрия Сергеева"


def organization_id(request) -> str:
    return request.build_absolute_uri("/") + "#organization"


def postal_address(site: SiteSettings) -> dict:
    address = {"@type": "PostalAddress", "addressCountry": "RU"}
    for key, value in (
        ("addressRegion", site.address_region),
        ("addressLocality", site.address_locality),
        ("streetAddress", site.street_address),
        ("postalCode", site.postal_code),
    ):
        if value:
            address[key] = value
    return address


def founder(request, site: SiteSettings) -> dict | None:
    """Основатель (`Person`) для узла организации на странице «О нас»."""
    if not site.founder_name:
        return None
    photo = safe_spec_url(site, "founder_card")
    return _compact(
        {"@type": "Person", "name": site.founder_name, "image": request.build_absolute_uri(photo) if photo else None}
    )


def organization(request, *, with_founder: bool = False) -> dict:
    """Т-Парк как местная организация: адрес, телефоны, координаты, ссылки на VK и Яндекс Карты."""
    site = SiteSettings.load()
    data = {
        "@type": "LocalBusiness",
        "@id": organization_id(request),
        "name": SITE_NAME,
        "alternateName": ALTERNATE_NAME,
        "url": request.build_absolute_uri("/"),
        "logo": request.build_absolute_uri(static("img/logo.png")),
        "address": postal_address(site),
        "description": plaintext(site.home_intro) or None,
        "telephone": [phone.tel_url.removeprefix("tel:") for phone in site.phones.all()] or None,
        "image": request.build_absolute_uri(url) if (url := safe_spec_url(site, "og_card")) else None,
        "openingHours": site.opening_hours or None,
        "priceRange": site.price_range or None,
        "sameAs": [url for url in (site.vk_url, site.yandex_maps_url) if url] or None,
        "founder": founder(request, site) if with_founder else None,
    }
    if site.latitude is not None and site.longitude is not None:
        data["geo"] = {"@type": "GeoCoordinates", "latitude": float(site.latitude), "longitude": float(site.longitude)}
    return _compact(data)


def breadcrumbs(request, items: list[tuple[str, str]]) -> dict:
    """`BreadcrumbList` из [(название, путь)]; у последней крошки (текущей страницы) путь можно не указывать."""
    elements = []
    for position, (name, url) in enumerate(items, start=1):
        element = {"@type": "ListItem", "position": position, "name": name}
        if url:
            element["item"] = request.build_absolute_uri(url)
        elements.append(element)
    return {"@type": "BreadcrumbList", "itemListElement": elements}


def home_crumb() -> tuple[str, str]:
    return ("Главная", reverse("catalog:home"))


def service(request, service) -> dict:
    data = {
        "@type": "Service",
        "name": service.name,
        "url": request.build_absolute_uri(service.get_absolute_url()) if service.has_page else None,
        "description": plaintext(service.seo_description or service.short_description or service.description) or None,
        "provider": {"@id": organization_id(request)},
        "areaServed": SiteSettings.load().address_region or None,
    }
    # Цена бывает текстом («договорная») — в разметку попадает только число.
    price = service.price.replace(" ", "")
    if price.isdecimal():
        offer = {"@type": "Offer", "price": price, "priceCurrency": "RUB"}
        if service.price_unit:
            offer["priceSpecification"] = {
                "@type": "UnitPriceSpecification",
                "price": price,
                "priceCurrency": "RUB",
                "unitText": service.price_unit,
            }
        data["offers"] = offer
    return _compact(data)


def service_list(request, category, services) -> dict:
    return {
        "@type": "ItemList",
        "name": category.name,
        "itemListElement": [
            {"@type": "ListItem", "position": position, "item": service(request, item)}
            for position, item in enumerate(services, start=1)
        ],
    }


def price_offer(text: str, url: str) -> dict | None:
    """Цена из свободного текста («1000 ₽ с участника», «Бесплатно») — `Offer`; без числа — None."""
    if "бесплатн" in text.lower():
        amount = "0"
    elif match := re.search(r"\d[\d\s\u00a0]*", text):
        amount = re.sub(r"\D", "", match.group())
    else:
        return None
    return {"@type": "Offer", "price": amount, "priceCurrency": "RUB", "url": url}


def event(request, event, seo: dict) -> dict:
    site = SiteSettings.load()
    url = request.build_absolute_uri(event.get_absolute_url())
    starts_at = event.starts_at
    return _compact(
        {
            "@type": "Event",
            "name": event.title,
            "startDate": starts_at.isoformat() if starts_at else event.date.isoformat(),
            "endDate": event.last_date.isoformat(),
            "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "url": url,
            "description": seo["description"] or None,
            "image": [seo["image"]] if seo["image"] else None,
            "location": {"@type": "Place", "name": SITE_NAME, "address": postal_address(site)},
            "organizer": {"@id": organization_id(request)},
            "offers": price_offer(event.price, url) if event.price else None,
        }
    )


def _compact(data: dict) -> dict:
    return {key: value for key, value in data.items() if value is not None}
