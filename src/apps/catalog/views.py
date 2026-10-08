from django.shortcuts import get_object_or_404, render

from apps.catalog.models import Category, Service
from apps.core.images import safe_spec_url
from apps.core.seo import make_seo


def home(request):
    return render(request, "catalog/home.html")


def _absolute(request, url: str) -> str:
    return request.build_absolute_uri(url) if url else ""


def category_detail(request, slug):
    category = get_object_or_404(Category.objects.published(), slug=slug)
    photos = list(category.photos.all())
    image = safe_spec_url(category, "preview_card") or (safe_spec_url(photos[0], "slide") if photos else "")
    return render(
        request,
        "catalog/category.html",
        {
            "category": category,
            "photos": photos,
            "services": category.published_services(),
            "seo": make_seo(category.name, category.description, _absolute(request, image)),
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
    image = safe_spec_url(photos[0], "slide") if photos else ""
    return render(
        request,
        "catalog/service.html",
        {
            "service": service,
            "photos": photos,
            "category": link.category if link else None,
            "seo": make_seo(service.name, service.short_description or service.description, _absolute(request, image)),
        },
    )
