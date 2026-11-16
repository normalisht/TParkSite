import importlib
import io
import re

import pytest
from django.apps import apps as django_apps
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from apps.catalog.models import Service
from apps.content import dzen
from apps.content.dzen import DzenFetchError, validate_embed_url
from apps.content.dzen_import import import_channel, load_channel
from apps.content.models import Video, VideoCollection, VideoCollectionItem

pytestmark = pytest.mark.django_db

MIGRATION = "0018_dzen_channel"
THUMB = "https://avatars.dzeninfra.ru/get-zen_doc/1/pub_x/smart_crop_516x290"


def jpeg(size=(64, 36)) -> ContentFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, "orange").save(buffer, "JPEG")
    return ContentFile(buffer.getvalue(), name="poster.jpg")


class FakeDownload:
    def __init__(self, fail=(), size=(64, 36)):
        self.fail, self.size, self.calls = set(fail), size, []

    def __call__(self, url):
        self.calls.append(url)
        if url in self.fail:
            raise DzenFetchError("Не удалось скачать обложку — загрузите её вручную.")
        return jpeg(self.size)


def video_data(n, services=()):
    return {
        "embed_url": f"https://dzen.ru/embed/ch{n}",
        "title": f"Ролик {n}",
        "description": f"Описание {n}",
        "duration": 60 + n,
        "thumbnail_url": f"{THUMB}{n}",
        "dzen_url": f"https://dzen.ru/video/watch/{n:024x}",
        "services": list(services),
    }


@pytest.fixture
def data():
    return {
        "channel_url": "https://dzen.ru/id/x",
        "videos": [video_data(1, ["batut", "net-takoi"]), video_data(2), video_data(3, ["batut", "sap"])],
        "collections": [
            {
                "title": "Услуги",
                "description": "Про услуги",
                "dzen_url": "https://dzen.ru/suite/a",
                "videos": [
                    "https://dzen.ru/embed/ch3",
                    "https://dzen.ru/embed/ch1",
                ],
            },
            {
                "title": "Всё",
                "description": "",
                "dzen_url": "https://dzen.ru/suite/b",
                "videos": [
                    "https://dzen.ru/embed/ch2",
                ],
            },
        ],
    }


@pytest.fixture
def services():
    return {slug: Service.objects.create(name=slug, slug=slug) for slug in ("batut", "sap")}


def run(data, download, models=None, log=None):
    models = models or {
        "Video": Video,
        "VideoCollection": VideoCollection,
        "VideoCollectionItem": VideoCollectionItem,
        "Service": Service,
    }
    lines = []
    report = import_channel(**models, data=data, download=download, log=log or lines.append)
    return report, lines


def test_import_creates_videos_collections_items_and_service_links(data, services, make_video, make_collection):
    old_video = make_video(order=5)
    make_collection(title="Старая", order=3)
    download = FakeDownload()
    report, lines = run(data, download)

    new = list(Video.objects.exclude(pk=old_video.pk).order_by("order"))
    assert [v.title for v in new] == ["Ролик 1", "Ролик 2", "Ролик 3"]  # как на канале, после прежних
    assert [v.order for v in new] == [6, 7, 8]
    first = new[0]
    assert first.is_published and first.show_collection_tags and first.poster
    assert (first.description, first.duration) == ("Описание 1", 61)
    assert first.dzen_url == "https://dzen.ru/video/watch/" + f"{1:024x}"
    assert set(first.services.values_list("slug", flat=True)) == {"batut"}
    assert set(new[2].services.values_list("slug", flat=True)) == {"batut", "sap"}
    assert download.calls == [f"{THUMB}1", f"{THUMB}2", f"{THUMB}3"]

    services_col = VideoCollection.objects.get(title="Услуги")
    assert services_col.is_published and services_col.slug == "uslugi"
    assert services_col.description == "Про услуги"
    assert [c.title for c in VideoCollection.objects.order_by("order")] == ["Старая", "Услуги", "Всё"]
    assert [c.order for c in VideoCollection.objects.order_by("order")] == [3, 4, 5]
    items = services_col.items.order_by("order")
    assert [(i.video.title, i.order) for i in items] == [("Ролик 3", 1), ("Ролик 1", 2)]

    assert (report.videos_created, report.videos_existing) == (3, 0)
    assert (report.posters_downloaded, report.posters_failed) == (3, [])
    assert (report.collections_created, report.collections_existing) == (2, 0)
    assert (report.items_created, report.service_links_created) == (3, 3)
    assert report.missing_services == {"net-takoi"}
    assert lines[-1] == report.summary()
    assert "роликов 3" in report.summary() and "подборок 2" in report.summary()
    assert "net-takoi" in report.summary()


def test_rerun_creates_nothing_new(data, services):
    run(data, FakeDownload())
    counts = (
        Video.objects.count(),
        VideoCollection.objects.count(),
        VideoCollectionItem.objects.count(),
        Video.services.through.objects.count(),
    )
    download = FakeDownload()
    report, _ = run(data, download)
    assert counts == (
        Video.objects.count(),
        VideoCollection.objects.count(),
        VideoCollectionItem.objects.count(),
        Video.services.through.objects.count(),
    )
    assert download.calls == []  # у всех роликов обложка уже есть
    assert (report.videos_created, report.videos_existing) == (0, 3)
    assert (report.collections_created, report.collections_existing) == (0, 2)
    assert (report.items_created, report.service_links_created) == (0, 0)


