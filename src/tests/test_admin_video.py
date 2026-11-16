import io

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image

from apps.catalog.models import Service
from apps.content.dzen import DzenFetchError, DzenVideo
from apps.content.models import Video, VideoCollectionItem

pytestmark = pytest.mark.django_db

EMBED = "https://dzen.ru/embed/oakZI1TIPAAA"
IFRAME_CODE = (
    '<iframe width="560" height="315" src="https://dzen.ru/embed/oakZI1TIPAAA?from_block=partner&amp;from=zen'
    '&amp;mute=0&amp;autoplay=0&amp;tv=0" allow="autoplay; fullscreen; accelerometer; gyroscope; '
    'picture-in-picture; encrypted-media" frameborder="0" scrolling="no" allowfullscreen></iframe>'
)
THUMB = "https://avatars.dzeninfra.ru/get-zen_doc/123/abc/smart_crop_516x290"
DZEN_VIDEO = DzenVideo(
    title="Т-парк. Фрироуп 3. Железный век",
    description="Это третье видео о фрироупе в Т-Парке.",
    duration=925,
    thumbnail_url=THUMB,
)
DZEN_POSTER_SIZE = (320, 180)


class FakeDzen:
    """Подмена запросов к Дзену: запоминает вызовы, по `error` — падает как недоступный Дзен."""

    def __init__(self):
        self.video = DZEN_VIDEO
        self.error = ""
        self.calls = []
        self.poster_calls = []

    def fetch_video(self, embed_url):
        self.calls.append(embed_url)
        if self.error:
            raise DzenFetchError(self.error)
        return self.video

    def download_poster(self, thumbnail_url):
        self.poster_calls.append(thumbnail_url)
        buffer = io.BytesIO()
        Image.new("RGB", DZEN_POSTER_SIZE, "navy").save(buffer, "JPEG")
        return ContentFile(buffer.getvalue(), name="poster.jpg")


@pytest.fixture
def fake_dzen(monkeypatch):
    fake = FakeDzen()
    monkeypatch.setattr("apps.content.admin.fetch_video", fake.fetch_video)
    monkeypatch.setattr("apps.content.admin.download_poster", fake.download_poster)
    return fake


def video_data(collections=(), **fields):
    data = {
        "embed_url": "",
        "title": "",
        "description": "",
        "is_published": "on",
        "show_collection_tags": "on",
        "collection_items-TOTAL_FORMS": str(len(collections)),
        "collection_items-INITIAL_FORMS": "0",
    }
    for i, collection in enumerate(collections):
        data[f"collection_items-{i}-collection"] = str(collection.pk)
    data.update(fields)
    return data


def post_add(client, collections=(), **fields):
    return client.post(reverse("admin:content_video_add"), video_data(collections, **fields))


def post_change(client, video, **fields):
    current = {"embed_url": video.embed_url, "title": video.title, "description": video.description}
    return client.post(reverse("admin:content_video_change", args=[video.pk]), video_data(**{**current, **fields}))


def form_errors(response):
    return response.context["adminform"].form.errors


def test_add_video_fills_from_dzen(admin_client, fake_dzen):
    response = post_add(admin_client, embed_url=IFRAME_CODE, title="", description="")
    assert response.status_code == 302, form_errors(response)
    v = Video.objects.get()
    assert (v.embed_url, v.title, v.duration) == (EMBED, "Т-парк. Фрироуп 3. Железный век", 925)
    assert v.description.startswith("Это третье") and v.poster
    assert v.poster.width == DZEN_POSTER_SIZE[0]
    assert fake_dzen.calls == [EMBED]
    assert fake_dzen.poster_calls == [THUMB]


def test_add_video_keeps_admin_title_and_poster(admin_client, fake_dzen, make_image):
    response = post_add(
        admin_client, embed_url=IFRAME_CODE, title="Своё название", poster=make_image("own.jpg", size=(64, 48))
    )
    assert response.status_code == 302, form_errors(response)
    v = Video.objects.get()
    assert v.title == "Своё название"
    assert v.description == DZEN_VIDEO.description  # пустое поле заполнено с Дзена
    assert v.duration == 925
    assert v.poster.width == 64
    assert fake_dzen.poster_calls == []


