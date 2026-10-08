from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("info/<slug:slug>/", views.info_page, name="info"),
]
