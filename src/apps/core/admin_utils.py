from django.contrib import admin
from django.utils.html import format_html

from apps.core.images import safe_spec_url


def image_preview(spec_name: str, size: int = 64):
    @admin.display(description="Фото")
    def preview(_model_admin, obj):
        url = safe_spec_url(obj, spec_name)
        if not url:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="height:{}px;width:auto;border-radius:6px;object-fit:cover">', url, size
        )

    return preview
