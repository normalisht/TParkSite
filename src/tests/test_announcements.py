"""Плашка под шапкой (Announcement): включается галочкой и, по желанию, датами; на сайте — первая подходящая."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.models import Announcement

pytestmark = pytest.mark.django_db


def _set_today(monkeypatch, day):
    monkeypatch.setattr("apps.core.seasons.today", lambda: day)


def _banner(html):
    return html.split('class="site-banner', 1)[1].split("</div>", 1)[0]


def test_published_announcement_shows_under_header(client):
    Announcement.objects.create(text="Корпоративы <b>", link="/events/")
    html = client.get("/").content.decode()
    banner = _banner(html)
    assert '<a href="/events/"' in banner and "Корпоративы &lt;b&gt;" in banner
    # Под шапкой, а не над ней: над sticky-шапкой мобильное меню не влезает в экран.
    assert html.index("</header>") < html.index('class="site-banner') < html.index('<main id="content"')


def test_announcement_without_link_is_plain_text(client):
    Announcement.objects.create(text="Т-Парк закрыт 1 января")
    banner = _banner(client.get("/").content.decode())
    assert "<a " not in banner and "закрыт 1 января" in banner
    assert '<span class="whitespace-nowrap">Т-Парк</span>' in banner  # без переноса по дефису, как в текстах сайта


def test_switched_off_announcement_is_hidden(client):
    Announcement.objects.create(text="Корпоративы", is_published=False)
    assert "site-banner" not in client.get("/").content.decode()


def test_no_announcements_no_banner(client):
    assert "site-banner" not in client.get("/").content.decode()


@pytest.mark.parametrize(
    ("day", "shown"),
    [(date(2026, 10, 19), False), (date(2026, 10, 20), True), (date(2026, 10, 31), True), (date(2026, 11, 1), False)],
)
def test_dates_limit_announcement(client, monkeypatch, day, shown):
    Announcement.objects.create(text="Акция", starts_on=date(2026, 10, 20), ends_on=date(2026, 10, 31))
    _set_today(monkeypatch, day)
    assert ("site-banner" in client.get("/").content.decode()) is shown


def test_open_ended_dates(monkeypatch):
    Announcement.objects.create(text="С даты", starts_on=date(2026, 10, 20))
    Announcement.objects.create(text="До даты", ends_on=date(2026, 10, 1), order=1)
    assert Announcement.objects.current(date(2026, 9, 1)).text == "До даты"
    assert Announcement.objects.current(date(2026, 10, 10)) is None
    assert Announcement.objects.current(date(2027, 5, 1)).text == "С даты"


def test_first_by_order_wins(client):
    Announcement.objects.create(text="Вторая", order=2)
    Announcement.objects.create(text="Первая", order=1)
    banner = _banner(client.get("/").content.decode())
    assert "Первая" in banner and "Вторая" not in banner


def test_announcement_validation():
    item = Announcement(
        text="Акция", link="javascript:alert(1)", starts_on=date(2026, 11, 1), ends_on=date(2026, 10, 1)
    )
    with pytest.raises(ValidationError) as exc:
        item.full_clean()
    assert {"link", "ends_on"} <= set(exc.value.message_dict)


def test_banner_independent_of_season_one_query_and_stable_etag(client, monkeypatch):
    Announcement.objects.create(text="Акция")
    for day in (date(2026, 7, 14), date(2026, 12, 31)):
        _set_today(monkeypatch, day)
        with CaptureQueriesContext(connection) as ctx:
            first = client.get("/")
        assert "site-banner" in first.content.decode()
        assert sum('"core_announcement"' in q["sql"] for q in ctx.captured_queries) == 1
        assert client.get("/", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


def test_admin_list_toggles_and_shows_current(admin_client):
    Announcement.objects.create(text="Первая", order=1)
    Announcement.objects.create(text="Вторая", order=2)
    html = admin_client.get(reverse("admin:core_announcement_changelist")).content.decode()
    assert "под шапкой" in html  # вводная над списком
    assert 'name="form-0-is_published"' in html  # галочка «Показывать» прямо в списке
    assert html.count("Показывается") == 1


def test_admin_add_announcement(admin_client):
    response = admin_client.post(
        reverse("admin:core_announcement_add"),
        {"text": "Новогодние корпоративы", "link": "/events/", "is_published": "on", "order": "0"},
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert Announcement.objects.get().link == "/events/"
