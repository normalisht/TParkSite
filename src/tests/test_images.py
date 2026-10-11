import os
import re
import time

import pytest
from django.core.management import call_command
from django.template import Context, Template
from PIL import Image

from apps.catalog.models import Category, CategoryPhoto, Service, ServicePhoto
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


def test_lightbox_webp_is_lighter_than_jpeg_originals(make_image):
    # Оригиналы галереи уже сжаты JPEG: при WebP q80 каждое шестое фото выходило тяжелее оригинала, при q75 — ни одно.
    # method=6 не нужен: вдвое дольше кодирует (дольше прогрев после деплоя) ради 3 % размера.
    photo = GalleryPhoto.objects.create(image=make_image())
    assert photo.full.generator.options == {"quality": 75}


def test_failed_thumbnail_is_not_remembered_as_ready(make_image, media_root):
    # Ошибка генерации не должна запоминаться: на втором показе — снова заглушка, а не URL несуществующего файла.
    photo = GalleryPhoto.objects.create(image=make_image())
    (media_root / photo.image.name).unlink()
    assert images.safe_spec_url(photo, "thumb") == ""
    assert images.safe_spec_url(photo, "thumb") == ""
    assert picture_html(photo, "thumb_small 400w, thumb 600w", alt="") == ""


def test_broken_avif_never_yields_avif_source(monkeypatch, make_image):
    real_save = Image.Image.save

    def save(self, fp, format=None, **params):
        if (format or "").upper() == "AVIF":
            raise OSError("нет кодировщика AVIF")
        return real_save(self, fp, format, **params)

    monkeypatch.setattr(Image.Image, "save", save)
    photo = GalleryPhoto.objects.create(image=make_image())
    for _ in range(2):
        html = picture_html(photo, "thumb", alt="")
        assert html.startswith("<img ") and ".avif" not in html


def test_picture_skips_avif_when_pillow_cannot_encode_it(monkeypatch):
    monkeypatch.setattr(images, "AVIF_SUPPORTED", False)
    assert picture_html(Photo(), "card", alt="") == '<img src="/m/card.webp" alt="">'


def test_url_while_generating_elsewhere_waits_for_real_file(make_image):
    # Другой поток пометил миниатюру «создаётся», но файла ещё нет: показ создаёт её сам, а не отдаёт пустой URL.
    photo = GalleryPhoto.objects.create(image=make_image())
    spec = photo.thumb
    spec.cachefile_backend.set_state(spec, "generating")
    assert spec.url and spec.storage.exists(spec.name)


def test_thumbnail_written_atomically_and_readable_by_nginx(make_image, media_root):
    photo = GalleryPhoto.objects.create(image=make_image())
    path = media_root / photo.thumb.url.removeprefix("/media/")
    assert path.stat().st_mode & 0o777 == 0o644  # nginx в соседнем контейнере читает под своим пользователем
    assert not list(path.parent.glob(".*"))  # временных файлов не осталось


def _thumb_paths(photo, media_root, names=("thumb", "thumb_avif", "thumb_small", "full")):
    return [media_root / getattr(photo, name).url.removeprefix("/media/") for name in names]  # url создаёт файлы


def test_thumbnails_removed_with_photo_after_commit(make_image, media_root, django_capture_on_commit_callbacks):
    photo = GalleryPhoto.objects.create(image=make_image())
    paths = _thumb_paths(photo, media_root)
    folder = paths[0].parent
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        photo.delete()
    assert all(p.exists() for p in paths)  # до коммита — на месте: откат не должен терять файлы
    for callback in callbacks:
        callback()
    assert not any(p.exists() for p in paths)
    assert not folder.exists()  # папка миниатюр этого фото тоже


def test_thumbnails_of_replaced_photo_removed(make_image, media_root, django_capture_on_commit_callbacks):
    photo = GalleryPhoto.objects.create(image=make_image())
    old_paths = _thumb_paths(photo, media_root)
    with django_capture_on_commit_callbacks(execute=True):
        photo.image = make_image("new.jpg")
        photo.save()
    photo = GalleryPhoto.objects.get(pk=photo.pk)
    assert not any(p.exists() for p in old_paths)
    assert all(p.exists() for p in _thumb_paths(photo, media_root))


