"""Хосты виджета Яндекс Карт — отдельный модуль без зависимостей: его читают и поле карты, и настройки (CSP frame-src)."""

WIDGET_HOSTS = frozenset({"yandex.ru", "www.yandex.ru", "yandex.com", "www.yandex.com"})
