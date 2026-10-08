from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.seo import absolute_url, make_seo


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


def event_detail(request, slug):
    event = get_object_or_404(Event.objects.visible(), slug=slug)
    settings = SiteSettings.load()
    canonical = request.build_absolute_uri(event.get_absolute_url())
    seo = make_seo(event.title, event.description, absolute_url(request, safe_spec_url(event, "card")))
    structured = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "startDate": event.date.isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": canonical,
        "location": {"@type": "Place", "name": "Т-Парк", "address": settings.address or "Т-Парк"},
        "organizer": {"@type": "Organization", "name": "Т-Парк", "url": request.build_absolute_uri("/")},
    }
    if seo["description"]:
        structured["description"] = seo["description"]
    if seo["image"]:
        structured["image"] = [seo["image"]]
    return render(
        request,
        "content/event.html",
        {
            "event": event,
            "seo": seo,
            "canonical_url": canonical,
            "structured_data": structured,
        },
    )


def about(request):
    return render(
        request,
        "content/about.html",
        {
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
