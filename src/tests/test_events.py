import json
import re
from datetime import date, time, timedelta

import pytest
from django.utils import timezone

from apps.content.models import Event
from apps.core.models import PARK_ADDRESS, SiteSettings

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
    assert "<title>Слёт — Т-Парк, Калужская область</title>" in html
    assert 'name="description" content="Полное описание мероприятия"' in html
    assert 'property="og:image" content="http://testserver/media/' in html
    assert f'rel="canonical" href="http://testserver{event.get_absolute_url()}"' in html


def test_event_page_json_ld(client):
    event = make_event(description="<p>Описание</p>")
    html = client.get(event.get_absolute_url()).content.decode()
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    nodes = {
        (node["@type"][0] if isinstance(node["@type"], list) else node["@type"]): node
        for node in json.loads(raw)["@graph"]
    }
    data = nodes["Event"]
    assert data["name"] == "Слёт"
    assert data["startDate"] == data["endDate"] == event.date.isoformat()
    assert data["description"] == "Описание"
    assert data["location"]["address"]["addressRegion"] == "Калужская область"
    assert data["organizer"] == {"@id": nodes["LocalBusiness"]["@id"]}
    assert [item["name"] for item in nodes["BreadcrumbList"]["itemListElement"]] == ["Главная", "Мероприятия", "Слёт"]


def test_event_page_json_ld_time_period_and_offer(client):
    event = make_event(
        days=5, end_date=timezone.localdate() + timedelta(days=7), start_time=time(18, 0), price="1 500 ₽"
    )
    html = client.get(event.get_absolute_url()).content.decode()
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    data = next(node for node in json.loads(raw)["@graph"] if node["@type"] == "Event")
    assert data["startDate"] == f"{event.date.isoformat()}T18:00:00+03:00"
    assert data["endDate"] == event.end_date.isoformat()
    assert data["offers"] == {
        "@type": "Offer",
        "price": "1500",
        "priceCurrency": "RUB",
        "url": data["url"],
        "availability": "https://schema.org/InStock",
    }


def test_event_page_booking_card(client):
    make_event("Другое", days=10)
    event = make_event(days=5, start_time=time(18, 0), price="1000 ₽ с участника")
    html = client.get(event.get_absolute_url()).content.decode()
    assert "начало в 18:00" in html and "1000 ₽ с участника" in html
    assert "Через 5 дней" in html
    assert "Другие мероприятия" in html and "Другое" in html
    assert "уже прошло" not in html


def test_past_visible_event_page(client):
    make_event("Скоро снова", days=3)
    event = make_event(days=-5, show_after_date=True)
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert "Мероприятие уже прошло" in html
    assert "Ближайшие мероприятия" in html and "Скоро снова" in html
    assert "Записаться" not in html


def test_events_list_sections(client):
    make_event("Первое", days=2)
    make_event("Второе", days=9)
    for i in range(8):
        make_event(f"Архив {i}", days=-10 - i, show_after_date=True)
    html = client.get("/events/").content.decode()
    assert html.index("Ближайшее") < html.index("Первое") < html.index("Предстоящие") < html.index("Второе")
    assert html.index("Второе") < html.index("Прошедшие") < html.index("Архив 0")
    assert "Показать все прошедшие" in html
    assert html.count(":class=\"all && '!block'\"") == 2


def test_past_event_without_flag_opens_by_link_but_is_not_indexed(client):
    event = make_event("Прошлый слёт", days=-5)
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert '<meta name="robots" content="noindex">' in response.content.decode()
    assert event.get_absolute_url() not in client.get("/sitemap.xml").content.decode()
    assert "Прошлый слёт" not in client.get("/events/").content.decode()


def test_visible_events_are_indexed(client):
    for event in (make_event(days=3), make_event("Архив", days=-5, show_after_date=True)):
        assert 'name="robots"' not in client.get(event.get_absolute_url()).content.decode()


