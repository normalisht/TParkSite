"""Стартовое наполнение страницы «О нас»: форматы и цифры основателя из текстов старого сайта.

Без импорта моделей — используется и в data-миграции, и при импорте старой базы."""

import re

MOTTO = "Красивое место, интересные люди, запоминающееся приключение — вот формула ожидаемой реальности."
FOUNDER_NAME = "Дмитрий Сергеев"
FOUNDER_LEAD = "Этот человек придумал и создал Т-Парк"

# (название, подпись)
FORMATS = [
    ("T-park", "Тренинг-парк"),
    ("T-camp", "Тренинговый лагерь"),
    ("T-club", "Клубный формат тренинга"),
    ("T-raid", "Тренинг-рейды"),
]

# (число, подпись)
FOUNDER_FACTS = [
    ("1000+", "тренингов провёл"),
    ("50+", "социальных технологий придумал"),
    ("~100", "категорийных походов"),
    ("200+", "детских лагерей"),
    ("1500+", "клубных воспитанников"),
]


def fill_about_defaults(site, format_model, fact_model) -> None:
    """Добавляет форматы и цифры, если их ещё нет (модели передаются — подходят и исторические из миграции)."""
    if not format_model.objects.filter(settings=site).exists():
        format_model.objects.bulk_create(
            format_model(settings=site, name=name, caption=caption, order=order)
            for order, (name, caption) in enumerate(FORMATS)
        )
    if not fact_model.objects.filter(settings=site).exists():
        fact_model.objects.bulk_create(
            fact_model(settings=site, value=value, label=label, order=order)
            for order, (value, label) in enumerate(FOUNDER_FACTS)
        )


_LEADING_PARAGRAPH = re.compile(r"\s*<p>(.*?)</p>", re.DOTALL)


def _plain(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html).replace("&nbsp;", " ")
    return text.strip().rstrip(":.").strip().casefold()


def strip_founder_heading(text: str, *titles: str) -> str:
    """Убирает абзацы в начале биографии, которые повторяют имя и подзаголовок основателя: «О нас» выводит их над текстом."""
    wanted = {_plain(title) for title in titles if title.strip()}
    rest = text
    while (match := _LEADING_PARAGRAPH.match(rest)) and _plain(match.group(1)) in wanted:
        rest = rest[match.end() :]
    return text if rest is text else rest.lstrip()
