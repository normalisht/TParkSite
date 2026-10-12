"""Справка в админке (/admin/help/): список разделов — источник для оглавления, якорей и вводных над списками.

Раздел — шаблон `templates/admin/help/sections/<anchor>.html`; `help_anchor` у админок ссылается на `anchor`.
"""

from typing import NamedTuple

from django.contrib import admin
from django.template.response import TemplateResponse


class HelpSection(NamedTuple):
    anchor: str
    title: str

    @property
    def template(self) -> str:
        return f"admin/help/sections/{self.anchor}.html"


HELP_SECTIONS = (
    HelpSection("structure", "Как устроен сайт"),
    HelpSection("not-visible", "Почему этого не видно на сайте"),
    HelpSection("basics", "Общие приёмы"),
    HelpSection("photos", "Фото"),
    HelpSection("catalog", "Каталог: группы, категории, услуги"),
    HelpSection("events", "Мероприятия"),
    HelpSection("reviews", "Отзывы"),
    HelpSection("gallery", "Галерея и партнёры"),
)
HELP_ANCHORS = frozenset(section.anchor for section in HELP_SECTIONS)


def help_view(request):
    context = {**admin.site.each_context(request), "title": "Справка", "sections": HELP_SECTIONS}
    return TemplateResponse(request, "admin/help/index.html", context)
