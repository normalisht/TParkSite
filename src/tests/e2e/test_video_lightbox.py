"""Просмотр ролика Дзена: рамка 16:9, атрибуты iframe, выгрузка при перелистывании и закрытии (make e2e)."""

import pytest

pytest.importorskip("playwright")

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 844}
CURRENT_IFRAME = '.gslide.current iframe[src^="https://dzen.ru/embed/"]'


def open_video_tab(browser, live_server, viewport=DESKTOP, **context_args):
    """Страница «Видео» с заглушкой вместо Дзена; hits — адреса запросов к Дзену (в т. ч. из iframe)."""
    context = browser.new_context(viewport=viewport, **context_args)
    hits = []

    def stub(route):
        hits.append(route.request.url)
        route.fulfill(body="<html><body>stub</body></html>", content_type="text/html")

    context.route("https://dzen.ru/**", stub)
    page = context.new_page()
    page.goto(live_server.url + "/gallery/video/")
    page.wait_for_load_state("networkidle")
    return page, hits


def test_video_opens_in_16_9_frame_with_allow(live_server, browser, make_video):
    make_video(title="Фрироуп", embed_url="https://dzen.ru/embed/first")
    make_video()
    page, hits = open_video_tab(browser, live_server)
    page.locator('a[aria-label="Видео: Фрироуп"]').click()
    iframe = page.locator(CURRENT_IFRAME)
    iframe.wait_for()
    assert iframe.get_attribute("src") == "https://dzen.ru/embed/first"
    allow = iframe.get_attribute("allow")
    for feature in ("autoplay", "fullscreen", "picture-in-picture", "encrypted-media"):
        assert feature in allow
    assert iframe.get_attribute("allowfullscreen") is not None
    assert iframe.get_attribute("title") == "Фрироуп"
    page.wait_for_timeout(500)
    box = iframe.bounding_box()
    assert abs(box["width"] / box["height"] - 16 / 9) < 0.02
    assert box["width"] <= DESKTOP["width"] - 32 and box["y"] + box["height"] <= DESKTOP["height"]
    description = page.locator(".gslide.current .gslide-description")
    assert description.inner_text().strip() == "Фрироуп"
    assert description.bounding_box()["y"] >= box["y"] + box["height"] - 1
    # Атрибуты стоят с первой загрузки: Дзен запрошен один раз, соседний ролик заранее не грузится.
    assert hits == ["https://dzen.ru/embed/first"]


def test_no_dzen_requests_before_click(live_server, browser, make_video):
    make_video()
    make_video()
    page, hits = open_video_tab(browser, live_server)
    page.wait_for_timeout(300)
    assert hits == []
    assert page.locator("iframe").count() == 0


def test_video_iframe_unloaded_on_next_and_close(live_server, browser, make_video):
    for name in ("one", "two", "three"):
        make_video(title=name, embed_url=f"https://dzen.ru/embed/{name}")
    page, hits = open_video_tab(browser, live_server)
    page.locator('a[aria-label="Видео: one"]').click()
    page.locator(CURRENT_IFRAME).wait_for()

    page.locator(".gnext").click()
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/two"]').wait_for()
    assert page.locator('iframe[src^="https://dzen.ru/"]').count() == 1

    page.locator(".gprev").click()
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/one"]').wait_for()
    assert page.locator('iframe[src^="https://dzen.ru/"]').count() == 1
    assert hits.count("https://dzen.ru/embed/one") == 2  # вернулись — ролик загружен заново

    page.keyboard.press("Escape")
    page.locator(".glightbox-container").wait_for(state="detached")
    assert page.locator("iframe").count() == 0


def test_previous_video_removed_before_slide_animation(live_server, browser, make_video):
    for name in ("one", "two"):
        make_video(title=name, embed_url=f"https://dzen.ru/embed/{name}")
    page, _ = open_video_tab(browser, live_server)
    page.locator('a[aria-label="Видео: one"]').click()
    page.locator(CURRENT_IFRAME).wait_for()
    page.wait_for_timeout(500)
    # Звук прежнего ролика не должен звучать во время перелистывания (~0,5 с): iframe убран в первые 100 мс.
    gone = page.evaluate(
        """() => new Promise((resolve) => {
            document.querySelector(".gnext").click();
            setTimeout(() => resolve(!document.querySelector('iframe[src="https://dzen.ru/embed/one"]')), 100);
        })"""
    )
    assert gone
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/two"]').wait_for()


