from django.urls import reverse
from django.utils.functional import lazy
from django.utils.html import format_html, format_html_join

from apps.texts.registry import Page


def _texts_hint(*pages: Page) -> str:
    url = reverse("admin:texts_sitetext_changelist")
    links = format_html_join(
        ", ",
        '<a href="{}?page__exact={}" class="text-primary-600 underline">{}</a>',
        ((url, page.value, page.label) for page in pages),
    )
    return format_html("Заголовки блоков и короткие фразы страницы — в «Текстах сайта»: {}.", links)


# Описание вкладки настроек: рендерится при показе формы (URL-ы к этому моменту уже загружены).
texts_hint = lazy(_texts_hint, str)


def _texts_intro() -> str:
    return format_html(
        "Короткие фразы и заголовки блоков витрины. Вступления и длинные тексты страниц («О нас», биография, "
        '«Что рядом», текст контактов) — в <a href="{}" class="text-primary-600 underline">«Настройках сайта»</a>.',
        reverse("admin:core_sitesettings_changelist"),
    )


# Вводная над списком «Текстов сайта»: ссылка собирается при показе (URL-ы к этому моменту уже загружены).
texts_intro = lazy(_texts_intro, str)()
