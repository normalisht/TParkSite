from django.db.models import Prefetch, prefetch_related_objects
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from apps.catalog.models import Service
from apps.content.models import Event, GalleryPhoto, Partner, Review, Video, VideoCollection, VideoCollectionItem
from apps.core import structured_data as ld
from apps.core.images import safe_spec_url
from apps.core.maps import route_links
from apps.core.models import PARK_ADDRESS, SiteSettings
from apps.core.preview import finish, get_for_view, preview_context
from apps.core.seo import absolute_url, make_seo, page_seo

PAST_EVENTS_SHOWN = 6
RELATED_EVENTS = 3
GALLERY_PAGE = 24
SHELF_VIDEOS = 6  # на ПК в полке видно 4 (на планшете 3), остальные — свайпом на телефоне и по «Смотреть все»


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
        "has_videos": Video.objects.published().exists(),
        "breadcrumbs": crumbs,
        "seo": page_seo("gallery"),
        "structured_data": [ld.breadcrumbs(request, crumbs)],
    }
    return render(request, "content/gallery.html", context)


def video_crumbs(*tail: tuple[str, str]) -> list[tuple[str, str]]:
    return [ld.home_crumb(), ("Галерея", reverse("content:gallery")), *tail]


def shown_collections(**exclude) -> list[VideoCollection]:
    """Подборки для полки обложек: обложки-ролики подставлены одним запросом — иначе `cover_video` у каждой подборки
    загружал бы все её ролики."""
    collections = list(VideoCollection.objects.shown().with_first_video().exclude(**exclude))
    covers = Video.objects.in_bulk({c.first_video_id for c in collections if not c.cover})
    for collection in collections:
        if not collection.cover:
            collection.cover_video = covers.get(collection.first_video_id)
    return collections


def collection_videos(videos: list[Video], collections: list[VideoCollection]) -> dict[int, list[Video]]:
    """Ролики каждой подборки из списка `videos`, в порядке подборки, — одним запросом на все подборки."""
    by_pk = {video.pk: video for video in videos}
    result: dict[int, list[Video]] = {c.pk: [] for c in collections}
    pairs = VideoCollectionItem.objects.filter(video__in=videos, collection__in=collections).values_list(
        "collection_id", "video_id"
    )
    for collection_id, video_id in pairs:  # порядок связей — Meta.ordering: order, id
        result[collection_id].append(by_pk[video_id])
    return result


def attach_tags(videos: list[Video], collections: list[VideoCollection], links: dict[int, list[Video]]) -> list[Video]:
    """Теги карточек: подборки из `collections` (в их порядке; у ролика со снятой галочкой — ни одной) и услуги
    с открытой страницей — фиксированным числом запросов на весь список."""
    tags: dict[int, list[VideoCollection]] = {video.pk: [] for video in videos}
    for collection in collections:
        for video in links[collection.pk]:
            tags[video.pk].append(collection)
    for video in videos:
        video.collection_tags = tags[video.pk] if video.show_collection_tags else []
    open_services = Service.objects.with_open_page()
    prefetch_related_objects(videos, Prefetch("services", queryset=open_services, to_attr="service_tags"))
    return videos


def gallery_video(request):
    videos = list(Video.objects.published())
    if not videos:
        raise Http404
    collections = list(VideoCollection.objects.shown())
    links = collection_videos(videos, collections)
    for collection in collections:
        collection.shelf_videos = links[collection.pk][:SHELF_VIDEOS]
    crumbs = video_crumbs(("Видео", ""))
    context = {
        "videos": attach_tags(videos, collections, links),
        "collections": collections,
        "page_size": GALLERY_PAGE,
        "has_videos": True,
        "breadcrumbs": crumbs,
        "seo": page_seo("video"),
        "structured_data": [ld.breadcrumbs(request, crumbs)],
    }
    return render(request, "content/gallery_video.html", context)


def video_collection(request, slug):
    collection, preview = get_for_view(request, VideoCollection.objects.all(), slug=slug)
    videos = collection.shown_videos()
    if not videos:
        raise Http404
    if not collection.cover:
        collection.cover_video = videos[0]
    other_collections = shown_collections(pk=collection.pk)
    image = safe_spec_url(collection, "cover_og") or safe_spec_url(collection.cover_video, "og")
    seo = make_seo(
        collection.title,
        collection.description,
        absolute_url(request, image),
        obj=collection,
        default_description=f"Видео Т-Парка — подборка «{collection.title}». {PARK_ADDRESS}.",
    )
    if preview:
        seo["noindex"] = True
    crumbs = video_crumbs(("Видео", reverse("content:gallery_video")), (collection.title, ""))
    response = render(
        request,
        "content/video_collection.html",
        {
            "collection": collection,
            "videos": attach_tags(videos, other_collections, collection_videos(videos, other_collections)),
            "other_collections": other_collections,
            "page_size": GALLERY_PAGE,
            "breadcrumbs": crumbs,
            "seo": seo,
            "structured_data": [ld.breadcrumbs(request, crumbs)],
            **preview_context(collection, preview),
        },
    )
    return finish(response, preview)


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
