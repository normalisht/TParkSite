import pytest
from django.db import IntegrityError

from apps.catalog.models import Category, CategoryService, Service

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("price", "unit", "expected"),
    [
        ("900", "час", "900 ₽ / час"),
        ("15000", "", "15 000 ₽"),
        ("15 000", "день", "15 000 ₽ / день"),
        ("от 3500", "участник", "от 3500 ₽ / участник"),
        ("договорная", "", "договорная"),
        ("договорная", "час", "договорная / час"),
        ("", "час", ""),
    ],
)
def test_price_display(price, unit, expected):
    # В выводе неразрывные пробелы (перед «₽» и в «15 000»); сравниваем с обычными.
    assert Service(name="Услуга", price=price, price_unit=unit).price_display.replace("\u00a0", " ") == expected


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


def test_service_str_shows_price_to_tell_duplicates_apart():
    assert str(Service(name="Фрироуп", price="900", price_unit="час")).replace("\u00a0", " ") == "Фрироуп — 900 ₽ / час"
    assert str(Service(name="Фрироуп")) == "Фрироуп"
