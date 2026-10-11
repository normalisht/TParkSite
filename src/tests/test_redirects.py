"""Смена адреса страницы: старый адрес ведёт на новый (301), без цепочек и петель."""

import pytest
from django.utils import timezone

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core.models import InfoPage, Redirect

pytestmark = pytest.mark.django_db


def _rename(obj, slug):
    obj.slug = slug
    obj.save()
    return obj


def test_renamed_category_redirects(client):
    category = Category.objects.create(name="Школа", slug="shkola-2026", is_published=True)
    _rename(category, "shkola")
    response = client.get("/category/shkola-2026/")
    assert response.status_code == 301
    assert response["Location"] == "/category/shkola/"
    assert client.get("/category/shkola/").status_code == 200


def test_redirect_keeps_query_string(client):
    _rename(Category.objects.create(name="Школа", slug="old", is_published=True), "new")
    response = client.get("/category/old/?utm_source=vk")
    assert response["Location"] == "/category/new/?utm_source=vk"


def test_second_rename_does_not_chain(client):
    category = Category.objects.create(name="Школа", slug="a", is_published=True)
    _rename(category, "b")
    _rename(category, "c")
    assert client.get("/category/a/")["Location"] == "/category/c/"
    assert client.get("/category/b/")["Location"] == "/category/c/"


def test_rename_back_removes_redirect(client):
    category = Category.objects.create(name="Школа", slug="a", is_published=True)
    _rename(category, "b")
    _rename(category, "a")
    assert client.get("/category/a/").status_code == 200
    assert client.get("/category/b/")["Location"] == "/category/a/"
    assert not Redirect.objects.filter(old_path="/category/a/").exists()


def test_new_objects_and_unchanged_slugs_create_nothing():
    category = Category.objects.create(name="Школа", is_published=True)
    category.name = "Школа инструкторов"
    category.save()
    assert not Redirect.objects.exists()


@pytest.mark.parametrize(
    "make",
    [
        lambda: Service.objects.create(name="Троллей", slug="trollei-old", has_page=True),
        lambda: Event.objects.create(title="Слёт", slug="slet-old", date=timezone.localdate()),
        lambda: InfoPage.objects.create(title="Правила", slug="pravila-old"),
    ],
)
def test_other_pages_remember_slug_change(make):
    obj = make()
    old_url = obj.get_absolute_url()
    _rename(obj, obj.slug.removesuffix("-old"))
    assert Redirect.objects.get(old_path=old_url).new_path == obj.get_absolute_url()


def test_live_page_wins_over_redirect(client):
    Redirect.objects.create(old_path="/category/zhivaia/", new_path="/category/drugaia/")
    Category.objects.create(name="Живая", slug="zhivaia", is_published=True)
    assert client.get("/category/zhivaia/").status_code == 200
