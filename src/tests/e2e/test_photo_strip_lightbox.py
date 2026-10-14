"""Полоса «Как это выглядит»: фото открывается на весь экран, без перехода в галерею (make e2e)."""

import pytest

pytest.importorskip("playwright")

from apps.content.models import GalleryPhoto

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize("url", ["/", "/about/", "/reviews/"])
def test_strip_photo_opens_lightbox_and_pages(live_server, browser, make_image, url):
    for i in range(3):
        GalleryPhoto.objects.create(image=make_image(), caption=f"Фото {i}")
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    page.goto(live_server.url + url)
    page.wait_for_load_state("networkidle")
    page.locator('a[data-gallery="strip"]').first.click()
    lightbox = page.locator(".glightbox-container")
    lightbox.wait_for(state="visible")
    assert page.url == live_server.url + url  # остались на странице
    assert lightbox.locator(".gslide-description").first.inner_text().strip() == "Фото 0"
    page.locator(".gnext").click()
    page.locator(".gslide.current .gslide-title", has_text="Фото 1").wait_for()
    page.keyboard.press("Escape")
    lightbox.wait_for(state="detached")


@pytest.mark.parametrize("url", ["/", "/about/", "/reviews/"])
def test_strip_lightbox_has_arrows_on_phone(live_server, browser, make_image, url):
    # Стили GLightbox у полосы подключаются после tailwind.css — правило со стрелками не должно им проигрывать.
    for i in range(3):
        GalleryPhoto.objects.create(image=make_image(), caption=f"Фото {i}")
    page = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True).new_page()
    page.goto(live_server.url + url)
    page.wait_for_load_state("networkidle")
    page.locator('a[data-gallery="strip"]').first.click()
    page.locator(".glightbox-container").wait_for(state="visible")
    for arrow in (".gprev", ".gnext"):
        box = page.locator(arrow).bounding_box()
        assert box and 0 <= box["y"] and box["y"] + box["height"] <= 844, arrow
    page.locator(".gnext").click()
    page.locator(".gslide.current .gslide-title", has_text="Фото 1").wait_for()
