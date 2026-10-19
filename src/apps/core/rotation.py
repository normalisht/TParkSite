"""Ротация подборок витрины: состав меняется раз в сутки, а в течение дня одинаков."""

import random
from collections.abc import Sequence
from datetime import date

from django.utils import timezone


def daily_pick[T](items: Sequence[T], k: int, key: object = "", today: date | None = None) -> list[T]:
    """До k элементов items, выбранных на день today (по умолчанию — сегодня по местному времени) для ключа key.

    Порядок — как в items. Один день и ключ — один и тот же набор во всех процессах gunicorn (сид — строка,
    не hash()): HTML не меняется от запроса к запросу, и ETag/304 продолжают работать. Разные ключи — разные наборы.
    """
    if len(items) <= k:
        return list(items)
    today = today or timezone.localdate()
    rng = random.Random(f"{today.isoformat()}:{key}")
    return [items[i] for i in sorted(rng.sample(range(len(items)), k))]