def test_caption_below_frame_on_phone(live_server, browser, make_video):
    make_video(title="Ролик с длинным названием, которое на телефоне займёт пару строк")
    make_video()
    page, _ = open_video_tab(browser, live_server, viewport=PHONE, has_touch=True)
    page.locator("a.glightbox").first.click()
    iframe = page.locator(CURRENT_IFRAME)
    iframe.wait_for()
    page.wait_for_timeout(500)
    frame = iframe.bounding_box()
    assert abs(frame["width"] / frame["height"] - 16 / 9) < 0.02
    assert frame["width"] <= PHONE["width"] - 32
    description = page.locator(".gslide.current .gslide-description").bounding_box()
    assert description["y"] >= frame["y"] + frame["height"] - 1
    assert description["y"] + description["height"] <= PHONE["height"]


def test_photo_gallery_still_opens_images(live_server, browser, make_image):
    from apps.content.models import GalleryPhoto

    for i in range(2):
        GalleryPhoto.objects.create(image=make_image(), caption=f"Фото {i}")
    page = browser.new_context(viewport=DESKTOP).new_page()
    page.goto(live_server.url + "/gallery/")
    page.wait_for_load_state("networkidle")
    page.locator('a[data-gallery="gallery"]').first.click()
    page.locator(".gslide.current .gslide-image img").wait_for()
    page.locator(".gnext").click()
    page.locator(".gslide.current .gslide-title", has_text="Фото 1").wait_for()


def test_shelf_lists_only_its_videos(live_server, browser, make_video, make_collection):
    from apps.content.models import VideoCollectionItem

    shelf = make_collection("Услуги")
    for order, name in enumerate(("one", "two")):
        VideoCollectionItem.objects.create(
            collection=shelf, video=make_video(title=name, embed_url=f"https://dzen.ru/embed/{name}"), order=order
        )
    make_video(title="three", embed_url="https://dzen.ru/embed/three")
    page, _ = open_video_tab(browser, live_server)
    page.locator(f'[data-video-shelf="{shelf.slug}"] a[aria-label="Видео: two"]').click()
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/two"]').wait_for()
    page.locator(".gnext").click()  # в полке два ролика: «вперёд» возвращает к первому, а не к «three»
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/one"]').wait_for()


WATCH = "https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b"
DZEN_LINK = ".gslide.current .gslide-description a.video-dzen-link"


@pytest.mark.parametrize("viewport", [DESKTOP, PHONE], ids=["desktop", "phone"])
def test_open_on_dzen_link_under_player(live_server, browser, make_video, viewport):
    make_video(title="С адресом", embed_url="https://dzen.ru/embed/one", dzen_url=WATCH)
    make_video(title="Без адреса", embed_url="https://dzen.ru/embed/two")
    page, hits = open_video_tab(browser, live_server, viewport=viewport, has_touch=viewport is PHONE)
    page.locator('a[aria-label="Видео: С адресом"]').click()
    iframe = page.locator(CURRENT_IFRAME)
    iframe.wait_for()
    page.wait_for_timeout(500)
    link = page.locator(DZEN_LINK)
    assert link.inner_text().strip() == "Открыть на Дзене"
    assert (link.get_attribute("href"), link.get_attribute("target"), link.get_attribute("rel")) == (
        WATCH,
        "_blank",
        "noopener",
    )
    frame, box = iframe.bounding_box(), link.bounding_box()
    assert box["y"] >= frame["y"] + frame["height"] - 1 and box["y"] + box["height"] <= viewport["height"]
    assert hits == ["https://dzen.ru/embed/one"]  # ссылку не загружают заранее

    page.locator(".gnext").click()
    page.locator('.gslide.current iframe[src="https://dzen.ru/embed/two"]').wait_for()
    assert page.locator(DZEN_LINK).count() == 0
    assert page.locator(".gslide.current .gslide-title").inner_text().strip() == "Без адреса"
