from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Service, ServicePhoto
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
    url = "admin:catalog_service_changelist"
    assert _names(admin_client, url, gaps="photo") == {"Без всего"}
    assert _names(admin_client, url, gaps="price") == {"Без всего"}
    assert _names(admin_client, url, gaps="short") == {"Без всего"}


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
    Event.objects.create(title="Скоро", date=today + timedelta(days=5))
    Event.objects.create(title="Было", date=today - timedelta(days=5))
    Event.objects.create(title="Черновик", date=today + timedelta(days=5), is_published=False)
    page = admin_client.get(reverse("admin:content_event_changelist")).content.decode()
    for text in ("Предстоящее", "Прошедшее, скрыто", "Черновик"):
        assert text in page
    from apps.content.admin import EventAdmin

    assert EventAdmin.date_hierarchy is None


def test_review_search_and_toggle(admin_client):
    Review.objects.create(text="<p>Отличный сплав</p>", date=timezone.localdate())
    Review.objects.create(text="<p>Верёвочный парк</p>", date=timezone.localdate())
    response = admin_client.get(reverse("admin:content_review_changelist"), {"q": "сплав"})
    assert len(response.context["cl"].result_list) == 1
    from apps.content.admin import ReviewAdmin

    assert "is_published" in ReviewAdmin.list_editable
