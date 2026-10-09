"""Встраиваемая Яндекс Карта (в админке можно вставить и ссылку, и целиком код <iframe> из «Поделиться → Встроить»)
и ссылки «Построить маршрут» до координат парка."""

import html
import re
from urllib.parse import urlsplit

from django import forms
from django.core.exceptions import ValidationError
from django.db import models

WIDGET_HOSTS = {"yandex.ru", "www.yandex.ru", "yandex.com", "www.yandex.com"}
_IFRAME_SRC_RE = re.compile(r"""<iframe\b[^>]*?\ssrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def extract_map_src(value: str) -> str:
    """Из кода <iframe …> достаёт адрес src; обычную ссылку возвращает как есть."""
    value = (value or "").strip()
    match = _IFRAME_SRC_RE.search(value)
    return html.unescape(match.group(1)).strip() if match else value


def validate_map_widget_url(value: str) -> None:
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.hostname not in WIDGET_HOSTS or not parts.path.startswith("/map-widget/"):
        raise ValidationError(
            "Нужна ссылка виджета Яндекс Карт (https://yandex.ru/map-widget/…): "
            "в Яндекс Картах «Поделиться» → «Встроить карту», скопируйте код целиком."
        )


class MapEmbedFormField(forms.URLField):
    def to_python(self, value):
        return super().to_python(extract_map_src(value))

    def widget_attrs(self, widget):
        # Ограничение длины — на извлечённую ссылку, а не на вставляемый код <iframe>, он заметно длиннее.
        attrs = super().widget_attrs(widget)
        attrs.pop("maxlength", None)
        return attrs


class MapEmbedURLField(models.URLField):
    default_validators = [*models.URLField.default_validators, validate_map_widget_url]

    def formfield(self, **kwargs):
        kwargs.setdefault("form_class", MapEmbedFormField)
        kwargs.setdefault("widget", forms.Textarea(attrs={"rows": 3}))
        return super().formfield(**kwargs)


def route_links(latitude, longitude) -> dict[str, str]:
    """Маршрут до точки в картографических сервисах; без координат — пусто."""
    if latitude is None or longitude is None:
        return {}
    point = f"{float(latitude):.6f},{float(longitude):.6f}"
    lat, lon = point.split(",")
    return {
        "yandex": f"https://yandex.ru/maps/?rtext=~{point}&rtt=auto",
        "google": f"https://www.google.com/maps/dir/?api=1&destination={point}",
        "coordinates": f"{lat}, {lon}",
    }
