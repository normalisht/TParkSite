import os
import time

import pytest
from django.core.management import call_command
from django.template import Context, Template
from PIL import Image

from apps.catalog.models import Category, CategoryPhoto
from apps.content.models import GalleryPhoto
from apps.core import images
from apps.core.images import lightbox_url, picture_html
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


def _open(spec):
    return Image.open(spec.path)


def test_slide_is_cut_to_16_9_so_srcset_widths_are_true(make_image):
    photo = CategoryPhoto.objects.create(
        category=Category.objects.create(name="Сплавы"), image=make_image(size=(1200, 900))
    )
    assert _open(photo.slide).size == (1600, 900)
    assert _open(photo.slide_small).size == (800, 450)
    assert _open(photo.slide_avif).format == "AVIF"


def test_gallery_photo_specs(make_image):
    photo = GalleryPhoto.objects.create(image=make_image(size=(1200, 800)))
    assert (_open(photo.thumb).format, _open(photo.thumb).size) == ("WEBP", (600, 600))
    assert (_open(photo.thumb_small_avif).format, _open(photo.thumb_small_avif).size) == ("AVIF", (400, 400))
    assert (_open(photo.full).format, _open(photo.full).size) == ("WEBP", (1200, 800))  # без увеличения


def test_og_images_are_jpeg_1200x630(make_image):
    site = SiteSettings.load()
    site.og_image = make_image(size=(1300, 700))
    site.save()
    assert (_open(site.og_card).format, _open(site.og_card).size) == ("JPEG", (1200, 630))
    category = Category.objects.create(name="Байдарки", preview=make_image(size=(1080, 720)))
    assert _open(category.og).format == "JPEG"


class _Spec:
    def __init__(self, url):
        self.url = url


class Photo:
    card_small = _Spec("/m/card_small.webp")
    card = _Spec("/m/card.webp")
    card_small_avif = _Spec("/m/card_small.avif")
    card_avif = _Spec("/m/card.avif")
    row = _Spec("/m/row.webp")
    row_avif = _Spec("/m/row.avif")


class NoAvif:
    logo = _Spec("/m/logo.webp")


class BrokenAvif:
    card = _Spec("/m/card.webp")

    @property
    def card_avif(self):
        raise OSError("нет кодировщика AVIF")


def test_picture_with_srcset():
    html = picture_html(Photo(), "card_small 640w, card 800w", sizes="50vw", alt="", width=800, loading="lazy")
    assert html == (
        '<picture><source type="image/avif" srcset="/m/card_small.avif 640w, /m/card.avif 800w" sizes="50vw">'
        '<img src="/m/card.webp" srcset="/m/card_small.webp 640w, /m/card.webp 800w" sizes="50vw"'
        ' alt="" width="800" loading="lazy"></picture>'
    )


def test_picture_single_spec_has_no_sizes():
    assert picture_html(Photo(), "card", alt="x") == (
        '<picture><source type="image/avif" srcset="/m/card.avif"><img src="/m/card.webp" alt="x"></picture>'
    )


def test_picture_art_direction():
    html = picture_html(Photo(), "row", wide="card", media="(min-width: 640px)", alt="")
    assert html == (
        '<picture><source media="(min-width: 640px)" type="image/avif" srcset="/m/card.avif">'
        '<source media="(min-width: 640px)" type="image/webp" srcset="/m/card.webp">'
        '<source type="image/avif" srcset="/m/row.avif"><img src="/m/row.webp" alt=""></picture>'
    )


def test_picture_without_avif_twin_is_plain_img():
    assert picture_html(NoAvif(), "logo", alt="Партнёр") == '<img src="/m/logo.webp" alt="Партнёр">'


def test_picture_survives_broken_avif():
    assert picture_html(BrokenAvif(), "card", alt="") == '<img src="/m/card.webp" alt="">'


def test_picture_empty_without_source():
    assert picture_html(None, "card") == ""
    assert picture_html(object(), "card") == ""


def test_picture_drops_empty_attrs_but_keeps_alt_and_escapes():
    html = picture_html(NoAvif(), "logo", alt='«Т-Парк» <b>"', loading="", fetchpriority="high")
    assert html == '<img src="/m/logo.webp" alt="«Т-Парк» &lt;b&gt;&quot;" fetchpriority="high">'


def test_picture_rejects_mixed_srcset():
    with pytest.raises(ValueError):
        picture_html(Photo(), "card_small 640w, card")


def test_picture_tag_as_variable():
    tag = '{% load site_tags %}{% picture obj "card" alt="" as pic %}{% if pic %}[{{ pic }}]{% else %}нет{% endif %}'
    html = Template(tag).render(Context({"obj": Photo()}))
    assert html.startswith("[<picture>") and html.endswith("</picture>]")
    assert Template(tag).render(Context({"obj": None})) == "нет"


def test_lightbox_url_prefers_full_spec(make_image):
    photo = GalleryPhoto.objects.create(image=make_image())
    assert lightbox_url(photo) == photo.full.url and photo.full.url.endswith(".webp")


def test_thumbnails_generated_after_commit(monkeypatch, django_capture_on_commit_callbacks, make_image):
    monkeypatch.setattr(images, "run_in_background", lambda fn: fn())
    with django_capture_on_commit_callbacks(execute=True):
        photo = GalleryPhoto.objects.create(image=make_image())
    storage = photo.image.storage
    assert all(
        storage.exists(getattr(photo, name).name) for name in ("thumb", "thumb_avif", "thumb_small_avif", "full")
    )


def test_missing_thumbnail_still_generated_on_view(make_image):
    photo = GalleryPhoto.objects.create(image=make_image())  # on_commit в тесте не выполняется
    storage = photo.image.storage
    assert not storage.exists(photo.thumb_avif.name)
    assert photo.thumb_avif.url and storage.exists(photo.thumb_avif.name)


def test_prune_image_cache(make_image, media_root):
    photo = GalleryPhoto.objects.create(image=make_image())
    kept = media_root / photo.thumb.url.removeprefix("/media/")  # url создаёт файл
    stale = media_root / "CACHE/images/gallery/old/stale.webp"
    fresh = media_root / "CACHE/images/gallery/old/fresh.webp"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"x")
    fresh.write_bytes(b"x")
    two_hours_ago = time.time() - 2 * 3600
    os.utime(stale, (two_hours_ago, two_hours_ago))
    os.utime(kept, (two_hours_ago, two_hours_ago))

    call_command("prune_image_cache", "--dry-run")
    assert stale.exists()

    call_command("prune_image_cache")
    assert not stale.exists() and fresh.exists() and kept.exists()
