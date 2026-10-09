import json
import re

import pytest

from apps.catalog.models import Category, CategoryService, Service
from apps.content.models import GalleryPhoto, Review
from apps.core.models import InfoPage, Phone, SiteSettings

pytestmark = pytest.mark.django_db


def test_sitemap_lists_only_public_pages(client):
    Category.objects.create(name="Открытая", is_published=True)
    Category.objects.create(name="Закрытая", is_published=False)
    Service.objects.create(name="Со страницей", has_page=True)
    Service.objects.create(name="Без страницы")
    InfoPage.objects.create(title="Правила")
    xml = client.get("/sitemap.xml").content.decode()
    assert "/category/otkrytaia/" in xml
    assert "zakrytaia" not in xml
    assert "/service/so-stranitsei/" in xml
    assert "bez-stranitsy" not in xml
    assert "/info/pravila/" in xml
    assert "/events/" in xml and "/about/" in xml


def test_robots(client):
    response = client.get("/robots.txt")
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "Disallow: /admin/" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_category_meta(client, make_image):
    category = Category.objects.create(
        name="Байдарки", description="<p>Сплавы по Протве для всей семьи</p>", is_published=True, preview=make_image()
    )
    html = client.get(category.get_absolute_url()).content.decode()
    assert "<title>Байдарки — Т-Парк, Калужская область</title>" in html
    assert 'name="description" content="Сплавы по Протве для всей семьи"' in html
    assert 'property="og:image" content="http://testserver/media/' in html


def test_favicon_redirects_to_static(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"].endswith("img/favicon.ico")


def ld_nodes(html: str) -> dict:
    raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1)
    return {node["@type"]: node for node in json.loads(raw)["@graph"]}


def test_custom_seo_fields_win(client):
    category = Category.objects.create(
        name="Байдарки",
        description="<p>Текст страницы</p>",
        seo_title="Сплавы на байдарках по Угре",
        seo_description="Однодневные сплавы для семей и компаний",
        is_published=True,
    )
    html = client.get(category.get_absolute_url()).content.decode()
    assert "<title>Сплавы на байдарках по Угре</title>" in html
    assert 'name="description" content="Однодневные сплавы для семей и компаний"' in html


def test_title_suffix_from_settings(client):
    site = SiteSettings.load()
    site.seo_title_suffix = "Т-Парк, село Восход"
    site.save()
    page = InfoPage.objects.create(title="Правила")
    assert "<title>Правила — Т-Парк, село Восход</title>" in client.get(page.get_absolute_url()).content.decode()


def test_static_pages_have_own_titles_and_descriptions(client):
    pages = {}
    for url in ["/", "/events/", "/about/", "/reviews/", "/gallery/", "/contacts/"]:
        html = client.get(url).content.decode()
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        description = re.search(r'name="description" content="(.*?)"', html).group(1)
        pages[url] = (title, description)
    assert len({title for title, _ in pages.values()}) == len(pages)
    assert len({description for _, description in pages.values()}) == len(pages)
    # Тексты по умолчанию заполнила миграция core.0006_seo_content.
    assert pages["/"][0] == "Т-Парк — верёвочный парк и активный отдых под Обнинском"
    assert "село Восход" in pages["/contacts/"][1]


def test_static_page_seo_from_settings(client):
    site = SiteSettings.load()
    site.seo_gallery_title = "Фото тренинг-парка"
    site.seo_gallery_description = "Лучшие кадры сезона"
    site.save()
    html = client.get("/gallery/").content.decode()
    assert "<title>Фото тренинг-парка</title>" in html
    assert 'name="description" content="Лучшие кадры сезона"' in html


def test_canonical_drops_query(client):
    html = client.get("/about/?utm_source=vk").content.decode()
    assert '<link rel="canonical" href="http://testserver/about/">' in html


