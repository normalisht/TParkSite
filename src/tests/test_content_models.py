from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.content.models import Event, GalleryPhoto, Review

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 1)


def make_event(title, day, show_after=False, **kwargs):
    return Event.objects.create(title=title, date=day, show_after_date=show_after, **kwargs)


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


def test_multi_day_event_is_upcoming_until_it_ends():
    running = make_event("Идёт", date(2026, 6, 20), end_date=date(2026, 7, 5))
    over = make_event("Закончилось", date(2026, 6, 1), show_after=True, end_date=date(2026, 6, 30))
    assert list(Event.objects.upcoming(TODAY)) == [running]
    assert list(Event.objects.past_visible(TODAY)) == [over]
    assert set(Event.objects.visible(TODAY)) == {running, over}


def test_end_date_before_start_is_invalid():
    event = Event(title="x", date=TODAY, end_date=date(2026, 6, 30), description="<p>x</p>")
    with pytest.raises(ValidationError) as error:
        event.full_clean()
    assert "end_date" in error.value.message_dict


def test_end_date_same_as_start_is_dropped():
    event = Event(title="x", date=TODAY, end_date=TODAY, description="<p>x</p>")
    event.full_clean()
    assert event.end_date is None


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2022, 12, 3), None, "3 декабря 2022"),
        (date(2027, 11, 18), date(2027, 11, 25), "18–25 ноября 2027"),
        (date(2027, 11, 18), date(2027, 12, 17), "18 ноября — 17 декабря 2027"),
        (date(2026, 12, 28), date(2027, 1, 5), "28 декабря 2026 — 5 января 2027"),
    ],
)
def test_event_period(start, end, expected):
    assert Event(title="x", date=start, end_date=end).period == expected


@pytest.mark.parametrize(
    ("offset", "length", "expected"),
    [
        (-3, 0, "Прошло"),
        (-2, 5, "Идёт сейчас"),
        (0, 2, "Идёт сейчас"),
        (0, 0, "Сегодня"),
        (1, 0, "Завтра"),
        (2, 0, "Через 2 дня"),
        (5, 0, "Через 5 дней"),
        (21, 0, "Через 21 день"),
        (40, 0, ""),
    ],
)
def test_event_timing(offset, length, expected):
    start = timezone.localdate() + timedelta(days=offset)
    end = start + timedelta(days=length) if length else None
    assert Event(title="x", date=start, end_date=end).timing == expected


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


@pytest.mark.parametrize(
    ("link", "label"),
    [
        ("https://reviews.yandex.ru/user/x", "Яндекс Карты"),
        ("https://vk.com/wall1", "VK"),
        ("https://www.example.org/r", "example.org"),
        ("", ""),
    ],
)
def test_review_source_label(link, label):
    assert Review(link=link).source_label == label
