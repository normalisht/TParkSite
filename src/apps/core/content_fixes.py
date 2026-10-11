"""Приведение старого контента к единому виду: бренд «Т-Парк», «₽», единицы цен, кавычки, известные опечатки.

Чистые функции над строкой; команда `normalize_content` применяет их к полям моделей. Латинские T-park, T-camp,
T-club, T-raid — названия форматов в «О нас», их не трогаем. Кавычки меняем только в названиях (в HTML они в атрибутах).
"""

import re
from difflib import SequenceMatcher

TYPOS = {
    "рекрасное место": "Прекрасное место",
    "собирабтся": "собираются",
    "обязателный": "обязательный",
    "Продолжитальность": "Продолжительность",
    "движнием": "движением",
}
NAME_FIXES = {
    'Сплав на каноэ "На родину маршала Жукова, однодневный (летняя программа)': (
        "Сплав на каноэ «На родину маршала Жукова», однодневный (летняя программа)"
    ),
}
UNIT_FIXES = {"человек": "участник", "чел": "участник", "чел.": "участник", "в день": "день"}

_BRAND = re.compile(r"Т-парк")  # кириллические Т и п
_YO = re.compile(r"([Вв])еревочн")
_RUB = re.compile(r"(\d)\s*(?:руб(?:лей|ля|ль)?\.?|р\.?)(?![а-яёА-ЯЁ])")
_WATTS = re.compile(r"(\d)\s*w\b")
_MINUTES = re.compile(r"(\d+)\s*минут[аы]?(?![а-яё])")
_STRAIGHT_QUOTES = re.compile(r'"([^"]*)"')
_PRICE_CURRENCY = re.compile(r"(?<=\d)\s*(?:руб(?:лей|ля|ль)?\.?|р\.?|₽)\s*$")
_DIGIT_SPACES = re.compile(r"(?<=\d)[\s ]+(?=\d)")


def fix_text(value: str) -> str:
    """Любой текст, в том числе HTML: опечатки, бренд, «ё» в «верёвочный», «Вт», «₽»."""
    for wrong, right in TYPOS.items():
        value = value.replace(wrong, right)
    value = _BRAND.sub("Т-Парк", value)
    value = _YO.sub(r"\1ерёвочн", value)
    value = _WATTS.sub(r"\1 Вт", value)
    return _RUB.sub(r"\1 ₽", value)


def fix_name(value: str) -> str:
    """Название (без HTML): то же + без звёздочек старой системы, «ёлочки» вместо прямых кавычек."""
    value = fix_text(NAME_FIXES.get(value, value)).replace("*", "")
    value = _STRAIGHT_QUOTES.sub(r"«\1»", value)
    return re.sub(r"\s{2,}", " ", value).strip()


def fix_price(value: str) -> str:
    """Цена — число (возможно с «от»): пробелы внутри числа и «руб»/«р.»/«₽» в конце убираем, «₽» добавит витрина."""
    value = _PRICE_CURRENCY.sub("", value.strip())
    return _DIGIT_SPACES.sub("", value)


def fix_unit(value: str) -> str:
    value = value.strip()
    value = UNIT_FIXES.get(value.lower(), value)
    return _MINUTES.sub(r"\1 мин", value)


def fix_caption(value: str) -> str:
    return "" if value.strip().isdigit() else value


def has_unbalanced_quotes(value: str) -> bool:
    return value.count('"') % 2 == 1 or value.count("«") != value.count("»")


def describe_change(old: str, new: str, context: int = 25) -> str:
    """Изменённые места с контекстом: «…было… → …стало…» (для длинного HTML)."""
    parts = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag != "equal":
            parts.append(f"…{old[max(0, i1 - context) : i2 + context]}… → …{new[max(0, j1 - context) : j2 + context]}…")
    return "; ".join(parts[:5])
