import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Category, CategoryGroup
from apps.content.models import Event, Review
from apps.core.models import InfoPage, Phone, SiteSettings
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
    assert 'Приезжайте в <span class="whitespace-nowrap">Т-Парк</span>' in html


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


def test_header_logo_is_lightweight(client):
    """В шапке — уменьшенный логотип (3× от 122×40), а не исходник 600×197: он грузится вместе с LCP-фото."""
    html = client.get("/").content.decode()
    assert re.search(r'<img src="/static/img/logo-header\.png" alt="Т-Парк" width="122" height="40"', html)
    logo = Path(settings.BASE_DIR) / "static/img/logo-header.png"
    assert logo.stat().st_size < 8 * 1024


def _header(html: str) -> str:
    return html.split("<header", 1)[1].split("</header>", 1)[0]


def test_header_shows_phone_on_desktop(client):
    site = SiteSettings.load()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    header = _header(client.get("/").content.decode())
    assert 'href="tel:+79029856594"' in header
    assert "+7 (902) 985-65-94" in header
    assert "https://wa.me/79029856594" in header
    assert "Тренинг-парк Дмитрия Сергеева" not in header


def test_header_services_dropdown_lists_published_categories(client):
    group = CategoryGroup.objects.create(name="Активный отдых")
    visible = Category.objects.create(name="Байдарки", is_published=True)
    hidden = Category.objects.create(name="Черновик", is_published=False)
    group.categories.add(visible, hidden)
    header = _header(client.get("/").content.decode())
    assert re.search(r'<button type="button"[^>]*aria-controls="services-menu"', header)
    panel = header.split('id="services-menu"', 1)[1].split("</nav>", 1)[0]
    assert "Активный отдых" in panel
    assert f'href="{visible.get_absolute_url()}"' in panel
    assert "Черновик" not in panel and hidden.get_absolute_url() not in panel
    assert "Все услуги" in panel


def test_header_services_is_plain_link_without_groups(client):
    header = _header(client.get("/").content.decode())
    assert 'aria-controls="services-menu"' not in header and 'id="services-menu"' not in header
    assert re.search(r'<a href="/"[^>]*>Услуги</a>', header)


def test_contact_button_yields_to_menu_and_footer(client):
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    html = client.get("/").content.decode()
    fab = re.search(r'<div [^>]*class="(contact-fab [^"]*)"', html).group(1)
    assert "lg:hidden" in fab and "md:hidden" not in fab
    # Меню помечает <html> классом menu-open — по нему кнопка прячется (tailwind/source.css).
    assert "toggle('menu-open', open)" in html
    # Подвал не прячется под кнопкой: снизу место под неё, на ПК — обычный отступ.
    assert "pb-20 lg:pb-5" in html.split("<footer", 1)[1]


def _contact_menu(html: str) -> str:
    return html.split('id="contact-menu"', 1)[1].split("</div>", 1)[0]


def test_contact_links_include_vk_and_max(client):
    site = SiteSettings.load()
    site.vk_url = "https://vk.com/tpark"
    site.save()
    Phone.objects.create(settings=site, number="9029856594")
    menu = _contact_menu(client.get("/").content.decode())
    assert 'href="https://vk.com/tpark"' in menu
    assert "MAX" not in menu  # ссылка не указана — кнопки нет
    site.max_url = "https://max.ru/u/tpark"
    site.save()
    html = client.get("/").content.decode()
    assert 'href="https://max.ru/u/tpark"' in _contact_menu(html)
    assert 'href="https://max.ru/u/tpark"' in html.split("<footer", 1)[1]
    assert 'href="https://max.ru/u/tpark"' in client.get("/contacts/").content.decode()


def test_home_categories_grid_on_phone(client):
    group = CategoryGroup.objects.create(name="Групповые приключения")
    for i in range(6):
        group.categories.add(Category.objects.create(name=f"Категория {i}", is_published=True))
    html = client.get("/").content.decode()
    section = html.split("Групповые приключения</h2>", 1)[1].split("</section>", 1)[0]
    assert "grid grid-cols-2" in section
    assert "overflow-x-auto" not in section


