from django.urls import path

from apps.core import views
from apps.core.cookie_consent import cookie_consent

app_name = "core"

urlpatterns = [
    path("cookie-consent/", cookie_consent, name="cookie_consent"),
    path("info/<slug:slug>/", views.info_page, name="info"),
]
