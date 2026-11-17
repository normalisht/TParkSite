"""Витрина видео: вкладки галереи, «Видео», страницы подборок, SEO, sitemap, CSP."""

import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import Category, CategoryService, Service
from apps.content.models import GalleryPhoto, VideoCollectionItem
from apps.core.images import safe_spec_url

pytestmark = pytest.mark.django_db


def add(collection, *videos):
    for order, video in enumerate(videos):
        VideoCollectionItem.objects.create(collection=collection, video=video, order=order)


def _cards(html):
    return re.findall(r'<a class="glightbox[^>]*>', html)


def tags(html, title):
    """Теги карточки ролика в сетке: [(адрес, текст)]. Сетка идёт после полок — берём последнее вхождение."""
    card = html.rsplit(f'aria-label="Видео: {title}"', 1)[1].split("<li data-video-card", 1)[0]
    found = re.search(r"<ul data-video-tags[^>]*>(.*?)</ul>", card, re.DOTALL)
    return re.findall(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', found.group(1)) if found else []


def make_service(name, *, category_published=True, **kwargs):
    kwargs.setdefault("has_page", True)
    service = Service.objects.create(name=name, **kwargs)
    if category_published is not None:
        category = Category.objects.create(name=f"Категория {name}", is_published=category_published)
        CategoryService.objects.create(category=category, service=service)
    return service


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
    assert "<iframe" not in html and html.count("dzen.ru/embed") == html.count('href="https://dzen.ru/embed/')
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
    assert html.count(f'href="{shown.get_absolute_url()}"') == 4  # заголовок полки, «Смотреть все», теги двух роликов
    assert hidden.get_absolute_url() not in html and empty.get_absolute_url() not in html
    assert "Смотреть все" in html and "Все видео" in html


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
    html = client.get("/gallery/video/").content.decode()
    assert "3 видео · 2 подборки" in re.sub(r"<[^>]+>", "", html)
    # Счётчики не кликабельны — зелёные, как на странице подборки, а не оранжевые.
    lead = re.search(r'<p class="page-lead">(.*?)</p>', html, re.DOTALL).group(1)
    counters = re.findall(r'<span class="[^"]*\btext-pine-800\b[^"]*">([^<]+)</span>', lead)
    assert counters == ["3 видео", "2 подборки"] and "brand" not in lead


def test_photo_counter_is_green(client, make_image):
    GalleryPhoto.objects.create(image=make_image())
    html = client.get("/gallery/").content.decode()
    lead = re.search(r'<p class="page-lead">(.*?)</p>', html, re.DOTALL).group(1)
    assert '<span class="font-semibold text-pine-800">1 фотография</span>' in lead and "brand" not in lead


def test_collection_page_counter_is_green(client, make_video, make_collection):
    c = make_collection("Услуги")
    add(c, make_video(), make_video())
    html = client.get(c.get_absolute_url()).content.decode()
    assert '<span class="font-semibold text-pine-800">2 видео</span>' in html


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


def _collection_lastmod(client, collection) -> str:
    xml = client.get("/sitemap.xml").content.decode()
    block = xml.split(f"{collection.get_absolute_url()}</loc>", 1)[1].split("</url>", 1)[0]
    return block.split("<lastmod>", 1)[1].split("</lastmod>", 1)[0]


def _set_updated(*objects, day="2020-01-01"):
    for obj in objects:
        type(obj).objects.filter(pk=obj.pk).update(updated_at=f"{day}T12:00:00+00:00")


def test_collection_lastmod_follows_its_videos(client, make_video, make_collection):
    c = make_collection("Услуги")
    first, second, outside = make_video(), make_video(), make_video()
    add(c, first, second)
    _set_updated(c, first, second, outside)
    assert _collection_lastmod(client, c) == "2020-01-01"
    _set_updated(outside, day="2025-05-05")  # чужой ролик дату подборки не двигает
    assert _collection_lastmod(client, c) == "2020-01-01"
    _set_updated(second, day="2024-04-04")
    assert _collection_lastmod(client, c) == "2024-04-04"
    second.is_published = False  # снятый с публикации ролик пропал со страницы подборки
    second.save()
    assert _collection_lastmod(client, c) > "2024-04-04"


def test_collection_lastmod_follows_added_and_removed_videos(client, make_video, make_collection):
    c = make_collection("Услуги")
    kept, added = make_video(), make_video()
    add(c, kept)
    _set_updated(c, kept, added)
    VideoCollectionItem.objects.create(collection=c, video=added, order=1)
    assert _collection_lastmod(client, c) > "2020-01-01"
    _set_updated(c)
    c.items.get(video=added).delete()  # так удаляет inline админки
    assert _collection_lastmod(client, c) > "2020-01-01"
    VideoCollectionItem.objects.create(collection=c, video=added, order=1)
    _set_updated(c)
    added.delete()  # связь удаляется каскадом
    assert _collection_lastmod(client, c) > "2020-01-01"


def test_collection_sitemap_queries_do_not_grow(client, make_video, make_collection):
    def count_queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/sitemap.xml").status_code == 200
        return len(ctx.captured_queries)

    add(make_collection("Первая"), make_video())
    count_queries()  # первый показ ещё и записывает версию страницы для Last-Modified
    small = count_queries()
    for n in range(3):
        add(make_collection(f"Ещё {n}"), make_video(), make_video())
    count_queries()
    assert count_queries() == small


@pytest.mark.parametrize("path", ["/gallery/video/", "/gallery/video/uslugi/"])
def test_video_pages_etag_304(client, make_video, make_collection, path):
    add(make_collection("Услуги"), make_video())
    first = client.get(path)
    assert first.status_code == 200 and first.has_header("ETag") and first.has_header("Last-Modified")
    assert client.get(path, HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


def test_csp_allows_dzen_frames(settings):
    assert "https://dzen.ru" in settings.SECURE_CSP_REPORT_ONLY["frame-src"]


def test_shelves_show_collections_in_order(client, make_video, make_collection):
    first = make_collection("Услуги", description="Чем заняться в парке")
    second = make_collection("Эмоции")
    videos = [make_video(title=f"Ролик {n}") for n in range(8)]
    add(first, *reversed(videos))
    add(second, videos[0])
    html = client.get("/gallery/video/").content.decode()
    shelves = re.findall(r'<section data-video-shelf="([^"]+)"(.*?)</section>', html, re.DOTALL)
    assert [slug for slug, _ in shelves] == [first.slug, second.slug]
    body = shelves[0][1]
    assert "Чем заняться в парке" in body and "Смотреть все" in body
    # Заголовок полки — ссылка на подборку, без числа роликов.
    heading = re.search(r"<h2[^>]*>(.*?)</h2>", body, re.DOTALL).group(1)
    assert re.fullmatch(rf'<a href="{first.get_absolute_url()}"[^>]*>Услуги</a>', heading.strip())
    titles = re.findall(r'aria-label="Видео: ([^"]+)"', body)
    assert titles == [f"Ролик {n}" for n in range(7, 1, -1)]  # первые 6 в порядке подборки
    assert body.count(f'data-gallery="shelf-{first.slug}"') == 6
    assert re.findall(r'aria-label="Видео: ([^"]+)"', shelves[1][1]) == ["Ролик 0"]


def test_collection_tags_hidden_when_unchecked(client, make_video, make_collection):
    c, other = make_collection("Услуги"), make_collection("Эмоции")
    shown, hidden = make_video(title="Альфа"), make_video(title="Бета", show_collection_tags=False)
    add(c, shown, hidden)
    add(other, hidden)
    html = client.get("/gallery/video/").content.decode()
    assert tags(html, "Альфа") == [(c.get_absolute_url(), "Услуги")]
    assert tags(html, "Бета") == []
    assert "data-video-tags" not in html.rsplit('aria-label="Видео: Бета"', 1)[1].split("<li data-video-card", 1)[0]
    assert tags(client.get(other.get_absolute_url()).content.decode(), "Бета") == []


def test_collection_page_excludes_current_collection_tag(client, make_video, make_collection):
    c, other = make_collection("Услуги"), make_collection("Эмоции")
    video = make_video(title="Альфа")
    add(c, video)
    add(other, video)
    assert tags(client.get(c.get_absolute_url()).content.decode(), "Альфа") == [(other.get_absolute_url(), "Эмоции")]


def test_service_tags_link_to_service_pages(client, make_video, make_collection):
    c = make_collection("Услуги")
    video = make_video(title="Альфа")
    add(c, video)
    zipline, banya = make_service("Зиплайн"), make_service("Баня")
    video.services.add(zipline, banya)
    html = client.get("/gallery/video/").content.decode()
    assert tags(html, "Альфа") == [
        (c.get_absolute_url(), "Услуги"),
        (banya.get_absolute_url(), "Баня"),
        (zipline.get_absolute_url(), "Зиплайн"),
    ]
    assert client.get(banya.get_absolute_url()).status_code == 200


def test_unpublished_or_pageless_service_tag_hidden(client, make_video):
    video = make_video(title="Альфа")
    video.services.add(
        make_service("Открытая"),
        make_service("Снятая", is_published=False),
        make_service("Без страницы", has_page=False),
        make_service("В черновой категории", category_published=False),
        make_service("Без категории", category_published=None),
    )
    html = client.get("/gallery/video/").content.decode()
    assert [text for _, text in tags(html, "Альфа")] == ["Открытая"]


def test_service_tags_shown_when_collection_tags_off(client, make_video, make_collection):
    c = make_collection("Услуги")
    video = make_video(title="Альфа", show_collection_tags=False)
    add(c, video)
    service = make_service("Зиплайн")
    video.services.add(service)
    for path in ("/gallery/video/", c.get_absolute_url()):
        assert tags(client.get(path).content.decode(), "Альфа") == [(service.get_absolute_url(), "Зиплайн")]


@pytest.mark.parametrize("path", ["/gallery/video/", "/gallery/video/pervaia/"])
def test_video_tab_query_count_constant(client, make_video, make_collection, path):
    def count_queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(path).status_code == 200
        return len(ctx.captured_queries)

    v = make_video()
    v.services.add(make_service("Зиплайн"))
    first = make_collection("Первая")
    add(first, v)
    add(make_collection("Вторая"), v)
    count_queries()  # первый показ ещё и записывает версию страницы для Last-Modified
    small = count_queries()
    for n in range(4):
        extra = make_video()
        extra.services.add(make_service(f"Услуга {n}"), make_service(f"Ещё услуга {n}"))
        add(make_collection(f"Ещё {n}"), extra, v)
        VideoCollectionItem.objects.create(collection=first, video=extra, order=n + 1)
    count_queries()
    assert count_queries() == small


def test_video_tab_image_loading(client, make_video, make_collection):
    """Полка первой подборки — первый экран: её первая обложка — LCP; ниже сгиба — lazy."""
    first, second = make_collection("Первая"), make_collection("Вторая")
    videos = [make_video(title=f"Ролик {n}") for n in range(6)]
    add(first, *videos)
    add(second, *videos)
    html = client.get("/gallery/video/").content.decode()
    imgs = re.findall(r"<img [^>]*>", html.split('data-video-shelf="', 1)[1])
    assert html.count('fetchpriority="high"') == 1 and 'fetchpriority="high"' in imgs[0]
    assert ['loading="lazy"' in img for img in imgs[:6]] == [False] * 4 + [True] * 2
    assert all('loading="lazy"' in img for img in imgs[6:])  # вторая полка и «Все видео»


def test_collection_page_image_loading(client, make_video, make_collection):
    c, other = make_collection("Первая"), make_collection("Вторая")
    videos = [make_video(title=f"Ролик {n}") for n in range(5)]
    add(c, *videos)
    add(other, videos[0])
    html = client.get(c.get_absolute_url()).content.decode()
    grid, bottom = html.split("<li data-video-card", 1)[1].split("Другие подборки", 1)
    imgs = re.findall(r"<img [^>]*>", grid)
    assert html.count('fetchpriority="high"') == 1 and 'fetchpriority="high"' in imgs[0]
    assert ['loading="lazy"' in img for img in imgs] == [False] * 3 + [True] * 2
    assert all('loading="lazy"' in img for img in re.findall(r"<img [^>]*>", bottom))


def test_collection_counter_not_link_colored(client, make_video, make_collection):
    c = make_collection("Первая")
    add(c, make_video())
    html = client.get(c.get_absolute_url()).content.decode()
    counter = re.search(r'<span class="([^"]*)">1 видео</span>', html)
    assert counter and "brand" not in counter.group(1)


@pytest.mark.parametrize("path", ["/gallery/video/", "/gallery/video/pervaia/"])
def test_design_switch_removed(client, make_video, make_collection, settings, path):
    settings.DEBUG = True
    add(make_collection("Первая"), make_video(), make_video())
    add(make_collection("Вторая"), make_video())
    plain = client.get(path).content.decode()
    assert client.get(f"{path}?card=2&collections=1").content.decode() == plain
    assert "?card=" not in plain and "collections=" not in plain


CHANNEL = "https://dzen.ru/t_park"


def channel_links(html):
    return re.findall(r"<a [^>]*data-dzen-channel[^>]*>.*?</a>", html, re.DOTALL)


@pytest.mark.parametrize("path", ["/gallery/video/", "/gallery/video/pervaia/"])
def test_channel_button_from_settings(client, make_video, make_collection, path):
    from apps.core.models import SiteSettings

    add(make_collection("Первая"), make_video())
    site = SiteSettings.load()
    site.dzen_url = CHANNEL
    site.save()
    [link] = channel_links(client.get(path).content.decode())
    assert f'href="{CHANNEL}"' in link and 'target="_blank"' in link and 'rel="noopener"' in link
    assert "img/social/dzen" in link and ">Дзен</a>" in link
    assert "btn btn-ghost" in link
    site.dzen_url = ""
    site.save()
    assert channel_links(client.get(path).content.decode()) == []


def test_card_passes_dzen_url_to_lightbox(client, make_video):
    make_video(title="С адресом", dzen_url="https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b")
    make_video(title="Без адреса")
    cards = {
        re.search(r'data-title="([^"]*)"', c).group(1): c
        for c in _cards(client.get("/gallery/video/").content.decode())
    }
    assert 'data-dzen-url="https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b"' in cards["С адресом"]
    assert 'data-dzen-label="Открыть на Дзене"' in cards["С адресом"]
    assert "data-dzen" not in cards["Без адреса"]


def test_dzen_label_with_brand_keeps_attribute(client, make_video):
    """В тексте «Т-Парк» nobr добавил бы <span class="…">: в атрибуте его кавычки обрывали бы значение."""
    from apps.texts.models import SiteText

    SiteText.objects.filter(key="gallery.open_on_dzen").update(text="Смотреть на Дзене Т-Парка")
    make_video(title="С адресом", dzen_url="https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b")
    [card] = _cards(client.get("/gallery/video/").content.decode())
    assert 'data-dzen-label="Смотреть на Дзене Т-Парка" aria-label="Видео: С адресом"' in card


def service_videos_block(html):
    found = re.search(r"<section data-service-videos.*?</section>", html, re.DOTALL)
    return found.group(0) if found else ""


def test_service_page_shows_its_videos(client, make_video):
    service = make_service("Зиплайн", description="<p>Описание услуги</p>")
    other = make_service("Баня")
    videos = [make_video(title=f"Ролик {n}") for n in range(5)]
    hidden = make_video(title="Черновик", is_published=False)
    for video in [*videos[1:], hidden]:
        video.services.add(service)
    videos[0].services.add(other)
    html = client.get(service.get_absolute_url()).content.decode()
    block = service_videos_block(html)
    titles = re.findall(r'data-title="([^"]*)"', block)
    assert titles == ["Ролик 1", "Ролик 2", "Ролик 3"]  # до трёх, в порядке роликов, без черновика и чужих
    assert re.search(r"<h2[^>]*>\s*Видео\s*</h2>", block)
    assert re.search(r'<a href="/gallery/video/"[^>]*>\s*Все видео', block)
    assert 'data-gallery="service"' in block and "glightbox.min.js" in html
    imgs = re.findall(r"<img [^>]*>", block)
    assert imgs and all('loading="lazy"' in img for img in imgs) and 'fetchpriority="high"' not in block
    assert html.index("Описание услуги") < html.index("<section data-service-videos")


def test_service_videos_before_related(client, make_video):
    service = make_service("Зиплайн")
    category = service.category_links.get().category
    sibling = make_service("Скалодром", category_published=None)
    CategoryService.objects.create(category=category, service=sibling)
    make_video().services.add(service)
    html = client.get(service.get_absolute_url()).content.decode()
    assert "Ещё в категории" in html
    assert html.index("<section data-service-videos") < html.index("Ещё в категории")


def test_service_page_without_videos_has_no_block(client, make_video):
    service = make_service("Зиплайн")
    make_video(is_published=False).services.add(service)
    make_video()  # опубликованный, но не этой услуги
    assert service_videos_block(client.get(service.get_absolute_url()).content.decode()) == ""


def test_service_page_video_queries_do_not_grow(client, make_video):
    def count_queries():
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(service.get_absolute_url()).status_code == 200
        return len(ctx.captured_queries)

    service = make_service("Зиплайн")
    make_video().services.add(service)
    count_queries()  # первый показ ещё и записывает версию страницы для Last-Modified
    small = count_queries()
    for _ in range(4):
        make_video(duration=60, dzen_url="https://dzen.ru/video/watch/" + "a" * 24).services.add(service)
    count_queries()
    assert count_queries() == small
