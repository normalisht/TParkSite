"""Особые дни (SpecialDay): «закрыты с 16:00» или «работаем с 14:00» в конкретную дату — рядом с часами работы."""

from datetime import date, time

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.core.models import SiteSettings, SpecialDay
from apps.texts.models import SiteText

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 14)  # tests/conftest.py подменяет seasons.today()


@pytest.mark.parametrize(
    ("opens_at", "closes_at", "expected"),
    [
        (None, time(16), "закрыты с 16:00"),
        (time(14), None, "работаем с 14:00"),
        (time(9), time(16, 30), "работаем с 09:00 до 16:30"),
    ],
)
def test_hours_text(opens_at, closes_at, expected):
    assert SpecialDay(day=TODAY, opens_at=opens_at, closes_at=closes_at).hours_text == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [(TODAY, "Сегодня"), (date(2026, 7, 15), "Завтра"), (date(2026, 7, 16), "16 июля"), (date(2027, 1, 2), "2 января")],
)
def test_day_text(day, expected):
    assert SpecialDay(day=day, closes_at=time(16)).day_text == expected


@pytest.mark.parametrize("url", ["/", "/contacts/", "/gallery/"])
def test_special_day_is_shown_near_hours_and_in_footer(client, url):
    SpecialDay.objects.create(day=date(2026, 7, 20), closes_at=time(16))
    html = client.get(url).content.decode()
    assert '<span class="font-semibold text-white">20 июля</span> — закрыты с 16:00' in html[html.index("<footer") :]
    if url != "/gallery/":
        main = html[html.index("<main") : html.index("</main>")]
        assert "20 июля</span> — закрыты с 16:00" in main


def test_special_day_shows_today_and_hides_after_date(client):
    SpecialDay.objects.create(day=TODAY, opens_at=time(14))
    SpecialDay.objects.create(day=date(2026, 7, 13), closes_at=time(16))
    html = client.get("/contacts/").content.decode()
    assert "Сегодня</span> — работаем с 14:00" in html
    assert "закрыты с 16:00" not in html


def test_shown_is_nearest_first_and_limited():
    days = [date(2026, 7, 20 + i) for i in range(3)]
    for day in reversed(days):
        SpecialDay.objects.create(day=day, closes_at=time(16))
    assert [item.day for item in SpecialDay.objects.shown(TODAY, 2)] == days[:2]


def test_site_shows_as_many_days_as_set_in_settings(client):
    for offset in range(4):
        SpecialDay.objects.create(day=date(2026, 7, 20 + offset), closes_at=time(16))
    assert "23 июля" not in client.get("/contacts/").content.decode()  # по умолчанию — три
    SiteSettings.objects.update(special_days_shown=4)
    assert "23 июля" in client.get("/contacts/").content.decode()
    SiteSettings.objects.update(special_days_shown=1)
    assert "21 июля" not in client.get("/contacts/").content.decode()


@pytest.mark.parametrize("value", [0, 11])
def test_days_shown_setting_is_limited(value):
    with pytest.raises(ValidationError) as error:
        SiteSettings(special_days_shown=value).clean_fields()
    assert "special_days_shown" in error.value.message_dict


def test_closed_all_day_text_and_needs_no_time(client):
    SpecialDay.objects.create(day=date(2026, 7, 20), is_all_day=True)
    assert SpecialDay.objects.get().hours_text == "закрыты весь день"
    SpecialDay(day=date(2026, 7, 21), is_all_day=True).full_clean()
    assert "20 июля</span> — закрыты весь день" in client.get("/contacts/").content.decode()


@pytest.mark.parametrize("url", ["/", "/contacts/"])
def test_closed_all_day_text_follows_admin_text(client, admin_client, url):
    SpecialDay.objects.create(day=date(2026, 7, 20), is_all_day=True)
    SiteText.objects.filter(key="common.closed_all_day").update(text="выходной")
    html = client.get(url).content.decode()
    assert html.count("20 июля</span> — выходной") == 2  # блок часов и подвал
    assert "20 июля — выходной" in admin_client.get("/admin/core/specialday/").content.decode()
    SiteText.objects.filter(key="common.closed_all_day").update(text="")  # обязательный: пустой — текст по умолчанию
    assert SpecialDay.objects.get().hours_text == "закрыты весь день"
    assert "20 июля</span> — закрыты весь день" in client.get(url).content.decode()


