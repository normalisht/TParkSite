"""Стартовое наполнение страницы «О нас»: форматы и цифры основателя из текстов старого сайта.

Без импорта моделей — используется и в data-миграции, и при импорте старой базы."""

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
