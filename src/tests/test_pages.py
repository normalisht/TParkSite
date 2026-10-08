from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Category, CategoryPhoto, CategoryService, Service
from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db

STATIC_PAGES = ["/events/", "/about/", "/reviews/", "/gallery/", "/contacts/"]


@pytest.mark.parametrize("url", STATIC_PAGES)
def test_static_pages_on_empty_db(client, url):
    assert client.get(url).status_code == 200


@pytest.fixture
def category(make_image):
    category = Category.objects.create(name="Сплавы", description="<p>Описание сплавов</p>", is_published=True)
    CategoryPhoto.objects.create(category=category, image=make_image(), order=0)
    return category


def test_category_page_lists_services(client, category):
    with_page = Service.objects.create(name="Однодневный сплав", price="2000", price_unit="человек", has_page=True)
    inline = Service.objects.create(
        name="Аренда байдарки", price="500", price_unit="час", short_description="<p>Весло включено</p>"
    )
    hidden = Service.objects.create(name="Скрытая услуга", is_published=False)
    for order, service in enumerate([with_page, inline, hidden]):
        CategoryService.objects.create(category=category, service=service, order=order)
    html = client.get(category.get_absolute_url()).content.decode()
    assert "Описание сплавов" in html
    assert "2000 руб / человек" in html and with_page.get_absolute_url() in html
    assert "Весло включено" in html
    assert "Скрытая услуга" not in html
    assert "swiper-slide" in html


def test_unpublished_category_is_404(client):
    category = Category.objects.create(name="Черновик", is_published=False)
    assert client.get(category.get_absolute_url()).status_code == 404


def test_service_page(client):
    service = Service.objects.create(name="Сплав", description="<p>Полное описание</p>", price="2000", has_page=True)
    response = client.get(service.get_absolute_url())
    assert response.status_code == 200
    assert "Полное описание" in response.content.decode()


@pytest.mark.parametrize("kwargs", [{"has_page": False}, {"has_page": True, "is_published": False}])
def test_service_page_404(client, kwargs):
    service = Service.objects.create(name="Сплав", **kwargs)
    assert client.get(service.get_absolute_url()).status_code == 404


def test_events_page_order(client):
    today = timezone.localdate()
    Event.objects.create(title="Будущее", date=today + timedelta(days=5))
    Event.objects.create(title="Сегодня", date=today)
    Event.objects.create(title="Прошлое видимое", date=today - timedelta(days=5), show_after_date=True)
    Event.objects.create(title="Прошлое скрытое", date=today - timedelta(days=3))
    html = client.get("/events/").content.decode()
    assert html.index("Сегодня") < html.index("Будущее") < html.index("Прошлое видимое")
    assert "Прошлое скрытое" not in html


def test_events_page_placeholder(client):
    assert "Скоро анонсируем" in client.get("/events/").content.decode()


def test_about_page(client, make_image):
    Employee.objects.create(name="Иван", position="Инструктор")
    Partner.objects.create(name="Партнёр", link="https://example.com", logo=make_image())
    html = client.get("/about/").content.decode()
    assert "Иван" in html and "Инструктор" in html and "https://example.com" in html


def test_about_page_hides_empty_employees(client):
    assert "Команда" not in client.get("/about/").content.decode()


def test_reviews_manual_order_and_published(client):
    Review.objects.create(author="Второй", text="<p>b</p>", order=2)
    Review.objects.create(author="Первый", text="<p>a</p>", order=1)
    Review.objects.create(author="Скрытый", text="<p>c</p>", is_published=False)
    html = client.get("/reviews/").content.decode()
    assert html.index("Первый") < html.index("Второй")
    assert "Скрытый" not in html


def test_gallery_page(client, make_image):
    GalleryPhoto.objects.create(image=make_image(), caption="Закат")
    html = client.get("/gallery/").content.decode()
    assert "glightbox" in html and "Закат" in html


def test_info_page(client):
    page = InfoPage.objects.create(title="Правила", body="<p>Текст правил</p>")
    assert "Текст правил" in client.get(page.get_absolute_url()).content.decode()
    hidden = InfoPage.objects.create(title="Черновик", is_published=False)
    assert client.get(hidden.get_absolute_url()).status_code == 404


def test_nav_has_all_sections(client):
    html = client.get("/").content.decode()
    for url in STATIC_PAGES:
        assert f'href="{url}"' in html
