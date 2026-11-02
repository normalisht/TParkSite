from django import template

from apps.catalog.tiles import category_tiles as _category_tiles

register = template.Library()


@register.filter
def category_tiles(categories) -> list:
    return _category_tiles(categories)
