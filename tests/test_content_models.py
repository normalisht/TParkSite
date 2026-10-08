from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.content.models import Event, GalleryPhoto

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 1)


def make_event(title, day, show_after=False):
    return Event.objects.create(title=title, date=day, show_after_date=show_after)


def test_upcoming_includes_today_sorted():
    later = make_event("Позже", date(2026, 7, 10))
    today = make_event("Сегодня", TODAY)
    make_event("Вчера", date(2026, 6, 30))
    assert list(Event.objects.upcoming(TODAY)) == [today, later]


def test_past_visible_only_flagged_newest_first():
    older = make_event("Старое", date(2026, 5, 1), show_after=True)
    newer = make_event("Новое", date(2026, 6, 1), show_after=True)
    make_event("Скрытое", date(2026, 6, 15))
    assert list(Event.objects.past_visible(TODAY)) == [newer, older]


def test_text_color_must_be_hex():
    event = Event(title="x", date=TODAY, text_color="red; background:url(x)")
    with pytest.raises(ValidationError):
        event.full_clean()


def test_gallery_photo_file_removed_on_delete(make_image, media_root, django_capture_on_commit_callbacks):
    photo = GalleryPhoto.objects.create(image=make_image())
    path = media_root / photo.image.name
    assert path.exists()
    with django_capture_on_commit_callbacks(execute=True):
        photo.delete()
    assert not path.exists()


def test_uploaded_photo_is_downscaled(make_image, media_root):
    from PIL import Image

    photo = GalleryPhoto.objects.create(image=make_image(size=(4000, 3000)))
    with Image.open(media_root / photo.image.name) as image:
        assert image.size == (1440, 1080)
