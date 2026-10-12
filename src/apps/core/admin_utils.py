from django.contrib import admin
from django.template.loader import render_to_string
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.core.images import safe_spec_url
from apps.core.request_cache import cached_on_request


def _render_seo_help(name: str, request=None) -> str:
    from apps.core.models import DEFAULT_TITLE_SUFFIX, SiteSettings
    from apps.core.seo import STATIC_PAGES, page_fallback

    site = SiteSettings.for_request(request)
    suffix = site.seo_title_suffix or DEFAULT_TITLE_SUFFIX
    # Для превью в настройках: что выведется на странице, если её поля оставить пустыми.
    pages = []
    for key, (label, path, _text_field) in STATIC_PAGES.items():
        title, description = page_fallback(key, site)
        pages.append({"key": key, "label": label, "path": path, "title": title, "description": description})
    return render_to_string(f"admin/seo/{name}.html", {"suffix": suffix, "pages": pages})


class SeoHelp:
    """Справка в описании вкладки (templates/admin/seo/): собирается при показе формы — с текущим окончанием заголовков.

    `SiteModelAdmin.get_fieldsets` подставляет готовый HTML один раз на запрос; шаблон Unfold вычисляет описание
    дважды (`if` и вывод), поэтому без этого каждая справка ходила бы за настройками дважды."""

    def __init__(self, name: str):
        self.name = name

    def render(self, request=None) -> str:
        if request is None:
            return _render_seo_help(self.name)
        return cached_on_request(request, f"seo_help:{self.name}", lambda: _render_seo_help(self.name, request))

    def __str__(self) -> str:
        return self.render()


seo_help = SeoHelp

# Вкладка SEO в формах страниц с `apps.core.models.SeoModel`.
SEO_FIELDSET = (
    "SEO",
    {"classes": ["tab"], "description": seo_help("object"), "fields": ["seo_title", "seo_description"]},
)


class SiteModelAdmin(ModelAdmin):
    """Базовая админка проекта: предупреждает при уходе со страницы с несохранёнными изменениями,
    у SEO-полей показывает счётчики символов и превью сниппета (admin_seo.js), над списком — вводную
    `help_intro`, над формой — ссылку на раздел справки `help_anchor` (apps/core/admin_help.py)."""

    help_intro = ""  # 1–2 предложения над списком; доверенный HTML (выводится через |safe)
    help_anchor = ""  # якорь раздела справки из HELP_SECTIONS
    list_before_template = "admin/help/list_intro.html"
    change_form_before_template = "admin/help/form_link.html"

    class Media:
        css = {"all": ["css/admin_seo.css"]}
        js = ["js/admin_unsaved.js", "js/admin_seo.js"]

    def get_fieldsets(self, request, obj=None):
        return [
            (title, {**options, "description": options["description"].render(request)})
            if isinstance(options.get("description"), SeoHelp)
            else (title, options)
            for title, options in super().get_fieldsets(request, obj)
        ]


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
