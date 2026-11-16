"""Перенос роликов и подборок с канала Дзена (`data/dzen_channel.json`): data-миграция и команда `import_dzen_channel`.

Модели передаются аргументами: миграция работает с историческими, у которых нет `save()` настоящих моделей, поэтому
slug подборки задаётся здесь. Обложку пережимает и историческое поле: спека imagekit ищется по id
«content:video:poster», а под ним зарегистрирована спека настоящего поля.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.db.models import Max

from apps.content import dzen
from apps.core.slugs import unique_slug

CHANNEL_FILE = Path(__file__).resolve().parent / "data" / "dzen_channel.json"


def load_channel(path: Path = CHANNEL_FILE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class ImportReport:
    videos_created: int = 0
    videos_existing: int = 0
    posters_downloaded: int = 0
    posters_failed: list[str] = field(default_factory=list)
    collections_created: int = 0
    collections_existing: int = 0
    items_created: int = 0
    service_links_created: int = 0
    missing_services: set[str] = field(default_factory=set)

    def summary(self) -> str:
        videos = self.videos_created + self.videos_existing
        collections = self.collections_created + self.collections_existing
        text = (
            f"Дзен: роликов {videos} (новых {self.videos_created}), без обложки {len(self.posters_failed)}, "
            f"подборок {collections} (новых {self.collections_created}), добавлено в подборки {self.items_created}, "
            f"связей с услугами {self.service_links_created}"
        )
        if self.missing_services:
            text += f"; нет услуг: {', '.join(sorted(self.missing_services))}"
        return text


def _next_order(model, **scope) -> int:
    return (model._default_manager.filter(**scope).aggregate(m=Max("order"))["m"] or 0) + 1


def _attach_poster(video, thumbnail_url, download, report, log) -> bool:
    try:
        content = download(thumbnail_url)
    except dzen.DzenFetchError as exc:
        report.posters_failed.append(video.title)
        log(f"Дзен: нет обложки у «{video.title}» — {exc}")
        return False
    video.poster.save("poster.jpg", content, save=False)
    report.posters_downloaded += 1
    return True


def import_channel(*, Video, VideoCollection, VideoCollectionItem, Service, data, download=None, log=print):
    """Создаёт недостающие ролики, подборки и связи; существующее (ролик — по адресу плеера, подборка — по названию)
    не меняет, только докачивает обложку ролику без неё и тогда публикует его. Без обложки ролик — черновик."""
    download = download or dzen.download_poster
    report = ImportReport()
    slugs = {slug for item in data["videos"] for slug in item["services"]}
    services = {s.slug: s for s in Service._default_manager.filter(slug__in=slugs)}
    report.missing_services = slugs - services.keys()

    existing = {
        v.embed_url: v for v in Video._default_manager.filter(embed_url__in=[i["embed_url"] for i in data["videos"]])
    }
    order = _next_order(Video)
    videos = {}
    for item in data["videos"]:
        video = existing.get(item["embed_url"])
        if video is None:
            video = Video(
                embed_url=item["embed_url"],
                title=item["title"],
                description=item["description"],
                duration=item["duration"],
                dzen_url=item["dzen_url"],
                order=order,
                show_collection_tags=True,
            )
            order += 1
            video.is_published = _attach_poster(video, item["thumbnail_url"], download, report, log)
            video.save()
            report.videos_created += 1
        else:
            report.videos_existing += 1
            if not video.poster and _attach_poster(video, item["thumbnail_url"], download, report, log):
                video.is_published = True
                video.save()
        videos[item["embed_url"]] = video
        linked = set(video.services.values_list("slug", flat=True))
        new_links = [services[slug] for slug in item["services"] if slug in services and slug not in linked]
        if new_links:
            video.services.add(*new_links)
            report.service_links_created += len(new_links)

    for entry in data["collections"]:
        collection = VideoCollection._default_manager.filter(title=entry["title"]).order_by("order", "id").first()
        if collection is None:
            collection = VideoCollection(
                title=entry["title"],
                description=entry["description"],
                is_published=True,
                order=_next_order(VideoCollection),
            )
            collection.slug = unique_slug(collection, entry["title"])
            collection.save()
            report.collections_created += 1
        else:
            report.collections_existing += 1
        present = set(collection.items.values_list("video_id", flat=True))
        item_order = _next_order(VideoCollectionItem, collection=collection)
        for embed_url in entry["videos"]:
            video = videos.get(embed_url)
            if video is None or video.pk in present:
                continue
            VideoCollectionItem._default_manager.create(collection=collection, video=video, order=item_order)
            present.add(video.pk)
            item_order += 1
            report.items_created += 1

    log(report.summary())
    return report