def test_prune_refuses_to_wipe_cache_when_database_has_no_photos(make_image, media_root):
    # Контейнер стартовал не с той базой (пустой) — не удаляем все миниатюры.
    stale = media_root / "CACHE/images/gallery/old/stale.webp"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"x")
    two_hours_ago = time.time() - 2 * 3600
    os.utime(stale, (two_hours_ago, two_hours_ago))
    call_command("prune_image_cache")
    assert stale.exists()


def test_request_does_not_generate_thumbnails_beyond_its_time_budget(client, monkeypatch, make_image):
    # Прод, 11.10.2026: после смены спек галерея пыталась пережать ~900 миниатюр в одном запросе,
    # gunicorn убил воркер по таймауту (30 с) → 500. Запрос тратит на генерацию не больше бюджета, остальное — потом.
    monkeypatch.setattr(images, "REQUEST_GENERATION_BUDGET", 0, raising=False)
    photo = GalleryPhoto.objects.create(image=make_image())
    response = client.get("/gallery/")
    assert response.status_code == 200
    assert not photo.thumb.storage.exists(photo.thumb.name)  # не пережимали в запросе
    html = response.content.decode()
    assert f'src="{photo.image.url}"' in html  # пока миниатюры нет — оригинал, фото не пропадает из галереи
    assert ".avif" not in html

    monkeypatch.setattr(images, "REQUEST_GENERATION_BUDGET", 5)
    html = client.get("/gallery/").content.decode()  # следующий запрос досоздаёт в пределах бюджета
    assert photo.thumb.storage.exists(photo.thumb.name) and ".avif" in html


def _imgs(html: str, path_part: str) -> list[str]:
    return [tag for tag in re.findall(r"<img [^>]*>", html) if path_part in tag]


def test_gallery_first_row_loads_eagerly(client, make_image):
    for i in range(6):
        GalleryPhoto.objects.create(image=make_image(f"{i}.jpg"))
    imgs = _imgs(client.get("/gallery/").content.decode(), "/gallery/")
    assert len(imgs) == 6
    assert 'fetchpriority="high"' in imgs[0]
    assert all('loading="lazy"' not in tag for tag in imgs[:4])
    assert all('loading="lazy"' in tag for tag in imgs[4:])
    assert sum('fetchpriority="high"' in tag for tag in imgs) == 1


def test_gallery_short_list(client, make_image):
    for i in range(2):
        GalleryPhoto.objects.create(image=make_image(f"{i}.jpg"))
    imgs = _imgs(client.get("/gallery/").content.decode(), "/gallery/")
    assert [('fetchpriority="high"' in t, 'loading="lazy"' in t) for t in imgs] == [(True, False), (False, False)]


def test_category_has_single_high_priority_photo(client, make_image):
    category = Category.objects.create(name="Парк", is_published=True, preview=make_image("preview.jpg"))
    for i in range(3):
        CategoryPhoto.objects.create(category=category, image=make_image(f"{i}.jpg"))
    html = client.get(category.get_absolute_url()).content.decode()
    assert html.count('fetchpriority="high"') == 1
    slides = _imgs(html, "/catalog/categories/")
    assert slides and all('loading="lazy"' in tag for tag in slides)


def test_service_slider_first_photo_stays_eager(client, make_image):
    service = Service.objects.create(name="Троллей", has_page=True)
    for i in range(2):
        ServicePhoto.objects.create(service=service, image=make_image(f"{i}.jpg"))
    slides = _imgs(client.get(service.get_absolute_url()).content.decode(), "/catalog/services/")
    assert 'fetchpriority="high"' in slides[0] and 'loading="lazy"' not in slides[0]
    assert 'loading="lazy"' in slides[1]
