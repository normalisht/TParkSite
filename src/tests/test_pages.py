import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
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
    html = client.get(category.get_absolute_url()).content.decode().replace("\u00a0", " ")
    assert "Описание сплавов" in html
    assert with_page.get_absolute_url() in html
    # Цена разбита по слешу: перенос только между ценой и единицей.
    assert '<span class="inline-block whitespace-nowrap">2000 ₽</span>' in html
    assert (
        '<span class="js-price-unit group/price inline-block data-wrapped:block"><span class="group-data-wrapped/price:hidden">/ </span>человек</span>'
        in html
    )
    assert "Весло включено" in html
    assert "Скрытая услуга" not in html
    assert "swiper-slide" in html
    # Полноэкранный просмотр открывает оригинал фото.
    assert f'data-full="{category.photos.get().full.url}"' in html
    # Услуга со страницей — карточкой, без страницы — в списке «Ещё услуги».
    cards, rows = html.split("Услуги и цены</h2>")[1].split("Ещё услуги")
    assert "Однодневный сплав" in cards and "Аренда байдарки" not in cards
    assert "Аренда байдарки" in rows


def test_category_page_cta_and_related(client, category, make_image):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    group = CategoryGroup.objects.create(name="Активный отдых")
    neighbour = Category.objects.create(name="Походы", is_published=True)
    draft = Category.objects.create(name="Черновик", is_published=False)
    group.categories.add(category, neighbour, draft)
    service = Service.objects.create(name="Сплав", short_description="<p>Коротко&nbsp;о главном</p>", has_page=True)
    ServicePhoto.objects.create(service=service, image=make_image(), order=0)
    CategoryService.objects.create(category=category, service=service)
    html = client.get(category.get_absolute_url()).content.decode()
    assert "Забронировать или задать вопрос" in html
    assert "Другие категории" in html and neighbour.get_absolute_url() in html
    assert draft.get_absolute_url() not in html
    assert "Коротко о главном" in html
    assert "Ещё услуги" not in html


def test_category_page_prices_anchor(client, category):
    service = Service.objects.create(name="Однодневный сплав", price="2000", has_page=True)
    CategoryService.objects.create(category=category, service=service)
    html = client.get(category.get_absolute_url()).content.decode()
    # Секция цен — цель якоря (с отступом под липкую шапку); кнопки «К ценам» в шапке нет.
    assert re.search(r'<section id="prices" class="[^"]*scroll-mt-20', html)
    assert "К ценам" not in html


def test_category_page_without_services_has_no_prices_anchor(client, category):
    html = client.get(category.get_absolute_url()).content.decode()
    assert 'id="prices"' not in html
    assert 'href="#prices"' not in html


def test_category_related_is_strip_on_phone(client, category):
    group = CategoryGroup.objects.create(name="Активный отдых")
    neighbour = Category.objects.create(name="Походы", is_published=True)
    group.categories.add(category, neighbour)
    html = client.get(category.get_absolute_url()).content.decode()
    related = html.split("Другие категории</h2>")[1].split("</section>")[0]
    # На телефоне — горизонтальная лента, с sm — сетка; карточка в обёртке заданной ширины.
    assert "scroll-strip" in related and "sm:grid-cols-2" in related
    assert re.search(
        r'<div class="w-\[44%\] [^"]*sm:w-auto">\s*<a href="' + re.escape(neighbour.get_absolute_url()), related
    )


def test_category_hero_photo_is_wide_on_phone(client, category):
    html = client.get(category.get_absolute_url()).content.decode()
    assert "aspect-[16/9]" in html and "lg:aspect-[3/2]" in html


def test_category_hero_opens_full_photo(client, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True)
    photo = CategoryPhoto.objects.create(category=category, image=make_image(), order=0)
    second = CategoryPhoto.objects.create(category=category, image=make_image("second.jpg"), order=1)
    html = client.get(category.get_absolute_url()).content.decode()
    # Шапка — первое фото, остальные листаются следом; первое не дублируется.
    assert html.count(f'href="{photo.full.url}" class="glightbox') == 1
    assert f'<a href="{second.full.url}" class="glightbox" data-gallery="category" hidden>' in html

    category.preview = make_image("preview.jpg")
    category.save()
    html = client.get(category.get_absolute_url()).content.decode()
    assert f'<a href="{category.preview.url}" class="glightbox block cursor-zoom-in" data-gallery="category">' in html
    assert f'<a href="{photo.full.url}" class="glightbox" data-gallery="category" hidden>' in html


