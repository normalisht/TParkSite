import pytest

from apps.catalog.models import Category, CategoryService, Service
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db


def assert_301(response, url):
    assert response.status_code == 301
    assert response.url == url


def test_tpark_and_about(client):
    assert_301(client.get("/TPark"), "/")
    assert_301(client.get("/about_2"), "/about/")


def test_category(client):
    category = Category.objects.create(id=5, name="Байдарки", is_published=True)
    assert_301(client.get("/category?category_id=5"), category.get_absolute_url())
    assert_301(client.get("/category/?category_id=5"), category.get_absolute_url())


def test_hidden_category_is_404(client):
    Category.objects.create(id=6, name="Скрытая", is_published=False)
    assert client.get("/category?category_id=6").status_code == 404


def test_service_with_page(client):
    service = Service.objects.create(id=12, name="Сплав", has_page=True)
    assert_301(client.get("/category/service?service_id=12"), service.get_absolute_url())


def test_service_without_page_goes_to_category(client):
    category = Category.objects.create(name="Аренда", is_published=True)
    service = Service.objects.create(id=13, name="Палатка")
    CategoryService.objects.create(category=category, service=service)
    assert_301(client.get("/category/service?service_id=13"), category.get_absolute_url())


def test_info(client):
    page = InfoPage.objects.create(id=11, title="Правила")
    assert_301(client.get("/info?info_id=11"), page.get_absolute_url())


@pytest.mark.parametrize(
    "url",
    [
        "/category?category_id=abc",
        "/category",
        "/category?category_id=",
        "/category/service?service_id=-1",
        "/info?info_id=999",
        "/category?category_id=%C2%B2",
        "/info?info_id=%C2%B3",
    ],
)
def test_legacy_redirect_bad_param_is_404(client, url):
    assert client.get(url).status_code == 404
