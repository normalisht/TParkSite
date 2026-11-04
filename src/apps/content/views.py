from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.maps import route_links
from apps.core.models import PARK_ADDRESS, SiteSettings
from apps.core.preview import finish, get_for_view, preview_context
from apps.core.seo import absolute_url, make_seo, page_seo

PAST_EVENTS_SHOWN = 6
RELATED_EVENTS = 3
GALLERY_PAGE = 24


def page_crumbs(title: str) -> list[tuple[str, str]]:
    """Крошки страницы первого уровня: «Главная / <заголовок>»."""
    return [ld.home_crumb(), (title, "")]


def events(request):
    today = timezone.localdate()
    upcoming = list(Event.objects.published().upcoming(today))
    crumbs = page_crumbs("Мероприятия")
    return render(
        request,
        "content/events.html",
        {
            "nearest": upcoming[0] if upcoming else None,
            "upcoming": upcoming[1:],
            "past": list(Event.objects.published().past_visible(today)),
            "past_shown": PAST_EVENTS_SHOWN,
            "breadcrumbs": crumbs,
            "seo": page_seo("events"),
            "structured_data": [
                n
                for n in (ld.organization(request), ld.breadcrumbs(request, crumbs), ld.event_list(request, upcoming))
                if n
            ],
        },
    )


def event_detail(request, slug):
    event, preview = get_for_view(request, Event.objects.all(), slug=slug)
    when = date_format(event.date, "j E Y")
    # Место проведения вне парка: описание не должно утверждать, что событие в Т-Парке (как «Где» и JSON-LD на странице).
    default_description = (
        f"{event.title}, {when} — {event.venue}."
        if event.venue
        else f"{event.title}, {when} — мероприятие в Т-Парке. {PARK_ADDRESS}."
    )
    seo = make_seo(
        event.title,
        event.description,
        absolute_url(request, safe_spec_url(event, "og")),
        obj=event,
        default_description=default_description,
    )
    # Прошедшее без «Показывать после даты»: по прямой ссылке открывается, в поиск не попадает.
    seo["noindex"] = preview or (event.is_past and not event.show_after_date)
    crumbs = [ld.home_crumb(), ("Мероприятия", reverse("content:events")), (event.title, "")]
    site = SiteSettings.load()
    response = render(
        request,
        "content/event.html",
        {
            "event": event,
            "contact_topic": "" if event.is_past else event.title,
            "related": list(Event.objects.published().upcoming().exclude(pk=event.pk)[:RELATED_EVENTS]),
            "route": route_links(site.latitude, site.longitude),
            "seo": seo,
            "breadcrumbs": crumbs,
            "structured_data": [
                ld.organization(request),
                ld.breadcrumbs(request, crumbs),
                ld.event(request, event, seo),
            ],
            **preview_context(event, preview),
        },
    )
    return finish(response, preview)


def about(request):
    site = SiteSettings.load()
    seo = page_seo("about")
    seo["image"] = absolute_url(request, safe_spec_url(site, "about_og"))
    crumbs = page_crumbs("О нас")
    return render(
        request,
        "content/about.html",
        {
            "formats": list(site.park_formats.select_related("category")),
            "facts": list(site.founder_facts.all()),
            "route": route_links(site.latitude, site.longitude),
            "photos": GalleryPhoto.strip_photos("about"),
            "partners": list(Partner.objects.all()),
            "breadcrumbs": crumbs,
            "seo": seo,
            "structured_data": [ld.organization(request, with_founder=True), ld.breadcrumbs(request, crumbs)],
        },
    )


def reviews(request):
    crumbs = page_crumbs("Отзывы")
    return render(
        request,
        "content/reviews.html",
        {
            "reviews": Review.objects.published(),
            "photos": GalleryPhoto.strip_photos("reviews"),
            "breadcrumbs": crumbs,
            "seo": page_seo("reviews"),
            "structured_data": [ld.breadcrumbs(request, crumbs)],
        },
    )


def gallery(request):
    photos = list(GalleryPhoto.objects.all())
    crumbs = page_crumbs("Галерея")
    context = {
        "photos": photos,
        "page_size": GALLERY_PAGE,
        "breadcrumbs": crumbs,
        "seo": page_seo("gallery"),
        "structured_data": [ld.breadcrumbs(request, crumbs)],
    }
    return render(request, "content/gallery.html", context)


def contacts(request):
    site = SiteSettings.load()
    crumbs = page_crumbs("Контакты")
    return render(
        request,
        "content/contacts.html",
        {
            "route": route_links(site.latitude, site.longitude),
            "breadcrumbs": crumbs,
            "seo": page_seo("contacts"),
            "structured_data": [ld.organization(request), ld.breadcrumbs(request, crumbs)],
        },
    )
