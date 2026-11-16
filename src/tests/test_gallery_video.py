"""Витрина видео: вкладки галереи, «Видео», страницы подборок, SEO, sitemap, CSP."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.content.models import GalleryPhoto, VideoCollectionItem
from apps.core.images import safe_spec_url

pytestmark = pytest.mark.django_db


def add(collection, *videos):
    for order, video in enumerate(videos):
        VideoCollectionItem.objects.create(collection=collection, video=video, order=order)


def _cards(html):
    return re.findall(r'<a class="glightbox[^>]*>', html)


def test_tabs_hidden_without_videos(client, make_image, make_video):
    GalleryPhoto.objects.create(image=make_image())
    make_video(is_published=False)
    html = client.get("/gallery/").content.decode()
    assert "/gallery/video/" not in html
    assert client.get("/gallery/video/").status_code == 404


def test_tabs_on_both_pages(client, make_video):
    make_video()
    photo_html = client.get("/gallery/").content.decode()
    video_html = client.get("/gallery/video/").content.decode()
    assert re.search(r'<a href="/gallery/" aria-current="page"[^>]*>\s*Фото', photo_html)
    assert re.search(r'<a href="/gallery/video/" class="[^"]*"[^>]*>\s*Видео', photo_html)
    assert re.search(r'<a href="/gallery/video/" aria-current="page"[^>]*>\s*Видео', video_html)
    assert 'href="/gallery/" aria-current' not in video_html


def test_video_card_markup(client, make_video):
    make_video(title="Фрироуп", duration=925, description="Железный век")
    html = client.get("/gallery/video/").content.decode()
    assert 'href="https://dzen.ru/embed/' in html and 'data-type="external"' in html
    assert "15:25" in html and 'aria-label="Видео: Фрироуп"' in html
    assert 'data-gallery="video"' in html and 'data-title="Фрироуп"' in html
    assert "Железный век" in html and 'class="video-play' in html
    assert "<iframe" not in html and html.count("dzen.ru") == html.count('href="https://dzen.ru/embed/')
    assert "glightbox.min.js" in html


def test_card_without_duration_has_no_badge(client, make_video):
    make_video(duration=None)
    assert "video-duration" not in client.get("/gallery/video/").content.decode()


def test_unpublished_video_hidden(client, make_video):
    make_video(title="Открытое")
    make_video(title="Скрытое", is_published=False)
    html = client.get("/gallery/video/").content.decode()
    assert "Открытое" in html and "Скрытое" not in html
    assert len(_cards(html)) == 1


def test_collections_shelf_and_chips(client, make_video, make_collection):
    shown, hidden, empty = (
        make_collection("Услуги"),
        make_collection("Секрет", is_published=False),
        make_collection("Пусто"),
    )
    a, b = make_video(title="Первое"), make_video(title="Второе")
    add(shown, a, b)
    add(hidden, a)
    add(empty, make_video(is_published=False))
    html = client.get("/gallery/video/").content.decode()
    assert html.count(f'href="{shown.get_absolute_url()}"') == 3  # полка + чипы двух роликов
    assert hidden.get_absolute_url() not in html and empty.get_absolute_url() not in html
    assert "Подборки" in html and "Все видео" in html


def test_collection_page_order_and_count(client, make_video, make_collection):
    c = make_collection("Услуги", description="Приключения для гостей")
    a, b = make_video(title="Альфа"), make_video(title="Бета")
    add(c, b, a)
    response = client.get("/gallery/video/uslugi/")
    assert response.status_code == 200
    html = response.content.decode()
    assert html.index('aria-label="Видео: Бета"') < html.index('aria-label="Видео: Альфа"')
    assert "2 видео" in html and "Приключения для гостей" in html
    assert 'href="/gallery/video/"' in html  # «← Все видео»
    assert response.context["seo"]["title"].startswith("Услуги — ")
    crumbs = response.context["breadcrumbs"]
    assert [title for title, _ in crumbs] == ["Главная", "Галерея", "Видео", "Услуги"]


def test_collection_page_other_collections(client, make_video, make_collection):
    c, other = make_collection("Услуги"), make_collection("Эмоции")
    v = make_video()
    add(c, v)
    add(other, v)
    html = client.get(c.get_absolute_url()).content.decode()
    assert "Другие подборки" in html
    assert html.count(f'href="{other.get_absolute_url()}"') == 2  # полка + чип ролика


def test_collection_og_image_falls_back_to_first_video(client, make_video, make_collection, make_image):
    c = make_collection("Услуги")
    video = make_video()
    add(c, video)
    seo = client.get(c.get_absolute_url()).context["seo"]
    assert seo["image"] == f"http://testserver{safe_spec_url(video, 'og')}"
    c.cover = make_image("cover.jpg", size=(200, 200))
    c.save()
    seo = client.get(c.get_absolute_url()).context["seo"]
    assert seo["image"] == f"http://testserver{safe_spec_url(c, 'cover_og')}"
    assert safe_spec_url(c, "cover_og") != safe_spec_url(video, "og")


def test_collection_hides_unpublished(client, make_video, make_collection):
    c = make_collection("Услуги")
    add(c, make_video(is_published=False))
    assert client.get(c.get_absolute_url()).status_code == 404
    make_video()  # вкладка «Видео» есть, а подборки на ней нет
    assert c.get_absolute_url() not in client.get("/sitemap.xml").content.decode()
    hidden = make_collection("Скрытая", is_published=False)
    add(hidden, make_video())
    assert client.get(hidden.get_absolute_url()).status_code == 404


def test_collection_draft_preview_for_staff(admin_client, make_video, make_collection):
    c = make_collection("Черновая", is_published=False)
    add(c, make_video())
    response = admin_client.get(c.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert "Черновик" in html and '<meta name="robots" content="noindex">' in html
    assert "no-cache" in response["Cache-Control"]


def test_collection_slug_change_redirects(client, make_video, make_collection):
    c = make_collection("Услуги")
    add(c, make_video())
    c.slug = "services"
    c.save()
    response = client.get("/gallery/video/uslugi/")
    assert response.status_code == 301 and response["Location"] == "/gallery/video/services/"


def test_video_counter(client, make_video, make_collection):
    videos = [make_video() for _ in range(3)]
    first, second = make_collection("Первая"), make_collection("Вторая")
    add(first, *videos)
    add(second, videos[0])
    assert "3 видео · 2 подборки" in client.get("/gallery/video/").content.decode()


def test_videos_after_page_size_hidden(client, make_video):
    for _ in range(26):
        make_video()
    html = client.get("/gallery/video/").content.decode()
    items = re.findall(r"<li data-video-card[^>]*>", html)
    assert [" hidden" in item for item in items] == [False] * 24 + [True] * 2
    assert len(_cards(html)) == 26  # просмотр листает весь список
    assert "data-gallery-more" in html


def test_collection_list_queries_do_not_grow(client, make_video, make_collection):
    def count_queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/gallery/video/").status_code == 200
        return len(ctx.captured_queries)

    v = make_video()
    add(make_collection("Первая"), v)
    count_queries()  # первый показ ещё и записывает версию страницы для Last-Modified
    small = count_queries()
    for n in range(4):
        add(make_collection(f"Ещё {n}"), make_video(), v)
    count_queries()
    assert count_queries() == small


def test_video_seo_defaults(client, make_video):
    make_video()
    seo = client.get("/gallery/video/").context["seo"]
    assert seo["title"] == "Видео Т-Парка — ролики о парке, Калужская область"
    crumbs = client.get("/gallery/video/").context["breadcrumbs"]
    assert crumbs[1:] == [("Галерея", "/gallery/"), ("Видео", "")]


def test_sitemap_has_video_pages(client, make_video, make_collection):
    assert "/gallery/video/" not in client.get("/sitemap.xml").content.decode()
    c = make_collection("Услуги")
    add(c, make_video())
    xml = client.get("/sitemap.xml").content.decode()
    assert "http://testserver/gallery/video/</loc>" in xml
    assert f"http://testserver{c.get_absolute_url()}</loc>" in xml
    block = xml.split("/gallery/video/</loc>", 1)[1].split("</url>", 1)[0]
    assert "<lastmod>" in block


@pytest.mark.parametrize("path", ["/gallery/video/", "/gallery/video/uslugi/"])
def test_video_pages_etag_304(client, make_video, make_collection, path):
    add(make_collection("Услуги"), make_video())
    first = client.get(path)
    assert first.status_code == 200 and first.has_header("ETag") and first.has_header("Last-Modified")
    assert client.get(path, HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


def test_csp_allows_dzen_frames(settings):
    assert "https://dzen.ru" in settings.SECURE_CSP_REPORT_ONLY["frame-src"]