@pytest.mark.parametrize("url", ["/", "/contacts/"])
def test_closed_days_do_not_add_queries_on_site(client, url):
    for day in (20, 21, 22):
        SpecialDay.objects.create(day=date(2026, 7, day), is_all_day=True)
    with CaptureQueriesContext(connection) as queries:
        client.get(url)
    assert sum("texts_sitetext" in query["sql"] for query in queries) == 1


@pytest.mark.parametrize(
    "fields",
    [{}, {"is_all_day": True, "closes_at": time(16)}, {"is_all_day": True, "opens_at": time(14)}],
    ids=["nothing", "closed-with-closing-time", "closed-with-opening-time"],
)
def test_closed_or_time_is_required(fields):
    with pytest.raises(ValidationError, match="что-то одно"):
        SpecialDay(day=TODAY, **fields).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        SpecialDay.objects.create(day=TODAY, **fields)


def test_closing_must_be_after_opening():
    with pytest.raises(ValidationError) as error:
        SpecialDay(day=TODAY, opens_at=time(16), closes_at=time(14)).full_clean()
    assert "closes_at" in error.value.message_dict


def test_one_record_per_date():
    SpecialDay.objects.create(day=TODAY, closes_at=time(16))
    with pytest.raises(ValidationError) as error:
        SpecialDay(day=TODAY, opens_at=time(14)).full_clean()
    assert "day" in error.value.message_dict


def test_admin_list_and_status(admin_client):
    SpecialDay.objects.create(day=date(2026, 7, 1), closes_at=time(16))
    SiteSettings.objects.update_or_create(pk=1, defaults={"special_days_shown": 1})
    for offset in range(2):
        SpecialDay.objects.create(day=date(2026, 7, 20 + offset), opens_at=time(14))
    html = admin_client.get("/admin/core/specialday/").content.decode()
    assert "Прошёл" in html and "Показывается" in html and "Появится позже" in html
    assert "работаем с 14:00" in html


def test_admin_create(admin_client):
    response = admin_client.post(
        "/admin/core/specialday/add/", {"day": "20.07.2026", "opens_at": "", "closes_at": "16:00"}
    )
    assert response.status_code == 302
    assert SpecialDay.objects.get().closes_at == time(16)


def test_admin_create_without_time_shows_error(admin_client):
    response = admin_client.post("/admin/core/specialday/add/", {"day": "20.07.2026", "opens_at": "", "closes_at": ""})
    assert response.status_code == 200
    assert "что-то одно" in response.content.decode()
    assert not SpecialDay.objects.exists()


def test_admin_form_shows_time_without_seconds(admin_client):
    item = SpecialDay.objects.create(day=date(2026, 7, 20), closes_at=time(16))
    html = admin_client.get(f"/admin/core/specialday/{item.pk}/change/").content.decode()
    assert 'value="16:00"' in html


@pytest.mark.parametrize("url", ["/", "/contacts/"])
def test_all_day_event_shows_own_text(client, admin_client, url):
    SpecialDay.objects.create(day=date(2026, 7, 20), is_all_day=True, all_day_text="корпоратив <b>парк закрыт")
    html = client.get(url).content.decode()
    assert html.count("20 июля</span> — корпоратив &lt;b&gt;парк закрыт") == 2  # блок часов и подвал
    assert "закрыты весь день" not in html
    assert "20 июля — корпоратив" in admin_client.get("/admin/core/specialday/").content.decode()


def test_all_day_text_needs_checkbox():
    with pytest.raises(ValidationError) as error:
        SpecialDay(day=TODAY, closes_at=time(16), all_day_text="корпоратив").full_clean()
    assert "all_day_text" in error.value.message_dict
    SpecialDay(day=TODAY, is_all_day=True, all_day_text="корпоратив").full_clean()


def test_admin_creates_all_day_event(admin_client):
    data = {
        "day": "20.07.2026",
        "is_all_day": "on",
        "all_day_text": "День открытых дверей",
        "opens_at": "",
        "closes_at": "",
    }
    assert admin_client.post("/admin/core/specialday/add/", data).status_code == 302
    item = SpecialDay.objects.get()
    assert item.is_all_day and item.all_day_text == "День открытых дверей"
