import pytest
from django.db import IntegrityError

from apps.catalog.models import Category, CategoryService, Service

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("price", "unit", "expected"),
    [("1500", "час", "1500 руб / час"), ("1500", "", "1500 руб"), ("", "час", ""), ("", "", "")],
)
def test_price_display(price, unit, expected):
    assert Service(name="x", price=price, price_unit=unit).price_display == expected


def test_slugs_generated():
    assert Category.objects.create(name="Байдарки").slug == "baidarki"
    assert Service.objects.create(name="Байдарки").slug == "baidarki"


def test_published_services_order_and_visibility():
    category = Category.objects.create(name="Сплавы", is_published=True)
    late = Service.objects.create(name="Поздняя")
    early = Service.objects.create(name="Ранняя")
    hidden = Service.objects.create(name="Скрытая", is_published=False)
    CategoryService.objects.create(category=category, service=late, order=5)
    CategoryService.objects.create(category=category, service=early, order=1)
    CategoryService.objects.create(category=category, service=hidden, order=0)
    assert category.published_services() == [early, late]


def test_category_service_unique():
    category = Category.objects.create(name="A")
    service = Service.objects.create(name="B")
    CategoryService.objects.create(category=category, service=service)
    with pytest.raises(IntegrityError):
        CategoryService.objects.create(category=category, service=service)


def test_category_defaults_hidden():
    assert Category.objects.create(name="Новая").is_published is False
