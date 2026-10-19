from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static

from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.models import InfoPage
from apps.core.preview import finish, get_for_view, preview_context
from apps.core.rich_text import parse_info_body
from apps.core.seo import absolute_url, make_seo

TRACKING_PARAMS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "utm_referrer",
    "yclid",
    "ysclid",  # Яндекс сам добавляет его к переходам из выдачи
    "_openstat",
    "from",
    "gclid",
    "fbclid",
]


def healthz(request):
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")


def info_page(request, slug):
    page, preview = get_for_view(request, InfoPage.objects.all(), slug=slug)
    crumbs = [ld.home_crumb(), (page.title, "")]
    seo = make_seo(page.title, page.lead or page.body, absolute_url(request, safe_spec_url(page, "cover_og")), obj=page)
    if preview:
        seo["noindex"] = True
    response = render(
        request,
        "core/info.html",
        {
            "page": page,
            "body": parse_info_body(page.body, questions=page.layout == InfoPage.Layout.FAQ),
            "breadcrumbs": crumbs,
            "seo": seo,
            "structured_data": [ld.breadcrumbs(request, crumbs)],
            **preview_context(page, preview),
        },
    )
    return finish(response, preview)


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /healthz/",
        "",
        # Яндекс: метки рекламы и рассылок не плодят дубли страниц.
        f"Clean-param: {'&'.join(TRACKING_PARAMS)}",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def favicon(request):
    # Браузеры и поисковики запрашивают /favicon.ico без учёта <link rel="icon">
    return redirect(static("img/favicon.ico"), permanent=True)
