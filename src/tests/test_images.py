import pytest
from PIL import Image

from apps.catalog.models import Category, CategoryPhoto
from apps.content.models import GalleryPhoto
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
