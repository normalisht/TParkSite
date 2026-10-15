"""Предпросмотр черновиков: сотрудник по ссылке «Смотреть на сайте» видит неопубликованную страницу с плашкой
«Черновик»; посетители по-прежнему получают 404.

Пользователь (а значит, сессия) проверяется только для неопубликованной записи: ответы опубликованных страниц
не зависят от того, кто смотрит, — ETag/304 не ломаются."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.cache import add_never_cache_headers


def get_for_view(request, queryset, **lookup):
    """(запись, черновик ли). `queryset` — без фильтра публикации (например, `Service.objects.filter(has_page=True)`);
    запись в корзине — 404 всем."""
    obj = get_object_or_404(queryset.filter(deleted_at__isnull=True), **lookup)
    if obj.is_published:
        return obj, False
    opts = obj._meta
    user = request.user
    if user.is_staff and user.has_perm(f"{opts.app_label}.view_{opts.model_name}"):
        return obj, True
    raise Http404


def preview_context(obj, preview: bool) -> dict:
    if not preview:
        return {"preview": False}
    opts = obj._meta
    return {
        "preview": True,
        "preview_admin_url": reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]),
    }


def finish(response, preview: bool):
    if preview:
        add_never_cache_headers(response)  # черновик не должен осесть ни в каком кеше
    return response
