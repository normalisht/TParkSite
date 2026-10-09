import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Category, CategoryPhoto, CategoryService, Service
from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.models import FounderFact, InfoPage, ParkFormat, Phone, SiteSettings

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
    assert with_page.get_absolute_url() in html
    # Цена разбита по слешу: перенос только между ценой и единицей.
    assert '<span class="inline-block whitespace-nowrap">2000 руб</span>' in html
    assert '<span class="data-wrapped:invisible">/ </span>человек</span>' in html
    assert "Весло включено" in html
    assert "Скрытая услуга" not in html
    assert "swiper-slide" in html
    # Полноэкранный просмотр открывает оригинал фото.
    assert f'data-full="{category.photos.get().image.url}"' in html


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
    Partner.objects.create(name="Партнёр", link="https://example.com", logo=make_image())
    html = client.get("/about/").content.decode()
    assert "https://example.com" in html


def test_about_page_sections(client):
    site = SiteSettings.load()
    site.about_text = "<p>Природа и тренинг</p>"
    site.founder_text = "<ul><li>Педагог</li></ul>"
    site.safety_page = InfoPage.objects.create(title="Правила безопасности", body="<p>Каски</p>")
    site.save()
    published = Category.objects.create(name="Верёвочный парк", is_published=True)
    hidden = Category.objects.create(name="Черновик", is_published=False)
    ParkFormat.objects.create(settings=site, name="T-park", caption="Тренинг-парк", category=published, order=0)
    ParkFormat.objects.create(settings=site, name="T-camp", caption="Тренинговый лагерь", category=hidden, order=1)
    FounderFact.objects.create(settings=site, value="1000+", label="тренингов провёл")

    html = client.get("/about/").content.decode()
    assert site.about_motto in html
    assert "Природа и тренинг" in html and "Педагог" in html
    assert "T-park" in html and "T-camp" in html and "1000+" in html
    assert published.get_absolute_url() in html
    assert hidden.get_absolute_url() not in html
    assert site.safety_page.get_absolute_url() in html
    assert '"founder"' in html and "Дмитрий Сергеев" in html


def test_about_hides_unpublished_safety_page(client):
    site = SiteSettings.load()
    site.safety_page = InfoPage.objects.create(title="Правила", body="<p>x</p>", is_published=False)
    site.save()
    assert site.safety_page.get_absolute_url() not in client.get("/about/").content.decode()


def test_reviews_newest_first_and_published(client):
    Review.objects.create(text="<p>Без даты</p>")
    Review.objects.create(text="<p>Старый</p>", date=date(2021, 6, 6))
    Review.objects.create(text="<p>Новый</p>", date=date(2023, 10, 26))
    Review.objects.create(text="<p>Скрытый</p>", is_published=False)
    html = client.get("/reviews/").content.decode()
    assert html.index("Новый") < html.index("Старый") < html.index("Без даты")
    assert "Скрытый" not in html


def test_review_signed_as_guest(client):
    Review.objects.create(text="<p>Классно</p>")
    for url in ("/reviews/", "/"):
        assert "Гость Т-Парка" in client.get(url).content.decode()


def test_review_card_links_to_source_when_link_set(client):
    Review.objects.create(text="<p>a</p>", link="https://reviews.yandex.ru/u/1", date=date(2022, 7, 20))
    Review.objects.create(text="<p>b</p>")
    html = client.get("/reviews/").content.decode()
    # Ссылка — только подпись источника, не вся карточка.
    assert re.search(r'<a href="https://reviews\.yandex\.ru/u/1"[^>]*>Яндекс Карты<', html)
    assert html.count('href="https://reviews.yandex.ru/u/1"') == 1
    assert "after:inset-0" not in html and "20 июля 2022" in html


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
    # В мобильном меню первым пунктом — ссылка на главную (категории идут сразу за ней).
    assert re.search(r'<a href="/" class="[^"]*">Главная</a>', html)


def test_contacts_page_hours_routes_and_reviews(client):
    site = SiteSettings.load()
    site.opening_hours = "Mo-Su 10:00-18:00"
    site.latitude, site.longitude = Decimal("54.956545"), Decimal("36.769595")
    site.reviews_url = "https://yandex.ru/maps/org/1/reviews/"
    site.vk_url = "https://vk.com/tparkprotva"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    html = client.get("/contacts/").content.decode()
    assert "Ежедневно, 10:00–18:00" in html
    assert "rtext=~54.956545,36.769595" in html
    assert "54.956545, 36.769595" in html
    assert "Оставить отзыв" in html and "https://vk.com/tparkprotva" in html
    main = html[html.index("<main") : html.index("</main>")]
    assert main.count("+7 (902) 985-65-94") == 1  # номер больше не дублируется кнопкой


def test_contacts_page_without_coordinates_has_no_routes(client):
    site = SiteSettings.load()
    site.latitude = site.longitude = None
    site.reviews_url = ""
    site.save()
    html = client.get("/contacts/").content.decode()
    assert "rtext=" not in html and "Оставить отзыв" not in html


def test_contacts_page_embeds_yandex_map_only_when_set(client):
    site = SiteSettings.load()
    assert "<iframe" not in client.get("/contacts/").content.decode()
    site.map_embed_url = "https://yandex.ru/map-widget/v1/?um=constructor%3Aabc&source=constructor"
    site.save()
    html = client.get("/contacts/").content.decode()
    assert 'src="https://yandex.ru/map-widget/v1/?um=constructor%3Aabc&amp;source=constructor"' in html


def test_reviews_page_header_cta_and_tones(client):
    site = SiteSettings.load()
    for i in range(3):
        Review.objects.create(text=f"<p>Отзыв {i}</p>", link="https://yandex.ru/maps/org/1/reviews/")
    html = client.get("/reviews/").content.decode()
    assert "3 отзыва" in html and "Гость Т-Парка" in html and "Яндекс Карты" in html
    assert re.findall(r"review-tone-(\w+)", html) == ["green", "warm", "heather"]  # цвета по кругу
    assert "Оставить отзыв" not in html  # без ссылки на Яндекс Карты кнопок нет
    site.reviews_url = "https://yandex.ru/maps/org/t_park/1/reviews/"
    site.save()
    html = client.get("/reviews/").content.decode()
    assert "Оставить отзыв" in html and "Все отзывы на Яндекс Картах" in html


def test_home_shows_reviews_carousel(client):
    assert "Отзывы гостей" not in client.get("/").content.decode()
    Review.objects.create(text="<p>Классно</p>")
    Review.objects.create(text="<p>Скрытая</p>", is_published=False)
    Review.objects.create(text="<p>Отлично</p>")
    html = client.get("/").content.decode()
    assert "Отзывы гостей" in html and "Классно" in html and "Скрытая" not in html
    # В карусели цвета чередуются по карточкам; кнопки — свои (на ПК по бокам, на телефоне под карточками со счётчиком).
    assert re.findall(r"review-tone-(\w+)", html) == ["green", "warm"]
    assert "js-carousel-prev" in html and "js-carousel-next" in html and "js-carousel-counter" in html
