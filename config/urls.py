from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core import legacy_redirects
from apps.core.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    # 301 со старых URL Flask-версии
    path("TPark", RedirectView.as_view(url="/", permanent=True)),
    path("about_2", RedirectView.as_view(pattern_name="content:about", permanent=True)),
    path("category", legacy_redirects.category),
    path("category/", legacy_redirects.category),
    path("category/service", legacy_redirects.service),
    path("info", legacy_redirects.info),
    path("", include("apps.catalog.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
