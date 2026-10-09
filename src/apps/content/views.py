from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.models import PARK_ADDRESS
from apps.core.seo import absolute_url, make_seo, page_seo


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
            "seo": page_seo("events"),
        },
    )


def event_detail(request, slug):
    event = get_object_or_404(Event.objects.visible(), slug=slug)
    seo = make_seo(
        event.title,
        event.description,
        absolute_url(request, safe_spec_url(event, "card")),
        obj=event,
        default_description=f"{event.title}, {date_format(event.date, 'j E Y')} — мероприятие в Т-Парке. {PARK_ADDRESS}.",
    )
    crumbs = [ld.home_crumb(), ("Мероприятия", reverse("content:events")), (event.title, "")]
    return render(
        request,
        "content/event.html",
        {
            "event": event,
            "seo": seo,
            "breadcrumbs": crumbs,
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.event(request, event, seo),
            ],
        },
    )


def about(request):
    return render(
        request,
        "content/about.html",
        {
            "partners": list(Partner.objects.all()),
            "seo": page_seo("about"),
        },
    )


def reviews(request):
    return render(request, "content/reviews.html", {"reviews": Review.objects.published(), "seo": page_seo("reviews")})


def gallery(request):
    return render(request, "content/gallery.html", {"photos": GalleryPhoto.objects.all(), "seo": page_seo("gallery")})


def contacts(request):
    return render(
        request,
        "content/contacts.html",
        {
            "seo": page_seo("contacts"),
            "structured_data": [ld.organization(request)],
        },
    )
