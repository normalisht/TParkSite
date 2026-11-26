"""Полоса «Как это выглядит»: фото открывается на весь экран, без перехода в галерею (make e2e)."""

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import expect

from apps.catalog.models import Category, CategoryPhoto
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
    lightbox.get_by_role("button", name="Следующее фото", exact=True).click()
    page.locator(".gslide.current .gslide-title", has_text="Фото 1").wait_for()
    page.keyboard.press("Escape")
    lightbox.wait_for(state="detached")


def test_category_photo_slider_and_lightbox_have_russian_controls(live_server, browser, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True)
    for order in range(3):
        CategoryPhoto.objects.create(category=category, image=make_image(), order=order)
    with browser.new_context(reduced_motion="reduce") as context:
        page = context.new_page()
        page.goto(live_server.url + category.get_absolute_url())
        slider = page.locator(".js-slider")
        for name in ("Предыдущее фото", "Следующее фото", "Перейти к фото 2"):
            expect(slider.get_by_role("button", name=name, exact=True)).to_be_visible()

        slider.locator(".swiper-slide-active img").click()
        lightbox = page.get_by_role("dialog")
        expect(lightbox.get_by_role("button", name="Предыдущее фото", exact=True)).to_be_visible()
        lightbox.get_by_role("button", name="Закрыть", exact=True).click()
        expect(lightbox).to_have_count(0)


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
