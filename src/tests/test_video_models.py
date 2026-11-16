import pytest
from django.core.exceptions import ValidationError

from apps.content.models import Video, VideoCollection, VideoCollectionItem
from apps.core.models import Redirect

pytestmark = pytest.mark.django_db


def add(collection, *videos):
    for order, video in enumerate(videos):
        VideoCollectionItem.objects.create(collection=collection, video=video, order=order)


def test_collection_shown_counts_only_published(make_video, make_collection):
    c = make_collection("Услуги")
    a, b = make_video(), make_video(is_published=False)
    add(c, a, b)
    [shown] = VideoCollection.objects.shown()
    assert shown.video_count == 1
    assert c.shown_videos() == [a]
    assert c.cover_video == a


def test_collection_without_published_videos_not_shown(make_video, make_collection):
    c = make_collection("Пустая")
    add(c, make_video(is_published=False))
    make_collection("Совсем пустая")
    assert list(VideoCollection.objects.shown()) == []
    assert c.cover_video is None


def test_unpublished_collection_not_shown(make_video, make_collection):
    c = make_collection("Скрытая", is_published=False)
    add(c, make_video())
    assert list(VideoCollection.objects.shown()) == []


def test_video_in_two_collections_keeps_own_order(make_video, make_collection):
    first, second = make_collection("Первая"), make_collection("Вторая")
    a, b = make_video(), make_video()
    add(first, a, b)
    add(second, b, a)
    assert first.shown_videos() == [a, b]
    assert second.shown_videos() == [b, a]
    assert set(a.collections.all()) == {first, second}


def test_collection_slug_from_title_and_redirect_on_change(make_collection, monkeypatch):
    # Маршрут подборки появится вместе с витриной, адрес здесь подставлен.
    monkeypatch.setattr(VideoCollection, "get_absolute_url", lambda self: f"/video/{self.slug}/")
    c = make_collection("Услуги")
    assert c.slug == "uslugi"
    assert c.slug_source() == "Услуги"
    c.slug = "services"
    c.save()
    assert Redirect.objects.get(old_path="/video/uslugi/").new_path == "/video/services/"


def test_duplicate_video_rejected(make_video):
    a = make_video()
    dup = Video(embed_url=a.embed_url, title="Другое")
    with pytest.raises(ValidationError):
        dup.full_clean(exclude=["poster"])


def test_deleting_video_removes_items(make_video, make_collection):
    c = make_collection("Услуги")
    a = make_video()
    add(c, a)
    a.delete()
    assert VideoCollectionItem.objects.count() == 0
    assert VideoCollection.objects.count() == 1


def test_duration_text(make_video):
    assert make_video(duration=125).duration_text == "2:05"
    assert make_video(duration=None).duration_text == ""