def test_no_canonical_on_404(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert 'rel="canonical"' not in response.content.decode()


def test_home_local_business(client):
    site = SiteSettings.load()
    site.vk_url = "https://vk.com/tpark"
    site.yandex_maps_url = "https://yandex.ru/maps/org/tpark/123/"
    site.latitude, site.longitude = "54.9", "36.6"
    site.save()
    Phone.objects.create(settings=site, number="9029856594")
    business = ld_nodes(client.get("/").content.decode())["LocalBusiness"]
    assert business["address"]["addressRegion"] == "Калужская область"
    assert business["address"]["addressLocality"] == "Жуковский район, село Восход"
    assert business["telephone"] == ["+79029856594"]
    assert business["sameAs"] == ["https://vk.com/tpark", "https://yandex.ru/maps/org/tpark/123/"]
    assert business["geo"] == {"@type": "GeoCoordinates", "latitude": 54.9, "longitude": 36.6}


def test_default_address(db):
    assert SiteSettings.load().address == "Калужская область, Жуковский район, село Восход"


def test_category_breadcrumbs_and_offers(client):
    category = Category.objects.create(name="Сплавы", is_published=True)
    priced = Service.objects.create(name="Сплав", price="2 000", price_unit="человек", has_page=True)
    contract = Service.objects.create(name="Корпоратив", price="договорная")
    for order, service in enumerate([priced, contract]):
        CategoryService.objects.create(category=category, service=service, order=order)
    html = client.get(category.get_absolute_url()).content.decode()
    nodes = ld_nodes(html)
    crumbs = nodes["BreadcrumbList"]["itemListElement"]
    assert crumbs[0] == {"@type": "ListItem", "position": 1, "name": "Главная", "item": "http://testserver/"}
    assert crumbs[1] == {"@type": "ListItem", "position": 2, "name": "Сплавы"}
    assert 'aria-label="Хлебные крошки"' in html
    first, second = (item["item"] for item in nodes["ItemList"]["itemListElement"])
    assert first["offers"]["price"] == "2000"
    assert first["offers"]["priceCurrency"] == "RUB"
    assert first["offers"]["priceSpecification"]["unitText"] == "человек"
    assert first["url"] == f"http://testserver{priced.get_absolute_url()}"
    assert "offers" not in second and "url" not in second


def test_service_page_ld(client):
    category = Category.objects.create(name="Сплавы", is_published=True)
    service = Service.objects.create(name="Сплав", price="1500", has_page=True)
    CategoryService.objects.create(category=category, service=service)
    nodes = ld_nodes(client.get(service.get_absolute_url()).content.decode())
    assert [c["name"] for c in nodes["BreadcrumbList"]["itemListElement"]] == ["Главная", "Сплавы", "Сплав"]
    assert nodes["Service"]["provider"] == {"@id": nodes["LocalBusiness"]["@id"]}
    assert nodes["Service"]["offers"]["price"] == "1500"


def test_sitemap_lastmod(client):
    Category.objects.create(name="Открытая", is_published=True)
    assert "<lastmod>" in client.get("/sitemap.xml").content.decode()


def test_robots_clean_param(client):
    body = client.get("/robots.txt").content.decode()
    assert "Disallow: /healthz/" in body
    assert "Clean-param: utm_source&utm_medium&utm_campaign" in body


def test_www_redirects_to_canonical_host(client, settings):
    settings.CANONICAL_HOST = "t-camp.ru"
    settings.ALLOWED_HOSTS = ["t-camp.ru", "www.t-camp.ru", "localhost"]
    response = client.get("/about/?a=1", HTTP_HOST="www.t-camp.ru")
    assert response.status_code == 301
    assert response["Location"] == "https://t-camp.ru/about/?a=1"
    assert client.get("/about/", HTTP_HOST="t-camp.ru").status_code == 200
    assert client.get("/healthz/", HTTP_HOST="localhost").status_code == 200


def test_metrika_and_verification(client, settings):
    html = client.get("/").content.decode()
    assert "mc.yandex.ru" not in html
    assert "yandex-verification" not in html
    site = SiteSettings.load()
    site.yandex_metrika_id = "12345678"
    site.yandex_verification = "abc123"
    site.google_verification = "g-456"
    site.save()
    html = client.get("/").content.decode()
    assert 'ym(12345678, "init"' in html
    assert '<meta name="yandex-verification" content="abc123">' in html
    assert '<meta name="google-site-verification" content="g-456">' in html
    settings.DEBUG = True
    assert "mc.yandex.ru" not in client.get("/").content.decode()


def test_default_og_image(client, make_image):
    html = client.get("/contacts/").content.decode()
    assert 'property="og:image"' not in html
    assert 'name="twitter:card" content="summary"' in html
    site = SiteSettings.load()
    site.og_image = make_image(size=(1300, 700))
    site.save()
    html = client.get("/contacts/").content.decode()
    assert 'property="og:image" content="http://testserver/media/' in html
    assert 'name="twitter:card" content="summary_large_image"' in html


def test_vendor_scripts_only_where_needed(client):
    assert "swiper-bundle" not in client.get("/contacts/").content.decode()
    assert "glightbox" not in client.get("/contacts/").content.decode()
    gallery = client.get("/gallery/").content.decode()
    assert "glightbox.min.js" in gallery and "swiper-bundle" not in gallery
    assert "swiper-bundle" not in client.get("/").content.decode()  # на главной Swiper — только для карусели отзывов
    Review.objects.create(text="<p>Классно</p>")
    assert "swiper-bundle.min.js" in client.get("/").content.decode()


def test_gallery_alt_fallback(client, make_image):
    GalleryPhoto.objects.create(image=make_image(), order=0)
    html = client.get("/gallery/").content.decode()
    assert 'alt="Т-Парк, Калужская область — фото 1"' in html


def test_empty_category_gets_own_description(client):
    category = Category.objects.create(name="Верёвочный парк", is_published=True)
    html = client.get(category.get_absolute_url()).content.decode()
    assert (
        'content="Верёвочный парк в Т-Парке: услуги и цены. Калужская область, Жуковский район, село Восход."' in html
    )


def test_fill_seo_content_fills_only_empty(db):
    from decimal import Decimal

    from apps.core.seo_content import fill_seo_content

    site = SiteSettings.load()
    site.seo_home_title = "Свой заголовок"
    site.save()
    rope = Category.objects.create(name="Верёвочный парк", slug="veriovochnyi-park")
    boats = Category.objects.create(name="Лодки", slug="lodochnaia-stantsiia", seo_title="Своё")
    other = Category.objects.create(name="Другое")
    fill_seo_content(SiteSettings, Category)
    site.refresh_from_db()
    assert site.seo_home_title == "Свой заголовок"
    assert site.seo_contacts_title == "Контакты Т-Парка — как добраться в село Восход"
    assert site.opening_hours == "Mo-Su 10:00-18:00"
    assert site.yandex_maps_url == "https://yandex.ru/maps/-/CXq0VZJk"
    assert (site.latitude, site.longitude, site.postal_code) == (Decimal("54.956545"), Decimal("36.769595"), "249191")
    rope.refresh_from_db()
    boats.refresh_from_db()
    other.refresh_from_db()
    assert rope.seo_title == "Верёвочный парк под Обнинском — цены | Т-Парк"
    assert boats.seo_title == "Своё" and boats.seo_description.startswith("Лодочная станция")
    assert other.seo_title == ""
