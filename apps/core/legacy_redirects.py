"""301-редиректы со старых URL Flask-версии (сохраняем позиции в поиске и внешние ссылки)."""

from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from apps.catalog.models import Category, Service
from apps.core.models import InfoPage


def _id_param(request, name: str) -> int:
    value = request.GET.get(name, "")
    if not value.isdigit():
        raise Http404
    return int(value)


def category(request):
    obj = get_object_or_404(Category.objects.published(), pk=_id_param(request, "category_id"))
    return HttpResponsePermanentRedirect(obj.get_absolute_url())


def service(request):
    obj = get_object_or_404(Service.objects.published(), pk=_id_param(request, "service_id"))
    if obj.has_page:
        return HttpResponsePermanentRedirect(obj.get_absolute_url())
    link = (
        obj.category_links.filter(category__is_published=True)
        .select_related("category")
        .order_by("category__order", "category__id")
        .first()
    )
    if link is None:
        raise Http404
    return HttpResponsePermanentRedirect(link.category.get_absolute_url())


def info(request):
    obj = get_object_or_404(InfoPage.objects.published(), pk=_id_param(request, "info_id"))
    return HttpResponsePermanentRedirect(obj.get_absolute_url())
