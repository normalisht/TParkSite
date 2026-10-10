"""Правила вёрстки, которые проверяются по исходникам шаблонов (браузерная проверка — tests/e2e)."""

import re
from pathlib import Path

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
