import json
import re
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.content.models import Event

pytestmark = pytest.mark.django_db


def make_event(title="Слёт", days=5, **kwargs):
    return Event.objects.create(title=title, date=timezone.localdate() + timedelta(days=days), **kwargs)


def test_slug_from_title_and_year():
    event = Event.objects.create(title="Летний слёт", date=date(2026, 7, 10))
    assert event.slug == "letnii-sliot-2026"
    assert event.get_absolute_url() == "/events/letnii-sliot-2026/"


def test_slug_unique_for_same_title_and_year():
    first = Event.objects.create(title="Сплав", date=date(2026, 6, 1))
    second = Event.objects.create(title="Сплав", date=date(2026, 8, 1))
    assert first.slug != second.slug


def test_visible_matches_list():
    today = timezone.localdate()
    upcoming = make_event("Будущее")
    shown = make_event("Прошлое видимое", days=-5, show_after_date=True)
    make_event("Прошлое скрытое", days=-5)
    assert set(Event.objects.visible(today)) == {upcoming, shown}


def test_event_page(client, make_image):
    event = make_event(
        description="<p>Полное описание мероприятия</p>", link="https://vk.com/tpark", image=make_image()
    )
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert "Полное описание мероприятия" in html
    assert "https://vk.com/tpark" in html
    assert "<title>Слёт — Т-Парк</title>" in html
    assert 'name="description" content="Полное описание мероприятия"' in html
    assert 'property="og:image" content="http://testserver/media/' in html
    assert f'rel="canonical" href="http://testserver{event.get_absolute_url()}"' in html


def test_event_page_json_ld(client):
    event = make_event(description="<p>Описание</p>")
    html = client.get(event.get_absolute_url()).content.decode()
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    data = json.loads(raw)
    assert data["@type"] == "Event"
    assert data["name"] == "Слёт"
    assert data["startDate"] == event.date.isoformat()
    assert data["description"] == "Описание"


def test_past_visible_event_page(client):
    event = make_event(days=-5, show_after_date=True)
    assert client.get(event.get_absolute_url()).status_code == 200


def test_hidden_past_event_is_404(client):
    event = make_event(days=-5)
    assert client.get(event.get_absolute_url()).status_code == 404


def test_events_list_links_to_detail(client):
    long_text = "Слово " * 100
    event = make_event(description=f"<p>{long_text}</p>", link="https://vk.com/external")
    html = client.get("/events/").content.decode()
    assert event.get_absolute_url() in html
    assert long_text.strip() not in html
    assert "https://vk.com/external" not in html


def test_sitemap_lists_visible_events(client):
    shown = make_event("Видимое")
    hidden = make_event("Скрытое", days=-5)
    xml = client.get("/sitemap.xml").content.decode()
    assert shown.get_absolute_url() in xml
    assert hidden.get_absolute_url() not in xml
