from django.utils.text import slugify
from unidecode import unidecode


def slugify_ru(value: str, max_length: int = 200) -> str:
    return slugify(unidecode(value or ""))[:max_length].strip("-") or "item"


def unique_slug(instance, value: str, field: str = "slug") -> str:
    """Slug из `value`, уникальный среди записей той же модели (суффиксы -2, -3, …)."""
    base = slugify_ru(value)
    manager = type(instance)._default_manager
    candidate, counter = base, 2
    while manager.filter(**{field: candidate}).exclude(pk=instance.pk).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