def test_category_hero_srcset_up_to_1080(client, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True, preview=make_image(size=(1080, 720)))
    html = client.get(category.get_absolute_url()).content.decode()
    hero = html.split('data-gallery="category">')[1].split("</a>")[0]
    assert re.search(r'srcset="[^"]+\.avif 640w, [^"]+\.avif 1080w" sizes="\(min-width: 1152px\) 536px', hero)
    assert 'fetchpriority="high"' in hero and 'width="1080" height="720"' in hero


def test_category_page_without_services(client):
    category = Category.objects.create(name="Утренники", description="<p>Скоро</p>", is_published=True)
    html = client.get(category.get_absolute_url()).content.decode()
    assert "Скоро" in html
    assert "Услуги и цены" not in html
    assert "Другие категории" not in html


def test_unpublished_category_is_404(client):
    category = Category.objects.create(name="Черновик", is_published=False)
    assert client.get(category.get_absolute_url()).status_code == 404


def test_service_page(client):
    service = Service.objects.create(name="Сплав", description="<p>Полное описание</p>", price="2000", has_page=True)
    response = client.get(service.get_absolute_url())
    assert response.status_code == 200
    assert "Полное описание" in response.content.decode()


def test_service_page_booking_card_and_related(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    category = Category.objects.create(name="Сплавы", is_published=True)
    services = [
        Service.objects.create(name=name, price="2000", price_unit="человек", has_page=has_page)
        for name, has_page in [("Сплав", True), ("Сплав ночной", True), ("Аренда весла", False)]
    ]
    for order, service in enumerate(services):
        CategoryService.objects.create(category=category, service=service, order=order)
    html = client.get(services[0].get_absolute_url()).content.decode()
    assert "Стоимость" in html
    assert "tel:" in html.split("<aside")[1].split("</aside>")[0]
    related = html.split("Ещё в категории «Сплавы»")[1]
    assert services[1].get_absolute_url() in related
    assert services[0].get_absolute_url() not in related
    assert "Аренда весла" not in related


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


def test_about_founder_text_in_details(client):
    site = SiteSettings.load()
    site.founder_text = "<ul><li>Педагог-биография</li></ul>"
    site.save()
    html = client.get("/about/").content.decode()
    details = re.search(r"<details\b.*?</details>", html, re.DOTALL)
    assert details, "биография должна быть под <details>"
    assert "Педагог-биография" in details.group(0)
    assert re.search(r"<summary\b[^>]*>.*?Полная биография.*?</summary>", details.group(0), re.DOTALL)
    # Раскрытие анимирует site.js (data-smooth): высота обёртки текста, без JS — обычный <details>.
    assert re.match(r"<details[^>]*\bdata-smooth\b", details.group(0))
    assert "<div data-details-body>" in details.group(0)


def test_about_without_founder_text_has_no_details(client):
    site = SiteSettings.load()
    site.founder_text = ""
    site.save()
    assert "<details" not in client.get("/about/").content.decode()


def test_about_hides_unpublished_safety_page(client):
    site = SiteSettings.load()
    site.safety_page = InfoPage.objects.create(title="Правила", body="<p>x</p>", is_published=False)
    site.save()
    assert site.safety_page.get_absolute_url() not in client.get("/about/").content.decode()


def _footer(client):
    html = client.get("/").content.decode()
    return html[html.index("<footer") : html.index("</footer>")]


@pytest.mark.parametrize(
    ("field", "title"),
    [("privacy_page", "Политика конфиденциальности"), ("safety_page", "Правила безопасности")],
)
def test_footer_legal_link_only_when_published(client, field, title):
    page = InfoPage.objects.create(title=title, body="<p>x</p>")
    site = SiteSettings.load()
    setattr(site, field, page)
    site.save()
    footer = _footer(client)
    assert f'href="{page.get_absolute_url()}"' in footer
    assert title in footer

    page.is_published = False
    page.save()
    footer = _footer(client)
    assert page.get_absolute_url() not in footer
    assert title not in footer


def test_footer_legal_links_without_pages(client):
    footer = _footer(client)
    assert "Политика конфиденциальности" not in footer
    assert "Правила безопасности" not in footer
    assert " · " not in footer


def test_footer_legal_links_separated(client):
    site = SiteSettings.load()
    site.privacy_page = InfoPage.objects.create(title="Политика конфиденциальности", body="<p>x</p>")
    site.safety_page = InfoPage.objects.create(title="Правила безопасности", body="<p>y</p>")
    site.save()
    assert _footer(client).count("·") == 2


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


def test_reviews_page_photo_strip(client, make_image):
    assert "Как это выглядит" not in client.get("/reviews/").content.decode()
    GalleryPhoto.objects.create(image=make_image(), caption="Закат")
    html = client.get("/reviews/").content.decode()
    assert "Как это выглядит" in html and 'alt="Закат"' in html


def _strip_gallery(make_image, count):
    """count фото с подписями «Фото 0…»: по alt видно, какие попали в полосу."""
    first = GalleryPhoto.objects.create(image=make_image(), caption="Фото 0")
    GalleryPhoto.objects.bulk_create(
        [GalleryPhoto(image=first.image.name, caption=f"Фото {i}", order=i) for i in range(1, count)]
    )


def _strip_alts(html):
    strip = html.split("Как это выглядит")[1].split("</section>")[0]
    return re.findall(r'alt="(Фото \d+)"', strip)


@pytest.mark.parametrize("url", ["/", "/about/", "/reviews/"])
def test_photo_strip_rotates_daily(client, make_image, monkeypatch, url):
    _strip_gallery(make_image, 15)
    seen = set()
    for shift in range(10):
        day = date(2026, 10, 1) + timedelta(days=shift)
        monkeypatch.setattr("django.utils.timezone.localdate", lambda day=day: day)
        alts = _strip_alts(client.get(url).content.decode())
        assert len(alts) == GalleryPhoto.STRIP_SIZE
        assert alts == sorted(alts, key=lambda alt: int(alt.split()[1]))  # порядок — как в галерее
        seen.update(alts)
    assert len(seen) > GalleryPhoto.STRIP_SIZE  # не всегда первые шесть


def test_photo_strip_differs_between_pages(client, make_image, monkeypatch):
    _strip_gallery(make_image, 15)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 10, 11))
    home, about = (_strip_alts(client.get(url).content.decode()) for url in ("/", "/about/"))
    assert home != about