def test_change_video_url_replaces_unchanged_fields(admin_client, fake_dzen, make_video):
    video = make_video(
        embed_url="https://dzen.ru/embed/old", title="Старое", description="Старое описание", duration=10
    )
    old_poster = video.poster.name
    response = post_change(admin_client, video, embed_url=EMBED, description="Своё описание")
    assert response.status_code == 302, form_errors(response)
    video.refresh_from_db()
    assert video.embed_url == EMBED
    assert video.title == DZEN_VIDEO.title
    assert video.description == "Своё описание"  # изменено в этой же отправке — не перезаписываем
    assert video.duration == 925
    assert video.poster.name != old_poster
    assert fake_dzen.poster_calls == [THUMB]


def test_edit_without_url_change_does_not_fetch(admin_client, fake_dzen, make_video):
    video = make_video(duration=100)
    response = post_change(admin_client, video, title="Новое название", description="")
    assert response.status_code == 302, form_errors(response)
    video.refresh_from_db()
    assert (video.title, video.duration) == ("Новое название", 100)
    assert fake_dzen.calls == []


def test_edit_requires_title_and_poster_without_dzen(admin_client, fake_dzen, make_video):
    video = make_video()
    response = post_change(admin_client, video, title="", **{"poster-clear": "on"})
    assert response.status_code == 200
    assert set(form_errors(response)) == {"title", "poster"}
    assert fake_dzen.calls == []


def test_dzen_error_is_form_error(admin_client, fake_dzen):
    fake_dzen.error = "Дзен не ответил."
    response = post_add(admin_client, embed_url=IFRAME_CODE, title="Своё название")
    assert response.status_code == 200
    assert form_errors(response)["embed_url"] == [
        (
            "Не удалось получить данные ролика с Дзена: Дзен не ответил. "
            "Попробуйте позже или заполните название и загрузите обложку вручную."
        )
    ]
    assert Video.objects.count() == 0


def test_dzen_error_allowed_with_manual_title_and_poster(admin_client, fake_dzen, make_image):
    fake_dzen.error = "Дзен не ответил."
    response = post_add(admin_client, embed_url=IFRAME_CODE, title="Своё название", poster=make_image())
    assert response.status_code == 302, form_errors(response)
    v = Video.objects.get()
    assert (v.title, v.duration) == ("Своё название", None)
    assert v.poster


def test_dzen_error_on_url_change_needs_new_title_and_poster(admin_client, fake_dzen, make_video, make_image):
    """Название и обложка прежнего ролика к новому не подходят: без Дзена их надо заменить вручную."""
    video = make_video(embed_url="https://dzen.ru/embed/old", duration=10)
    fake_dzen.error = "Дзен не ответил."
    response = post_change(admin_client, video, embed_url=EMBED)
    assert response.status_code == 200
    assert "embed_url" in form_errors(response)
    response = post_change(admin_client, video, embed_url=EMBED, title="Новое", poster=make_image("new.jpg"))
    assert response.status_code == 302, form_errors(response)
    video.refresh_from_db()
    assert (video.embed_url, video.title, video.duration) == (EMBED, "Новое", None)


def test_fetch_without_thumbnail_requires_poster(admin_client, fake_dzen, make_image):
    fake_dzen.video = DzenVideo(title="Ролик", description="", duration=61, thumbnail_url="")
    response = post_add(admin_client, embed_url=EMBED)
    assert response.status_code == 200
    assert "poster" in form_errors(response)
    assert Video.objects.count() == 0
    response = post_add(admin_client, embed_url=EMBED, poster=make_image())
    assert response.status_code == 302, form_errors(response)
    assert Video.objects.get().title == "Ролик"
    assert fake_dzen.poster_calls == []


def test_poster_download_error_is_poster_error(admin_client, fake_dzen, monkeypatch):
    def broken(_url):
        raise DzenFetchError("Не удалось скачать обложку — загрузите её вручную.")

    monkeypatch.setattr("apps.content.admin.download_poster", broken)
    response = post_add(admin_client, embed_url=EMBED)
    assert response.status_code == 200
    assert form_errors(response)["poster"] == ["Не удалось скачать обложку — загрузите её вручную."]
    assert Video.objects.count() == 0


def test_watch_link_rejected_with_hint(admin_client, fake_dzen):
    response = post_add(admin_client, embed_url="https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b")
    assert response.status_code == 200
    assert "Поделиться" in " ".join(form_errors(response)["embed_url"])
    assert fake_dzen.calls == []


