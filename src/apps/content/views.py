from django.shortcuts import render
from django.utils import timezone

from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.seo import make_seo


def events(request):
    today = timezone.localdate()
    upcoming = list(Event.objects.upcoming(today))
    past = list(Event.objects.past_visible(today))
    nearest = upcoming[0] if upcoming else None
    hero = safe_spec_url(nearest, "card") if nearest else ""
    return render(
        request,
        "content/events.html",
        {
            "events": upcoming + past,
            "nearest": nearest,
            "hero_image": hero,
            "seo": make_seo("Мероприятия", SiteSettings.load().events_intro),
        },
    )


def about(request):
    return render(
        request,
        "content/about.html",
        {
            "employees": list(Employee.objects.all()),
            "partners": list(Partner.objects.all()),
            "seo": make_seo("О нас", SiteSettings.load().about_text),
        },
    )


def reviews(request):
    return render(request, "content/reviews.html", {"reviews": Review.objects.published(), "seo": make_seo("Отзывы")})


def gallery(request):
    return render(request, "content/gallery.html", {"photos": GalleryPhoto.objects.all(), "seo": make_seo("Галерея")})


def contacts(request):
    return render(request, "content/contacts.html", {"seo": make_seo("Контакты", SiteSettings.load().contacts_text)})
