"""Правила вёрстки, которые проверяются по исходникам шаблонов (браузерная проверка — tests/e2e)."""

import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.core.models import ContactChannel

TEMPLATES = Path(settings.BASE_DIR) / "templates"

# Шапка секции «Заголовок … ссылка справа»: без flex-wrap длинный заголовок выталкивает ссылку за край экрана.
SECTION_HEAD = re.compile(r'<div class="(mb-4 flex [^"]*justify-between[^"]*)">\s*<h2')


def test_section_heads_wrap_on_narrow_screens():
    heads = [
        (path.relative_to(TEMPLATES), match.group(1))
        for path in TEMPLATES.rglob("*.html")
        for match in SECTION_HEAD.finditer(path.read_text())
    ]
    assert heads, "шаблон шапки секции не найден — обновите регулярку"
    assert [(path, cls) for path, cls in heads if "flex-wrap" not in cls] == []


@pytest.mark.django_db
def test_skip_link_and_reduced_motion(client):
    html = client.get("/").content.decode()
    assert '<html lang="ru" class="motion-safe:scroll-smooth">' in html
    body = html.split("<body", 1)[1]
    # Ссылка «Перейти к содержимому» — первый фокусируемый элемент страницы.
    assert body.index('href="#content"') < body.index("<header")
    assert '<main id="content" tabindex="-1"' in html


def test_slider_uses_brand_colors():
    css = (Path(settings.BASE_DIR) / "tailwind/source.css").read_text()
    assert "--swiper-theme-color: var(--color-brand-500)" in css


@pytest.mark.django_db
def test_touch_targets_are_large_enough(client):
    from apps.core.models import Phone, SiteSettings

    site = SiteSettings.load()
    site.vk_url = "https://vk.com/tpark"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    html = client.get("/").content.decode()
    header = html.split("<header", 1)[1].split("</header>", 1)[0]
    assert re.search(r'<button type="button" class="[^"]*\bh-11 w-11\b[^"]*md:hidden"', header)  # бургер
    footer = html.split("<footer", 1)[1]
    assert footer.count("h-11 w-11") == 2  # иконки WhatsApp и VK
    assert "h-8 w-8" not in footer
    assert re.search(r'<a href="tel:\+79029856594" class="[^"]*\bmin-h-11\b', footer)


@pytest.mark.django_db
def test_past_event_badge_is_readable(client):
    from datetime import date

    from apps.content.models import Event

    event = Event.objects.create(title="Сплав", date=date(2020, 5, 1), show_after_date=True)
    html = client.get(event.get_absolute_url()).content.decode()
    badge = re.search(r'<span class="([^"]*)">Прошло</span>', html).group(1)
    assert "text-sm" in badge and "text-xs" not in badge


SOCIAL_ICONS = Path(settings.BASE_DIR) / "static/img/social"


def test_max_icon_is_official_mark():
    """Знак MAX — цветной файл из брендбука (st.max.ru/brandbook/max-colored.zip), а не самодельный рисунок;
    геометрия округлена до 0,1 (сдвиг контура — доли пикселя), смещения и прозрачность градиентов — как в оригинале."""
    svg = (SOCIAL_ICONS / "max.svg").read_text()
    assert 'viewBox="0 0 100 100"' in svg and 'd="M50.8 0.3C78.3 0.3 99.9 22.6' in svg
    assert 'offset="0.01"' in svg
    assert svg.count("<linearGradient") == 154


def test_vk_icon_is_official_mark():
    """Знак ВКонтакте — из брендбука vk.ru/brand (компонент vk_logo_48)."""
    svg = (SOCIAL_ICONS / "vk.svg").read_text()
    assert 'viewBox="0 0 48 48"' in svg and 'fill="#0077FF"' in svg
    assert 'd="M25.54 34.58c-10.94 0-17.18-7.5-17.44-19.98h5.48' in svg


def test_meta_and_telegram_icons_are_official_marks():
    """WhatsApp и Telegram — файлы из паков meta.com/brand и telegram.org/tour/screenshots без правок."""
    whatsapp = (SOCIAL_ICONS / "whatsapp.svg").read_text()
    assert 'viewBox="0 0 720 720"' in whatsapp and "fill: #25d366" in whatsapp
    telegram = (SOCIAL_ICONS / "telegram.svg").read_text()
    assert 'stop-color="#2AABEE"' in telegram and 'stop-color="#229ED9"' in telegram


def test_instagram_icon_is_small_raster():
    """У Instagram в паке Meta только растровый градиентный знак (SVG — обёртка над картинкой 10 МБ): WebP 96 px без потерь."""
    from PIL import Image

    with Image.open(SOCIAL_ICONS / "instagram.webp") as image:
        assert image.size == (96, 96) and image.mode == "RGBA"


def test_every_contact_channel_has_icon():
    assert {path.stem for path in SOCIAL_ICONS.iterdir()} == set(ContactChannel.Kind.values)


def test_vk_is_called_vkontakte_everywhere():
    """В текстах сайта и админки соцсеть называется «ВКонтакте», а не «VK»."""
    offenders = [
        f"{path.relative_to(TEMPLATES)}: {line.strip()}"
        for path in TEMPLATES.rglob("*")
        if path.suffix in {".html", ".svg"}
        for line in path.read_text().splitlines()
        if re.search(r"\bVK\b", line)
    ]
    assert offenders == []


def test_vk_labels_in_models():
    from apps.core.models import SiteSettings

    assert SiteSettings._meta.get_field("vk_url").verbose_name == "ВКонтакте"
    assert "VK" not in SiteSettings._meta.get_field("og_image").help_text