def test_video_added_to_collection_goes_last(admin_client, fake_dzen, make_video, make_collection):
    collection = make_collection()
    for i in (1, 2):
        VideoCollectionItem.objects.create(collection=collection, video=make_video(), order=i)
    response = post_add(admin_client, collections=[collection], embed_url=EMBED)
    assert response.status_code == 302, form_errors(response)
    item = VideoCollectionItem.objects.get(video__embed_url=EMBED)
    assert (item.collection, item.order) == (collection, 3)


def test_collection_inline_reorders_videos(admin_client, make_video, make_collection):
    collection = make_collection("Фрироуп")
    first, second = make_video(), make_video()
    items = [
        VideoCollectionItem.objects.create(collection=collection, video=v, order=i)
        for i, v in enumerate((first, second), 1)
    ]
    data = {
        "title": collection.title,
        "slug": collection.slug,
        "description": "",
        "is_published": "on",
        "seo_title": "",
        "seo_description": "",
        "items-TOTAL_FORMS": "2",
        "items-INITIAL_FORMS": "2",
    }
    for i, (item, order) in enumerate(zip(items, (2, 1), strict=True)):
        data |= {
            f"items-{i}-id": str(item.pk),
            f"items-{i}-collection": str(collection.pk),
            f"items-{i}-video": str(item.video_id),
            f"items-{i}-order": str(order),
        }
    response = admin_client.post(reverse("admin:content_videocollection_change", args=[collection.pk]), data)
    assert response.status_code == 302, response.context["adminform"].form.errors
    assert collection.shown_videos() == [second, first]


def test_collection_inline_new_row_starts_after_last(admin_client, make_video, make_collection):
    collection = make_collection()
    VideoCollectionItem.objects.create(collection=collection, video=make_video(), order=4)
    response = admin_client.get(reverse("admin:content_videocollection_change", args=[collection.pk]))
    formset = response.context["inline_admin_formsets"][0].formset
    assert formset.form.base_fields["order"].initial == 5


def test_move_videos_to_top(admin_client, make_video):
    videos = [make_video(order=i) for i in range(1, 4)]
    response = admin_client.post(
        reverse("admin:content_video_changelist"), {"action": "move_to_top", "_selected_action": [videos[2].pk]}
    )
    assert response.status_code == 302
    assert list(Video.objects.values_list("pk", flat=True)) == [videos[2].pk, videos[0].pk, videos[1].pk]


def test_new_admin_pages_open(admin_client, make_video, make_collection):
    collection = make_collection("Фрироуп")
    video = make_video(title="Железный век", duration=925)
    VideoCollectionItem.objects.create(collection=collection, video=video, order=1)
    html = admin_client.get(reverse("admin:content_video_changelist")).content.decode()
    assert "▶ 15:25" in html
    assert "Фрироуп" in html
    html = admin_client.get(reverse("admin:content_videocollection_changelist")).content.decode()
    assert "Фрироуп" in html
    html = admin_client.get(reverse("admin:content_video_add")).content.decode()
    assert '<textarea name="embed_url"' in html
    assert "Встроить" in html
    for name in ("admin:content_videocollection_add", "admin:content_video_change"):
        args = [video.pk] if name.endswith("change") else []
        assert admin_client.get(reverse(name, args=args)).status_code == 200


def test_help_explains_video(admin_client):
    html = admin_client.get(reverse("admin_help")).content.decode()
    gallery = html.split('<section id="gallery">', 1)[1].split("</section>", 1)[0]
    for phrase in (
        "«Поделиться» → «Встроить»",
        "заполнятся с Дзена",
        "Рекламу и рекомендации",
        "удалите его и здесь",
        "Подборки видео",
        "Показывать подборки на карточке",
        "«Отдельная страница»",
        "своя полка",
    ):
        assert phrase in gallery, phrase
    assert reverse("admin:content_video_changelist") in gallery
    assert reverse("admin:content_videocollection_changelist") in gallery


def test_video_form_saves_services_and_checkbox(admin_client, fake_dzen):
    zipline, banya = Service.objects.create(name="Зиплайн"), Service.objects.create(name="Баня")
    response = post_add(
        admin_client, embed_url=EMBED, services=[str(zipline.pk), str(banya.pk)], show_collection_tags=""
    )
    assert response.status_code == 302, form_errors(response)
    video = Video.objects.get()
    assert set(video.services.all()) == {zipline, banya}
    assert video.show_collection_tags is False
    response = admin_client.get(reverse("admin:content_video_change", args=[video.pk]))
    form = response.context["adminform"].form
    assert "Autocomplete" in type(form.fields["services"].widget.widget).__name__
    assert "show_collection_tags" in form.fields