def test_category_card_shade_covers_card_on_phone(client):
    """На телефоне подпись бывает в три строки и начинается почти у верха — затемнение на всю высоту, с sm — на 3/4."""
    group = CategoryGroup.objects.create(name="Группа")
    group.categories.add(Category.objects.create(name="Дни рождения и выпускные", is_published=True))
    html = client.get("/").content.decode()
    assert re.search(r'<div class="absolute inset-x-0 bottom-0 h-full sm:h-3/4 bg-linear-to-t', html)


def _cookie_notice(html: str) -> str:
    return html.split('aria-label="Уведомление о cookie"', 1)[1].split("</section>", 1)[0]


def test_cookie_notice_with_metrika_links_to_privacy(client):
    site = SiteSettings.load()
    site.yandex_metrika_id = "12345"
    site.privacy_page = InfoPage.objects.create(title="Политика конфиденциальности", body="<p>x</p>")
    site.save()
    Phone.objects.create(settings=site, number="9029856594")
    html = client.get("/").content.decode()
    notice = _cookie_notice(html)
    assert "Мы используем cookie и Яндекс Метрику" in notice
    assert f'href="{site.privacy_page.get_absolute_url()}"' in notice
    assert "Понятно" in notice
    # Баннер скрыт до инициализации Alpine, а доступ к localStorage защищён от приватного режима.
    assert "x-cloak" in html.split('aria-label="Уведомление о cookie"', 1)[0].rsplit("<section", 1)[1]
    assert "cookie-ok" in html and "try" in html
    assert html.index("Уведомление о cookie") < html.index('class="contact-fab')
    # Класс нужен правилу в tailwind/source.css: баннер прячется, пока открыто мобильное меню.
    assert 'class="cookie-notice fixed ' in html


def test_cookie_notice_without_privacy_page_has_no_link(client):
    site = SiteSettings.load()
    site.yandex_metrika_id = "12345"
    site.save()
    notice = _cookie_notice(client.get("/").content.decode())
    assert "<a " not in notice
    assert "Понятно" in notice


def test_no_cookie_notice_without_metrika(client):
    html = client.get("/").content.decode()
    assert "Уведомление о cookie" not in html
    assert "cookie-ok" not in html


def test_contact_button_hidden_while_cookie_notice_open():
    css = (Path(settings.BASE_DIR) / "tailwind/source.css").read_text()
    assert "html.cookie-open .contact-fab { display: none; }" in css


def test_cookie_notice_hidden_while_menu_open():
    """Баннер не закрывает нижние пункты открытого мобильного меню."""
    css = (Path(settings.BASE_DIR) / "tailwind/source.css").read_text()
    assert "html.menu-open .cookie-notice { display: none; }" in css


def _footer(html: str) -> str:
    return html.split("<footer", 1)[1].split("</footer>", 1)[0]


def test_footer_lists_published_categories(client):
    published = Category.objects.create(name="Байдарки", is_published=True)
    draft = Category.objects.create(name="Черновик", is_published=False)
    CategoryGroup.objects.create(name="Вода", is_published=True).categories.add(published, draft)
    footer = _footer(client.get("/").content.decode())
    assert f'href="{published.get_absolute_url()}"' in footer
    assert "Байдарки" in footer
    assert "Черновик" not in footer
    assert "Услуги" in footer


def test_footer_hides_services_column_without_categories(client):
    assert "Услуги" not in _footer(client.get("/").content.decode())


def test_footer_shows_at_most_eight_categories_without_duplicates(client):
    categories = [Category.objects.create(name=f"Категория {i}", is_published=True) for i in range(10)]
    CategoryGroup.objects.create(name="Первая").categories.add(*categories[:6])
    CategoryGroup.objects.create(name="Вторая").categories.add(*categories[4:])
    footer = _footer(client.get("/").content.decode())
    assert len(re.findall(r'href="/category/[^"]+"', footer)) == 8


def test_footer_shows_opening_hours_on_any_page(client):
    site = SiteSettings.load()
    site.opening_hours = "Mo-Su 10:00-18:00"
    site.save()
    for url in ("/", "/about/", "/contacts/"):
        assert "Ежедневно, 10:00–18:00" in _footer(client.get(url).content.decode())