def test_photo_strip_stable_within_day_keeps_304(client, make_image):
    _strip_gallery(make_image, 15)
    first = client.get("/")
    assert first.has_header("ETag")
    assert client.get("/", HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


def test_gallery_page(client, make_image):
    GalleryPhoto.objects.create(image=make_image(), caption="Закат")
    html = client.get("/gallery/").content.decode()
    assert "glightbox" in html and "Закат" in html


def test_gallery_thumbs_avif_srcset_and_light_lightbox(client, make_image):
    photo = GalleryPhoto.objects.create(image=make_image(), caption='Закат "у реки"')
    html = client.get("/gallery/").content.decode()
    assert f'<a href="{photo.full.url}" class="glightbox' in html
    assert re.search(
        r'<source type="image/avif" srcset="[^"]+\.avif 400w, [^"]+\.avif 600w" sizes="\(min-width: 1152px\) 271px',
        html,
    )
    assert 'alt="Закат &quot;у реки&quot;"' in html


def test_category_page_survives_missing_photo_file(client, category, media_root):
    photo = category.photos.get()
    (media_root / photo.image.name).unlink()
    response = client.get(category.get_absolute_url())
    assert response.status_code == 200
    assert 'src=""' not in response.content.decode()


def _make_gallery(make_image, count):
    first = GalleryPhoto.objects.create(image=make_image())
    GalleryPhoto.objects.bulk_create([GalleryPhoto(image=first.image.name) for _ in range(count - 1)])


def _gallery_anchors(html):
    return re.findall(r'<a href="[^"]*" class="glightbox[^>]*>', html)


def test_gallery_shows_first_page_and_autoloads_rest(client, make_image):
    _make_gallery(make_image, 30)
    html = client.get("/gallery/").content.decode()
    anchors = _gallery_anchors(html)
    assert len(anchors) == 30  # просмотр листает всю галерею
    assert [" hidden" in a for a in anchors] == [False] * 24 + [True] * 6
    assert 'x-data="{ shown: 24, total: 30 }"' in html
    assert "data-gallery-more" in html and "IntersectionObserver" in html
    assert "Показать ещё" not in html


def test_gallery_without_autoload_when_one_page(client, make_image):
    _make_gallery(make_image, 20)
    html = client.get("/gallery/").content.decode()
    anchors = _gallery_anchors(html)
    assert len(anchors) == 20 and not any(" hidden" in a for a in anchors)
    assert "data-gallery-more" not in html


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


MAP_URL = "https://yandex.ru/map-widget/v1/org/t_park/17031236197/"


def _set_map(url: str, yandex_maps_url: str = "") -> None:
    site = SiteSettings.load()
    site.map_embed_url, site.yandex_maps_url = url, yandex_maps_url
    site.save()


@pytest.mark.django_db
def test_contacts_map_loads_on_click(client):
    _set_map(MAP_URL)
    html = client.get("/contacts/").content.decode()
    assert "Показать карту" in html
    template_at = html.index('<template x-if="map">')
    assert html.index("<iframe") > template_at  # iframe только внутри <template>: до клика браузер его не грузит
    assert html.count("<iframe") == 1


@pytest.mark.django_db
def test_contacts_map_has_no_js_fallback(client):
    _set_map(MAP_URL, "https://yandex.ru/maps/org/t_park/17031236197/")
    html = client.get("/contacts/").content.decode()
    assert "<noscript>" not in html
    link = html.split("Открыть в Яндекс Картах", 1)[0].rsplit("<a ", 1)[1]
    assert 'href="https://yandex.ru/maps/org/t_park/17031236197/"' in link
    assert "btn-ghost" in link and 'rel="noopener"' in link


@pytest.mark.django_db
def test_contacts_without_map(client):
    _set_map("")
    html = client.get("/contacts/").content.decode()
    assert "Показать карту" not in html and "<iframe" not in html
    assert "md:max-w-xl" in html


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


def test_not_found_page(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    response = client.get("/net-takoi-stranitsy/")
    assert response.status_code == 404
    content = response.content.decode()
    assert "Кажется, вы сошли с тропы" in content
    assert 'aria-label="Ошибка 404"' in content
    assert "+7 (902) 985-65-94" in content


def test_server_error_page_renders_without_context():
    from django.template.loader import render_to_string

    content = render_to_string("500.html")
    assert "Что-то пошло не так" in content
    assert "error-tree-fallen" in content


def test_service_card_picture_and_slider_srcset(client, make_image):
    category = Category.objects.create(name="Сплавы", is_published=True)
    service = Service.objects.create(name="Сплав", has_page=True)
    ServicePhoto.objects.create(service=service, image=make_image(size=(1600, 900)))
    CategoryPhoto.objects.create(category=category, image=make_image(size=(1600, 900)))
    CategoryService.objects.create(category=category, service=service)
    html = client.get(category.get_absolute_url()).content.decode()
    card = html.split("Услуги и цены</h2>")[1]
    # Телефон — квадрат row (336×336), с sm — card 640×480.
    assert '<picture><source media="(min-width: 640px)" type="image/avif" srcset="' in card
    slider = html.split("js-slider")[1]
    sizes = r'sizes="\(min-width: 1152px\) 1120px, calc\(100vw - 32px\)"'
    assert re.search(r'<source type="image/avif" srcset="[^"]+\.avif 800w, [^"]+\.avif 1600w" ' + sizes, slider)
    assert re.search(r'<img src="[^"]+\.webp" srcset="[^"]+\.webp 800w, [^"]+\.webp 1600w" ' + sizes, slider)
    html = client.get(service.get_absolute_url()).content.decode()
    assert 'sizes="(min-width: 1152px) 752px, (min-width: 1024px) calc(100vw - 400px), calc(100vw - 32px)"' in html


def test_service_related_skips_same_name_variants(client):
    category = Category.objects.create(name="Высота", is_published=True)
    services = [
        Service.objects.create(name=name, has_page=True)
        for name in ["Виа-феррата", "виа-феррата", "Скалодром", "Скалодром", "Тарзанка"]
    ]
    for order, service in enumerate(services):
        CategoryService.objects.create(category=category, service=service, order=order)
    related = client.get(services[0].get_absolute_url()).content.decode().split("Ещё в категории")[1]
    assert services[1].get_absolute_url() not in related  # тот же аттракцион другим вариантом
    assert services[2].get_absolute_url() in related
    assert services[3].get_absolute_url() not in related  # одинаковые названия — одна карточка
    assert services[4].get_absolute_url() in related


def _category_with_services(count):
    category = Category.objects.create(name="Высота", is_published=True)
    services = [Service.objects.create(name=f"Услуга {i}", has_page=True) for i in range(count)]
    for order, service in enumerate(services):
        CategoryService.objects.create(category=category, service=service, order=order)
    return services


def _related_urls(html):
    return re.findall(r'<a href="(/service/[^"]+)" class="card', html.split("Ещё в категории")[1])


def test_related_services_rotate_daily(client, monkeypatch):
    services = _category_with_services(8)
    current = services[0]
    urls_in_order = [s.get_absolute_url() for s in services]
    seen = set()
    for shift in range(20):
        day = date(2026, 10, 1) + timedelta(days=shift)
        monkeypatch.setattr("django.utils.timezone.localdate", lambda day=day: day)
        urls = _related_urls(client.get(current.get_absolute_url()).content.decode())
        assert len(urls) == 3
        assert current.get_absolute_url() not in urls
        positions = [urls_in_order.index(url) for url in urls]
        assert positions == sorted(positions)  # порядок — как в категории
        seen.update(urls)
    assert seen == set(urls_in_order[1:])  # ссылки получают все, не только первые три


def test_related_services_differ_between_services(client, monkeypatch):
    services = _category_with_services(8)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: date(2026, 10, 11))
    shown = [frozenset(_related_urls(client.get(s.get_absolute_url()).content.decode())) for s in services[4:]]
    assert len(set(shown)) > 1  # без ротации все четыре показывают первые три услуги


def test_related_services_stable_within_day(client):
    services = _category_with_services(8)
    first = client.get(services[0].get_absolute_url())
    assert client.get(services[0].get_absolute_url(), HTTP_IF_NONE_MATCH=first["ETag"]).status_code == 304


def test_whatsapp_prefilled_with_service_name(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594", is_whatsapp=True)
    service = Service.objects.create(name="Виа-феррата", has_page=True)
    html = client.get(service.get_absolute_url()).content.decode()
    hello = "%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5"  # «Здравствуйте»
    topic = "%C2%AB%D0%92%D0%B8%D0%B0-%D1%84%D0%B5%D1%80%D1%80%D0%B0%D1%82%D0%B0%C2%BB"  # «Виа-феррата»
    links = re.findall(r'href="(https://wa\.me/[^"]*)"', html)
    assert links and all(link.startswith(f"https://wa.me/79029856594?text={hello}") for link in links)
    assert all(topic in link for link in links)
    # На страницах без темы — ссылка без текста.
    assert set(re.findall(r'href="(https://wa\.me/[^"]*)"', client.get("/contacts/").content.decode())) == {
        "https://wa.me/79029856594"
    }


def test_whatsapp_topic_on_category_and_upcoming_event_only(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594", is_whatsapp=True)
    category = Category.objects.create(name="Сплавы", is_published=True)
    assert "?text=" in client.get(category.get_absolute_url()).content.decode()
    today = timezone.localdate()
    upcoming = Event.objects.create(title="Сплав", date=today + timedelta(days=3))
    past = Event.objects.create(title="Поход", date=today - timedelta(days=3), show_after_date=True)
    assert "?text=" in client.get(upcoming.get_absolute_url()).content.decode()
    assert "?text=" not in client.get(past.get_absolute_url()).content.decode()
