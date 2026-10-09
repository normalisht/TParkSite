import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Category, CategoryGroup
from apps.content.models import Event, Review
from apps.core.models import Phone, SiteSettings
from apps.core.seo import plaintext

pytestmark = pytest.mark.django_db


def test_home_on_empty_db(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Скоро здесь появятся наши услуги" in response.content.decode()


def test_home_shows_only_published_categories(client):
    group = CategoryGroup.objects.create(name="Активный отдых")
    visible = Category.objects.create(name="Байдарки", is_published=True)
    hidden = Category.objects.create(name="Скрытая", is_published=False)
    group.categories.add(visible, hidden)
    CategoryGroup.objects.create(name="Пустая группа")
    html = client.get("/").content.decode()
    assert "Активный отдых" in html and "Байдарки" in html
    assert "Скрытая" not in html
    assert "Пустая группа" not in html


@pytest.mark.parametrize("show", [True, False])
def test_home_upcoming_events_toggle(client, show):
    site = SiteSettings.load()
    site.home_show_events = show
    site.save()
    today = timezone.localdate()
    Event.objects.create(title="Сплав выходного дня", date=today + timedelta(days=3))
    Event.objects.create(title="Было", date=today - timedelta(days=3), show_after_date=True)
    html = client.get("/").content.decode()
    assert ("Ближайшие мероприятия" in html) is show
    assert ("Сплав выходного дня" in html) is show
    assert "Было" not in html


def test_home_hero_hours_and_route(client):
    site = SiteSettings.load()
    site.address = "село Восход"
    site.opening_hours = "Mo-Su 10:00-18:00"
    site.latitude, site.longitude = 54.9, 36.6
    site.save()
    Phone.objects.create(settings=site, number="9029856594")
    html = client.get("/").content.decode()
    assert "Ежедневно, 10:00–18:00" in html
    assert "Как добраться" in html and "rtext=~54.900000,36.600000" in html
    assert "Приезжайте в Т-Парк" in html


def test_home_hides_unpublished_group(client):
    category = Category.objects.create(name="Байдарки", is_published=True)
    CategoryGroup.objects.create(name="Скрытая группа", is_published=False).categories.add(category)
    html = client.get("/").content.decode()
    assert "Скрытая группа" not in html
    assert "Байдарки" not in html


def test_contacts_in_footer_and_contact_button(client):
    site = SiteSettings.load()
    site.address = "село Восход"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    html = client.get("/").content.decode()
    assert "село Восход" in html
    assert "tel:+79029856594" in html
    assert "https://wa.me/79029856594" in html
    assert "t.me/+7" not in html  # Telegram не отмечен ни у одного номера


def test_home_survives_missing_preview_file(client, make_image, media_root):
    group = CategoryGroup.objects.create(name="Группа")
    category = Category.objects.create(name="Без файла", is_published=True, preview=make_image())
    group.categories.add(category)
    (media_root / category.preview.name).unlink()
    response = client.get("/")
    assert response.status_code == 200
    assert "Без файла" in response.content.decode()


def test_404_page(client):
    response = client.get("/net-takoy-stranicy/")
    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()


def test_plaintext_strips_and_truncates():
    assert plaintext("<p>Привет,&nbsp;<b>мир</b></p>") == "Привет, мир"
    long = "<p>" + "слово " * 100 + "</p>"
    result = plaintext(long)
    assert len(result) <= 160 and result.endswith("…")


def _preview_imgs(html: str) -> list[str]:
    return [tag for tag in re.findall(r"<img [^>]*>", html) if "catalog/previews" in tag]


def test_home_first_screen_cards_load_eagerly(client, make_image):
    """Без фото в шапке LCP — первая карточка: первый ряд первой группы без lazy, первая — с высоким приоритетом."""
    first, second = CategoryGroup.objects.create(name="Первая"), CategoryGroup.objects.create(name="Вторая")
    for i in range(4):
        first.categories.add(Category.objects.create(name=f"Первая {i}", is_published=True, preview=make_image()))
    second.categories.add(Category.objects.create(name="Вторая 0", is_published=True, preview=make_image()))
    imgs = _preview_imgs(client.get("/").content.decode())
    assert len(imgs) == 5
    assert ['loading="lazy"' in tag for tag in imgs] == [False, False, False, True, True]
    assert ['fetchpriority="high"' in tag for tag in imgs] == [True, False, False, False, False]


def test_home_cards_lazy_when_hero_photo_set(client, make_image):
    site = SiteSettings.load()
    site.about_photo = make_image("hero.jpg")
    site.save()
    group = CategoryGroup.objects.create(name="Группа")
    group.categories.add(Category.objects.create(name="Байдарки", is_published=True, preview=make_image()))
    html = client.get("/").content.decode()
    assert html.count('fetchpriority="high"') == 1  # только фото в шапке
    assert all('loading="lazy"' in tag for tag in _preview_imgs(html))


def test_home_swiper_css_not_render_blocking(client):
    """Карусель отзывов внизу страницы: стили Swiper — в body перед ней, не в head; без отзывов Swiper не нужен."""
    html = client.get("/").content.decode()
    assert "swiper-bundle" not in html
    Review.objects.create(text="<p>Классно</p>")
    html = client.get("/").content.decode()
    head, body = html.split("</head>")
    assert "swiper-bundle" not in head
    assert body.index("swiper-bundle.min.css") < body.index("js-carousel-wrap")
    assert "swiper-bundle.min.js" in body


LOW_CONTRAST_TEXT = re.compile(r"\btext-ink/([0-9]+)\b")


def test_no_low_contrast_gray_text():
    """Серый текст — не светлее ink/65: ink/55 и светлее не проходят контраст WCAG 4.5:1 на белом."""
    root = Path(settings.BASE_DIR)
    files = [
        *(root / "templates").rglob("*.html"),
        root / "tailwind" / "source.css",
        *(root / "static" / "js").glob("*.js"),
    ]
    offenders = [
        f"{path.relative_to(root)}: text-ink/{match.group(1)}"
        for path in files
        for match in LOW_CONTRAST_TEXT.finditer(path.read_text())
        if int(match.group(1)) < 65
    ]
    assert offenders == []
