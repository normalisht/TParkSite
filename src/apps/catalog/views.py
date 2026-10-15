from django.shortcuts import render

from apps.catalog.models import Category, Service
from apps.content.models import Event, GalleryPhoto, Review
from apps.core import structured_data as ld
from apps.core.images import lightbox_url, safe_spec_url
from apps.core.maps import route_links
from apps.core.models import PARK_ADDRESS, SiteSettings
from apps.core.preview import finish, get_for_view, preview_context
from apps.core.rotation import daily_pick
from apps.core.seo import absolute_url, make_seo, page_seo

HOME_REVIEWS = 8
HOME_EVENTS = 3


def home(request):
    site = SiteSettings.load()
    hero = safe_spec_url(site, "about_card")
    return render(
        request,
        "catalog/home.html",
        {
            "hero": hero,
            # Без фото в шапке крупнейший элемент первого экрана (LCP) — первая карточка категории.
            "lcp_card": not hero,
            "route": route_links(site.latitude, site.longitude),
            "events": list(Event.objects.published().upcoming()[:HOME_EVENTS]) if site.home_show_events else [],
            "photos": GalleryPhoto.strip_photos("home"),
            "reviews": list(Review.objects.published()[:HOME_REVIEWS]),
            "seo": page_seo("home"),
            "structured_data": [ld.organization(request)],
        },
    )


def category_detail(request, slug):
    category, preview = get_for_view(request, Category.objects.all(), slug=slug)
    photos = list(category.photos.all())
    services = category.published_services()
    # Шапка: превью категории, без него — первое фото. Полноразмерное — для просмотра на весь экран.
    if safe_spec_url(category, "preview_card"):
        hero, hero_srcset, hero_full = category, "preview_card 640w, preview_large 1080w", category.preview.url
    elif photos and safe_spec_url(photos[0], "slide"):
        hero, hero_srcset, hero_full = photos[0], "slide_small 800w, slide 1600w", lightbox_url(photos[0])
    else:
        hero, hero_srcset, hero_full = None, "", ""
    crumbs = [ld.home_crumb(), (category.name, "")]
    seo = make_seo(
        category.name,
        category.description,
        absolute_url(request, safe_spec_url(hero, "og")),
        obj=category,
        default_description=f"{category.name} в Т-Парке: услуги и цены. {PARK_ADDRESS}.",
    )
    if preview:
        seo["noindex"] = True
    response = render(
        request,
        "catalog/category.html",
        {
            "category": category,
            "photos": photos,
            "services": services,
            # Тема первого сообщения в WhatsApp (фильтр whatsapp_url).
            "contact_topic": category.name,
            # Услуги со своей страницей — карточками, остальные — компактным списком.
            "service_cards": [s for s in services if s.has_page],
            "service_rows": [s for s in services if not s.has_page],
            "hero": hero,
            "hero_srcset": hero_srcset,
            "hero_full": hero_full,
            "related": category.related_categories(),
            "breadcrumbs": crumbs,
            "seo": seo,
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.service_list(request, category, services),
            ],
            **preview_context(category, preview),
        },
    )
    return finish(response, preview)


RELATED_SERVICES = 3


def related_services(category, service, limit: int = RELATED_SERVICES) -> list:
    """Другие услуги категории со своей страницей: у каждой услуги свой набор, меняется раз в сутки — иначе ссылки
    получали бы только первые услуги категории. Варианты с тем же названием (в т. ч. текущей услуги) — один раз.
    """
    seen = {service.name.casefold()}
    candidates = []
    for item in category.published_services():
        name = item.name.casefold()
        if item.has_page and name not in seen:
            seen.add(name)
            candidates.append(item)
    return daily_pick(candidates, limit, key=f"service:{service.pk}")


def service_detail(request, slug):
    service, preview = get_for_view(request, Service.objects.filter(has_page=True), slug=slug)
    photos = list(service.photos.all())
    link = (
        service.category_links.filter(category__is_published=True)
        .select_related("category")
        .order_by("category__order", "category__id")
        .first()
    )
    category = link.category if link else None
    crumbs = [
        ld.home_crumb(),
        *([(category.name, category.get_absolute_url())] if category else []),
        (service.name, ""),
    ]
    image = safe_spec_url(photos[0], "og") if photos else ""
    related = related_services(category, service) if category else []
    seo = make_seo(
        service.name,
        service.short_description or service.description,
        absolute_url(request, image),
        obj=service,
        default_description=" ".join(
            filter(None, [f"{service.name} в Т-Парке.", service.price_display, f"{PARK_ADDRESS}."])
        ),
    )
    if preview:
        seo["noindex"] = True
    response = render(
        request,
        "catalog/service.html",
        {
            "service": service,
            "contact_topic": service.name,
            "photos": photos,
            "category": category,
            "related": related,
            "breadcrumbs": crumbs,
            "seo": seo,
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.service(request, service),
            ],
            **preview_context(service, preview),
        },
    )
    return finish(response, preview)
