"""Правила вёрстки, которые проверяются по исходникам шаблонов (браузерная проверка — tests/e2e)."""

import re
from pathlib import Path

import pytest
from django.conf import settings

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


def test_max_icon_is_official_mark():
    """Знак MAX — контур из брендбука max.ru (st.max.ru/brandbook/max-dark.zip), а не самодельный рисунок."""
    svg = (TEMPLATES / "icons/max.svg").read_text()
    assert 'viewBox="0 0 100 100"' in svg and svg.count("<path") == 1
    assert 'd="M50.7571 0.261719C78.2929' in svg
