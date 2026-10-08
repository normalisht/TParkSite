from django.urls import path

from apps.content import views

app_name = "content"

urlpatterns = [
    path("events/", views.events, name="events"),
    path("about/", views.about, name="about"),
    path("reviews/", views.reviews, name="reviews"),
    path("gallery/", views.gallery, name="gallery"),
    path("contacts/", views.contacts, name="contacts"),
]
