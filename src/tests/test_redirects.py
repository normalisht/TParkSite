"""Смена адреса страницы: старый адрес ведёт на новый (301), без цепочек и петель."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
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
    ids=["service", "event", "info_page"],
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


@pytest.mark.parametrize(
    "new_path", ["https://evil.example/", "//evil.example/", "/\\evil.example", "http:evil", "category/new/", ""]
)
def test_new_path_must_be_site_relative(new_path):
    with pytest.raises(ValidationError) as error:
        Redirect(old_path="/category/old/", new_path=new_path).full_clean()
    assert "new_path" in error.value.message_dict


@pytest.mark.parametrize(
    "old_path", ["category/old/", "//evil.example/", "/category/old/?a=1", "/category/old/#x", "/category/old/\n"]
)
def test_old_path_must_be_site_relative_without_query(old_path):
    with pytest.raises(ValidationError) as error:
        Redirect(old_path=old_path, new_path="/category/new/").full_clean()
    assert "old_path" in error.value.message_dict


def test_redirect_to_itself_is_rejected():
    with pytest.raises(ValidationError):
        Redirect(old_path="/category/a/", new_path="/category/a/").full_clean()


def test_valid_redirect_passes_validation():
    Redirect(old_path="/category/old/", new_path="/category/new/?x=1").full_clean()


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/", "/\\evil.example", "category/new/"])
def test_middleware_ignores_unsafe_target(client, target):
    Redirect.objects.create(old_path="/nowhere/", new_path=target)  # в обход валидации
    assert client.get("/nowhere/").status_code == 404


def test_target_with_query_gets_ampersand(client):
    Redirect.objects.create(old_path="/nowhere/", new_path="/category/new/?x=1")
    assert client.get("/nowhere/?utm_source=vk")["Location"] == "/category/new/?x=1&utm_source=vk"


def test_failed_save_leaves_no_redirect():
    Category.objects.create(name="Один", slug="one", is_published=True)
    other = Category.objects.create(name="Два", slug="two", is_published=True)
    other.slug = "one"
    with pytest.raises(IntegrityError):
        other.save()
    assert not Redirect.objects.exists()
