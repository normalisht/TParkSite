from django import template

from apps.core.images import safe_spec_url
from apps.core.seo import plaintext as _plaintext

register = template.Library()


@register.filter
def spec_url(obj, spec_name: str) -> str:
    return safe_spec_url(obj, spec_name)


@register.filter
def plaintext(value, limit: int = 160) -> str:
    return _plaintext(value, int(limit))
