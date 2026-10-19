import pytest
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.search import fold

pytestmark = pytest.mark.django_db


def test_fold():
    assert fold("ЁЛКА и Ёж") == "елка и еж"
    assert fold(None) is None


def _names(admin_client, url_name, q):
    response = admin_client.get(reverse(url_name), {"q": q})
    assert response.status_code == 200
    return [str(obj) for obj in response.context["cl"].result_list]


def test_service_search_ignores_case_and_yo(admin_client):
    Service.objects.create(name="Батут большой")
    Service.objects.create(name="Верёвочная трасса")
    Service.objects.create(name="Сапборд")
    assert _names(admin_client, "admin:catalog_service_changelist", "батут") == ["Батут большой"]
    assert _names(admin_client, "admin:catalog_service_changelist", "ВЕРЕВОЧН") == ["Верёвочная трасса"]


def test_search_requires_every_word(admin_client):
    Service.objects.create(name="Батут большой")
    assert _names(admin_client, "admin:catalog_service_changelist", "батут большой") == ["Батут большой"]
    assert _names(admin_client, "admin:catalog_service_changelist", "батут сап") == []


SALE = "Скидка 50% на верёвочный парк"


@pytest.mark.parametrize(("q", "expected"), [("50%", [SALE]), ("_", []), ('"Верёвочный Парк"', [SALE]), ("%", [SALE])])
def test_search_special_characters_are_literal(admin_client, q, expected):
    Service.objects.create(name=SALE)
    Service.objects.create(name="Сапборд")
    assert _names(admin_client, "admin:catalog_service_changelist", q) == expected


def test_autocomplete_ignores_case(admin_client):
    Category.objects.create(name="Верёвочный парк")
    response = admin_client.get(
        reverse("admin:autocomplete"),
        {"term": "веревоч", "app_label": "catalog", "model_name": "categoryservice", "field_name": "category"},
    )
    assert [item["text"] for item in response.json()["results"]] == ["Верёвочный парк"]