def test_draft_event_is_hidden_everywhere(client):
    site = SiteSettings.load()
    site.home_show_events = True
    site.save()
    make_event("Опубликованное", days=2)
    draft = make_event("Черновик", days=3, is_published=False)
    assert client.get(draft.get_absolute_url()).status_code == 404
    for url in ("/", "/events/", "/sitemap.xml"):
        html = client.get(url).content.decode()
        assert "Черновик" not in html and draft.slug not in html, url


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


def test_event_cards_offer_smaller_photo(client, make_image):
    nearest = make_event("Ближайшее событие", days=2, image=make_image())
    make_event("Следующее", days=9, image=make_image())
    html = client.get("/events/").content.decode()
    img_srcsets = re.findall(r'<img src="[^"]+" srcset="([^"]+)"', html)
    avif_srcsets = re.findall(r'<source type="image/avif" srcset="([^"]+)"', html)
    assert len(img_srcsets) == len(avif_srcsets) == 2
    assert f"{nearest.card_small.url} 640w, {nearest.card.url} 800w" in img_srcsets
    assert f"{nearest.card_small_avif.url} 640w, {nearest.card_avif.url} 800w" in avif_srcsets
    assert html.count('sizes="(min-width') == 4


def _event_json_ld(client, event):
    html = client.get(event.get_absolute_url()).content.decode()
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    aside = re.search(r"<aside.*?</aside>", html, re.DOTALL).group()
    return aside, next(node for node in json.loads(raw)["@graph"] if node["@type"] == "Event")


def test_event_without_venue_is_in_park(client):
    SiteSettings.objects.update_or_create(pk=1, defaults={"latitude": "54.5", "longitude": "36.3"})
    aside, data = _event_json_ld(client, make_event())
    assert SiteSettings.load().address in aside
    assert "Маршрут" in aside
    assert data["location"]["name"] == "Т-Парк"


def test_event_with_venue_replaces_park_address_and_route(client):
    SiteSettings.objects.update_or_create(pk=1, defaults={"latitude": "54.5", "longitude": "36.3"})
    aside, data = _event_json_ld(client, make_event(venue="Лагерь «Сосны», Калуга"))
    assert "Лагерь «Сосны», Калуга" in aside
    assert SiteSettings.load().address not in aside
    assert "Маршрут" not in aside
    assert data["location"] == {"@type": "Place", "name": "Лагерь «Сосны», Калуга", "address": "Лагерь «Сосны», Калуга"}


def _meta_description(client, event):
    html = client.get(event.get_absolute_url()).content.decode()
    return re.search(r'name="description" content="(.*?)"', html).group(1)


def test_event_default_description_in_park(client):
    description = _meta_description(client, make_event())
    assert "мероприятие в Т-Парке" in description
    assert SiteSettings.load().address in description


def test_event_default_description_uses_venue_instead_of_park(client):
    description = _meta_description(client, make_event(venue="ТИЦ Обнинска"))
    assert "ТИЦ Обнинска" in description
    assert "в Т-Парке" not in description
    assert PARK_ADDRESS not in description


def _graph(html):
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    return json.loads(raw)["@graph"]


def test_event_ld_has_performer_and_availability(client):
    event = make_event(price="1000 ₽")
    node = next(n for n in _graph(client.get(event.get_absolute_url()).content.decode()) if n["@type"] == "Event")
    assert node["performer"] == node["organizer"]
    assert node["offers"]["availability"] == "https://schema.org/InStock"


def test_events_page_lists_upcoming_in_item_list(client):
    first, second = make_event("Первое", days=2), make_event("Второе", days=9)
    graph = _graph(client.get("/events/").content.decode())
    items = next(n for n in graph if n["@type"] == "ItemList")["itemListElement"]
    assert [i["url"] for i in items] == [f"http://testserver{e.get_absolute_url()}" for e in (first, second)]


def test_events_page_without_events_has_no_item_list(client):
    html = client.get("/events/").content.decode()
    assert '"ItemList"' not in html


def test_past_event_offer_has_no_availability(client):
    event = make_event(days=-30, price="500", show_after_date=True, is_published=True)
    html = client.get(event.get_absolute_url()).content.decode()
    node = next(n for n in _graph(html) if n["@type"] == "Event")
    assert node["offers"]["price"] == "500"
    assert "availability" not in node["offers"]
