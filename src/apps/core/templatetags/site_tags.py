import json

from django import template
from django.utils.safestring import mark_safe

from apps.core.images import safe_spec_url
from apps.core.seo import plaintext as _plaintext

register = template.Library()


@register.filter
def spec_url(obj, spec_name: str) -> str:
    return safe_spec_url(obj, spec_name)


@register.filter
def plaintext(value, limit: int = 160) -> str:
    return _plaintext(value, int(limit))


_JSON_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.filter
def ld_json(value) -> str:
    """Структурированные данные schema.org: `<script type="application/ld+json">` с экранированием, как у json_script."""
    data = json.dumps(value, ensure_ascii=False).translate(_JSON_ESCAPES)
    return mark_safe(f'<script type="application/ld+json">{data}</script>')


@register.filter
def ru_plural(number, forms: str) -> str:
    """`{{ n|ru_plural:"отзыв,отзыва,отзывов" }}` → «21 отзыв», «3 отзыва», «18 отзывов»."""
    one, few, many = forms.split(",")
    n = abs(int(number))
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = few
    else:
        word = many
    return f"{number} {word}"
