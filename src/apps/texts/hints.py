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
