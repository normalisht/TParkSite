"""Значения, общие для всего запроса: считаются один раз.

Контекст-процессоры выполняются на каждый шаблон, отрендеренный с request (в админке Unfold — 5–6 раз на страницу),
а JSON-LD спрашивает настройки сайта для каждой услуги. Кеш живёт в атрибуте запроса и умирает вместе с ним.
"""

from collections.abc import Callable


def cached_on_request[T](request, key: str, factory: Callable[[], T]) -> T:
    cache = request.__dict__.setdefault("_tpark_cache", {})
    if key not in cache:
        cache[key] = factory()
    return cache[key]
