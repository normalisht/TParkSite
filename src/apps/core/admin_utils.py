from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.core.images import safe_spec_url


class SiteModelAdmin(ModelAdmin):
    """Базовая админка проекта: предупреждает при уходе со страницы с несохранёнными изменениями."""

    class Media:
        js = ["js/admin_unsaved.js"]


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


def copy_url_button(path: str):
    """Кнопка, копирующая абсолютный адрес страницы; нужен static/js/admin_copy.js в Media админки."""
    return format_html(
        '<span class="inline-flex items-center gap-1"><a href="{0}" target="_blank" rel="noopener">{0}</a>'
        '<button type="button" data-copy-url="{0}" title="Скопировать адрес" aria-label="Скопировать адрес" '
        'class="flex items-center p-1 rounded-default text-base-400 hover:text-primary-600 '
        'dark:hover:text-primary-500">'
        '<span class="material-symbols-outlined text-lg">content_copy</span></button></span>',
        path,
    )
