from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.maps import route_links
from apps.core.models import PARK_ADDRESS, SiteSettings
from apps.core.opening_hours import human_opening_hours
from apps.core.seo import absolute_url, make_seo, page_seo

PAST_EVENTS_SHOWN = 6
RELATED_EVENTS = 3


def events(request):
    today = timezone.localdate()
    upcoming = list(Event.objects.upcoming(today))
    return render(
        request,
        "content/events.html",
        {
            "nearest": upcoming[0] if upcoming else None,
            "upcoming": upcoming[1:],
            "past": list(Event.objects.past_visible(today)),
            "past_shown": PAST_EVENTS_SHOWN,
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
    site = SiteSettings.load()
    return render(
        request,
        "content/event.html",
        {
            "event": event,
            "related": list(Event.objects.upcoming().exclude(pk=event.pk)[:RELATED_EVENTS]),
            "route": route_links(site.latitude, site.longitude),
            "seo": seo,
            "breadcrumbs": crumbs,
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.event(request, event, seo),
            ],
        },
    )


GALLERY_STRIP_SIZE = 6


def about(request):
    site = SiteSettings.load()
    seo = page_seo("about")
    seo["image"] = absolute_url(request, safe_spec_url(site, "about_card"))
    return render(
        request,
        "content/about.html",
        {
            "formats": list(site.park_formats.select_related("category")),
            "facts": list(site.founder_facts.all()),
            "safety_page": site.safety_page if site.safety_page and site.safety_page.is_published else None,
            "photos": list(GalleryPhoto.objects.all()[:GALLERY_STRIP_SIZE]),
            "partners": list(Partner.objects.all()),
            "seo": seo,
            "structured_data": [ld.organization(request, with_founder=True)],
        },
    )


def reviews(request):
    return render(
        request,
        "content/reviews.html",
        {
            "reviews": Review.objects.published(),
            "photos": list(GalleryPhoto.objects.all()[:GALLERY_STRIP_SIZE]),
            "seo": page_seo("reviews"),
        },
    )


def gallery(request):
    return render(request, "content/gallery.html", {"photos": GalleryPhoto.objects.all(), "seo": page_seo("gallery")})


def contacts(request):
    site = SiteSettings.load()
    return render(
        request,
        "content/contacts.html",
        {
            "hours": human_opening_hours(site.opening_hours),
            "route": route_links(site.latitude, site.longitude),
            "seo": page_seo("contacts"),
            "structured_data": [ld.organization(request)],
        },
    )
