from datetime import timedelta

import pytest
from django.contrib import admin
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Service, ServicePhoto
from apps.content.admin import EventAdmin
from apps.content.models import Event, Review

pytestmark = pytest.mark.django_db


def _names(admin_client, url_name, **params):
    response = admin_client.get(reverse(url_name), params)
    assert response.status_code == 200
    return {str(obj) for obj in response.context["cl"].result_list}


def test_service_gaps_filter(admin_client, make_image):
    with_photo = Service.objects.create(name="С фото", price="100", short_description="<p>Есть</p>")
    ServicePhoto.objects.create(service=with_photo, image=make_image())
    Service.objects.create(name="Без всего")
    empty_editor = Service.objects.create(name="Пустой редактор", price="200", short_description="<p></p>")
    ServicePhoto.objects.create(service=empty_editor, image=make_image("2.jpg"))
    url = "admin:catalog_service_changelist"
    assert _names(admin_client, url, gaps="photo") == {"Без всего"}
    assert _names(admin_client, url, gaps="price") == {"Без всего"}
    assert _names(admin_client, url, gaps="short") == {"Без всего", str(empty_editor)}


def test_service_list_queries_do_not_grow(admin_client, make_image):
    def count():
        with CaptureQueriesContext(connection) as ctx:
            admin_client.get(reverse("admin:catalog_service_changelist"))
        return len(ctx)

    Service.objects.create(name="А")
    before = count()
    for i in range(5):
        ServicePhoto.objects.create(service=Service.objects.create(name=f"Б{i}"), image=make_image(f"{i}.jpg"))
    assert count() == before


def test_event_status_column(admin_client):
    today = timezone.localdate()
    soon = Event.objects.create(title="Скоро", date=today + timedelta(days=5))
    past = Event.objects.create(title="Было", date=today - timedelta(days=5))
    archived = Event.objects.create(title="В архиве", date=today - timedelta(days=5), show_after_date=True)
    draft = Event.objects.create(title="Скрытое событие", date=today + timedelta(days=5), is_published=False)
    model_admin = EventAdmin(Event, admin.site)
    assert model_admin.status(soon) == "Предстоящее"
    assert model_admin.status(past) == "Прошедшее, скрыто"
    assert model_admin.status(archived) == "Прошедшее, в архиве"
    assert model_admin.status(draft) == "Черновик"
    page = admin_client.get(reverse("admin:content_event_changelist")).content.decode()
    assert "Статус" in page
    assert "Предстоящее" in page
    assert EventAdmin.date_hierarchy is None


def test_review_search_and_toggle(admin_client):
    today = timezone.localdate()
    shown = Review.objects.create(text="<p>Отличный сплав</p>", date=today)
    Review.objects.create(text="<p>Верёвочный парк</p>", date=today)
    url = reverse("admin:content_review_changelist")
    response = admin_client.get(url, {"q": "сплав"})
    assert len(response.context["cl"].result_list) == 1
    assert 'name="form-0-is_published"' in response.content.decode()
    # Снимаем галочку прямо в списке (в POST неотмеченный чекбокс отсутствует).
    admin_client.post(
        url,
        {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(shown.pk),
            "_save": "Сохранить",
        },
    )
    shown.refresh_from_db()
    assert shown.is_published is False
