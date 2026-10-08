import pytest

from apps.catalog.models import Category, Service
from apps.core.models import InfoPage

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
    assert "<title>Байдарки — Т-Парк</title>" in html
    assert 'name="description" content="Сплавы по Протве для всей семьи"' in html
    assert 'property="og:image" content="http://testserver/media/' in html


def test_favicon_redirects_to_static(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"].endswith("img/favicon.ico")
