from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("category/<slug:slug>/", views.category_detail, name="category"),
    path("service/<slug:slug>/", views.service_detail, name="service"),
]
