from django.shortcuts import get_object_or_404, render

from apps.catalog.models import Category, Service
from apps.content.models import Event, GalleryPhoto, Review
from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.maps import route_links
from apps.core.models import PARK_ADDRESS, SiteSettings
from apps.core.opening_hours import human_opening_hours
from apps.core.seo import absolute_url, make_seo, page_seo

HOME_REVIEWS = 8
HOME_EVENTS = 3
HOME_PHOTOS = 6


def home(request):
    site = SiteSettings.load()
    return render(
        request,
        "catalog/home.html",
        {
            "hero": safe_spec_url(site, "about_card"),
            "hours": human_opening_hours(site.opening_hours),
            "route": route_links(site.latitude, site.longitude),
            "events": list(Event.objects.upcoming()[:HOME_EVENTS]) if site.home_show_events else [],
            "photos": list(GalleryPhoto.objects.all()[:HOME_PHOTOS]),
            "reviews": list(Review.objects.published()[:HOME_REVIEWS]),
            "seo": page_seo("home"),
            "structured_data": [ld.organization(request)],
        },
    )


def category_detail(request, slug):
    category = get_object_or_404(Category.objects.published(), slug=slug)
    photos = list(category.photos.all())
    services = category.published_services()
    image = safe_spec_url(category, "preview_card") or (safe_spec_url(photos[0], "slide") if photos else "")
    crumbs = [ld.home_crumb(), (category.name, "")]
    return render(
        request,
        "catalog/category.html",
        {
            "category": category,
            "photos": photos,
            "services": services,
            # Услуги со своей страницей — карточками, остальные — компактным списком.
            "service_cards": [s for s in services if s.has_page],
            "service_rows": [s for s in services if not s.has_page],
            "hero": image,
            "related": category.related_categories(),
            "breadcrumbs": crumbs,
            "seo": make_seo(
                category.name,
                category.description,
                absolute_url(request, image),
                obj=category,
                default_description=f"{category.name} в Т-Парке: услуги и цены. {PARK_ADDRESS}.",
            ),
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.service_list(request, category, services),
            ],
        },
    )


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.published().filter(has_page=True), slug=slug)
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
    image = safe_spec_url(photos[0], "slide") if photos else ""
    related = [s for s in category.published_services() if s.has_page and s.pk != service.pk][:3] if category else []
    return render(
        request,
        "catalog/service.html",
        {
            "service": service,
            "photos": photos,
            "category": category,
            "related": related,
            "breadcrumbs": crumbs,
            "seo": make_seo(
                service.name,
                service.short_description or service.description,
                absolute_url(request, image),
                obj=service,
                default_description=" ".join(
                    filter(None, [f"{service.name} в Т-Парке.", service.price_display, f"{PARK_ADDRESS}."])
                ),
            ),
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.service(request, service),
            ],
        },
    )
