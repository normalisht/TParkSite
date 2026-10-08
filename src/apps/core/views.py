from django.db import connection
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static

from apps.core.models import InfoPage
from apps.core.seo import make_seo


def healthz(request):
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")


def info_page(request, slug):
    page = get_object_or_404(InfoPage.objects.published(), slug=slug)
    return render(request, "core/info.html", {"page": page, "seo": make_seo(page.title, page.body)})


def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /admin/", f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def favicon(request):
    # Браузеры и поисковики запрашивают /favicon.ico без учёта <link rel="icon">
    return redirect(static("img/favicon.ico"), permanent=True)
