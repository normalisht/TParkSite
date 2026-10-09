from django.contrib import admin
from django.template.loader import render_to_string
from django.utils.functional import lazy
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.core.images import safe_spec_url


def _render_seo_help(name: str) -> str:
    from apps.core.models import DEFAULT_TITLE_SUFFIX, SiteSettings
    from apps.core.seo import STATIC_PAGES, page_fallback

    site = SiteSettings.load()
    suffix = site.seo_title_suffix or DEFAULT_TITLE_SUFFIX
    # Для превью в настройках: что выведется на странице, если её поля оставить пустыми.
    pages = []
    for key, (label, path, _text_field) in STATIC_PAGES.items():
        title, description = page_fallback(key, site)
        pages.append({"key": key, "label": label, "path": path, "title": title, "description": description})
    return render_to_string(f"admin/seo/{name}.html", {"suffix": suffix, "pages": pages})


# Справка в описании вкладки (templates/admin/seo/): рендерится при показе формы — с текущим окончанием заголовков.
seo_help = lazy(_render_seo_help, str)

# Вкладка SEO в формах страниц с `apps.core.models.SeoModel`.
SEO_FIELDSET = (
    "SEO",
    {"classes": ["tab"], "description": seo_help("object"), "fields": ["seo_title", "seo_description"]},
)


class SiteModelAdmin(ModelAdmin):
    """Базовая админка проекта: предупреждает при уходе со страницы с несохранёнными изменениями,
    у SEO-полей показывает счётчики символов и превью сниппета (admin_seo.js)."""

    class Media:
        css = {"all": ["css/admin_seo.css"]}
        js = ["js/admin_unsaved.js", "js/admin_seo.js"]


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
