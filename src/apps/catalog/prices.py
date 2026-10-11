"""Цена услуги для витрины: «₽» только у числа, тысячи — через неразрывный пробел от 10 000."""

import re

_NUMBER = re.compile(r"^(?P<prefix>от\s+)?(?P<amount>\d[\d\s ]*)$", re.IGNORECASE)
NBSP = " "


def _group(digits: str) -> str:
    # 1500 — без пробела (так принято для четырёхзначных), 15 000 — с неразрывным пробелом.
    if len(digits) < 5:
        return digits
    return f"{int(digits):,}".replace(",", NBSP)


def format_price(text: str) -> str:
    text = (text or "").strip()
    match = _NUMBER.match(text)
    if not match:
        return text  # «договорная», «бесплатно» — как есть
    digits = re.sub(r"\D", "", match["amount"])
    prefix = "от " if match["prefix"] else ""
    return f"{prefix}{_group(digits)}{NBSP}₽"