def test_rerun_keeps_admin_edits_and_adds_missing_links(data, services):
    run(data, FakeDownload())
    video = Video.objects.get(embed_url="https://dzen.ru/embed/ch1")
    video.title, video.is_published = "Своё название", False
    video.save()
    video.services.clear()
    collection = VideoCollection.objects.get(title="Услуги")
    collection.items.filter(video=video).delete()
    report, _ = run(data, FakeDownload())
    video.refresh_from_db()
    assert video.title == "Своё название" and not video.is_published  # обложка была — не трогаем
    assert set(video.services.values_list("slug", flat=True)) == {"batut"}
    assert report.service_links_created == 1
    item = collection.items.get(video=video)
    assert item.order == 2  # после оставшихся роликов подборки
    assert report.items_created == 1


def test_failed_poster_leaves_draft_and_rerun_publishes(data, services):
    report, lines = run(data, FakeDownload(fail={f"{THUMB}2"}))
    video = Video.objects.get(embed_url="https://dzen.ru/embed/ch2")
    assert not video.is_published and not video.poster
    assert report.posters_failed == ["Ролик 2"]
    assert any("Ролик 2" in line for line in lines[:-1])
    assert "без обложки 1" in report.summary()

    download = FakeDownload()
    report, _ = run(data, download)
    video.refresh_from_db()
    assert video.is_published and video.poster
    assert download.calls == [f"{THUMB}2"]
    assert report.posters_downloaded == 1 and report.posters_failed == []


def test_unexpected_poster_error_propagates_only_as_dzen_error(data, services):
    """download_poster оборачивает сетевые ошибки в DzenFetchError; прочие исключения — баг, их не глотаем."""

    def broken(url):
        raise ValueError("bug")

    with pytest.raises(ValueError):
        run(data, broken)


def test_download_poster_wraps_network_errors(monkeypatch):
    def offline(url):
        raise OSError("нет сети")

    monkeypatch.setattr(dzen, "_download", offline)
    with pytest.raises(DzenFetchError):
        dzen.download_poster(f"{THUMB}1")


def test_historical_models_get_slug_and_processed_poster(data, services):
    """В миграции нет save() моделей: slug задаёт импорт, а обложку пережимает спека настоящего поля (тот же id)."""
    state_apps = MigrationExecutor(connection).loader.project_state(("content", MIGRATION)).apps
    models = {
        "Video": state_apps.get_model("content", "Video"),
        "VideoCollection": state_apps.get_model("content", "VideoCollection"),
        "VideoCollectionItem": state_apps.get_model("content", "VideoCollectionItem"),
        "Service": state_apps.get_model("catalog", "Service"),
    }
    run(data, FakeDownload(size=(2400, 1350)), models=models)
    assert VideoCollection.objects.get(title="Всё").slug == "vsio"
    video = Video.objects.get(embed_url="https://dzen.ru/embed/ch1")
    with video.poster.open() as f, Image.open(f) as image:
        assert image.size == (1920, 1080)
    assert set(video.services.values_list("slug", flat=True)) == {"batut"}


def migration():
    return importlib.import_module(f"apps.content.migrations.{MIGRATION}")


def test_migration_is_noop_without_services(monkeypatch):
    def no_network(url):
        raise AssertionError("миграция не должна ходить в сеть")

    monkeypatch.setattr(dzen, "download_poster", no_network)
    assert not Service.objects.exists()
    migration().import_dzen_channel(django_apps, None)
    assert not Video.objects.exists() and not VideoCollection.objects.exists()


def test_migration_imports_channel_when_catalog_has_services(monkeypatch, capsys):
    Service.objects.create(name="Фрироуп", slug="friroup-nizhniaia-verevochnaia-trassa")
    monkeypatch.setattr(dzen, "download_poster", FakeDownload())
    migration().import_dzen_channel(django_apps, None)
    assert Video.objects.filter(is_published=True).count() == 65
    assert VideoCollection.objects.count() == 8
    assert Service.objects.get().videos.count() == 3
    assert "Дзен: роликов 65" in capsys.readouterr().out


def test_command_imports_channel_file(monkeypatch):
    monkeypatch.setattr(dzen, "download_poster", FakeDownload(fail={load_channel()["videos"][0]["thumbnail_url"]}))
    out = io.StringIO()
    call_command("import_dzen_channel", stdout=out)
    assert Video.objects.count() == 65 and Video.objects.filter(is_published=False).count() == 1
    assert VideoCollection.objects.count() == 8
    assert "Дзен: роликов 65 (новых 65), без обложки 1, подборок 8 (новых 8)" in out.getvalue()


def test_channel_file_is_consistent():
    channel = load_channel()
    videos, collections = channel["videos"], channel["collections"]
    assert (len(videos), len(collections)) == (65, 8)
    embeds = [v["embed_url"] for v in videos]
    assert len(set(embeds)) == len(embeds)
    for video in videos:
        validate_embed_url(video["embed_url"])
        assert re.fullmatch(r"https://dzen\.ru/video/watch/[0-9a-f]{24}", video["dzen_url"]), video["dzen_url"]
        assert video["title"] and video["thumbnail_url"].startswith(f"https://{dzen.IMAGE_HOST}/")
        assert isinstance(video["services"], list)
    for collection in collections:
        assert collection["title"] and collection["videos"]
        assert set(collection["videos"]) <= set(embeds), collection["title"]
        assert len(set(collection["videos"])) == len(collection["videos"])
    assert len({c["title"] for c in collections}) == len(collections)
