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
