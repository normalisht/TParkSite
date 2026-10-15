from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.admin.options import ActionLocation
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.core import search
from apps.core.images import safe_spec_url
from apps.core.models import next_order
from apps.core.request_cache import cached_on_request
from apps.core.trash import TRASH_DAYS, purge_expired


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

# То же в формах с вкладками-inline (услуга, категория): вкладка «SEO» в одном ряду с вкладками-inline,
# а не вторая строка вкладок внутри «Основного». Класс «seo-pane» (не «tab»: Unfold ищет подстроку) —
# метка для templates/admin/includes/fieldset.html; саму вкладку рисует templates/unfold/helpers/tab_items.html.
SEO_PANE = "seo-pane"
SEO_FIELDS = ["seo_title", "seo_description"]
SEO_TAB = (None, {"classes": [SEO_PANE], "description": seo_help("object"), "fields": SEO_FIELDS})


class OrderedInlineMixin:
    """Новая строка inline встаёт в конец: начальное значение порядка — после последней записи родителя.
    Без этого у новой строки order=0, и после сохранения она оказывается первой: перетаскивание Unfold
    переписывает порядок строк, только если их двигали."""

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        scope = {formset.fk.name: obj} if obj is not None and obj.pk else None
        formset.form.base_fields["order"].initial = next_order(self.model, **scope) if scope else 1
        return formset


class SiteModelAdmin(ModelAdmin):
    """Базовая админка проекта: предупреждает при уходе со страницы с несохранёнными изменениями,
    у SEO-полей показывает счётчики символов и превью сниппета (admin_seo.js), над списком — вводную
    `help_intro`, над формой — ссылку на раздел справки `help_anchor` (apps/core/admin_help.py).
    Поиск — без учёта регистра и «ё»/«е» (apps/core/search.py)."""

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

    def render_change_form(self, request, context, *args, **kwargs):
        # Вкладка «SEO» (SEO_TAB) рисуется в ряду вкладок-inline: передаём ей число ошибок SEO-полей и поправку
        # для счётчика «Основного» (Unfold считает в нём все ошибки формы).
        if any(SEO_PANE in fieldset.classes for fieldset in context["adminform"]):
            errors = sum(name in context["adminform"].form.errors for name in SEO_FIELDS)
            for inline in context["inline_admin_formsets"]:
                inline.seo_tab = {"error_count": errors, "general_offset": -errors}
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        # Поля «Порядок» в формах нет — порядок задают перетаскиванием в списке, новая запись встаёт в конец.
        if not change and "order" not in form.fields and any(f.name == "order" for f in obj._meta.fields):
            obj.order = next_order(type(obj))
        super().save_model(request, obj, form, change)

    def get_search_results(self, request, queryset, search_term):
        # Без учёта регистра и «ё»/«е» (apps/core/search.py); кроме SQLite — как в Django.
        search_fields = self.get_search_fields(request)
        if not (search_fields and search_term) or connections[queryset.db].vendor != "sqlite":
            return super().get_search_results(request, queryset, search_term)
        return search.search(queryset, search_fields, search_term)


class TrashAdminMixin:
    """«Удалить» переносит запись в корзину (`TrashableModel`). Над списком — кнопка «Корзина»
    (добавьте "trash" в `actions_list`): там «Восстановить» и «Удалить навсегда»."""

    trash_enabled = True  # подпись «В корзину» вместо «Удалить» (templates/admin/submit_line.html)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted_at__isnull=True)

    def _changelist_url(self):
        opts = self.model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    def get_actions(self, request, action_location=ActionLocation.CHANGE_LIST):
        actions = super().get_actions(request, action_location=action_location)
        actions.pop("delete_selected", None)
        trash_action = self.get_action("move_selected_to_trash", action_location)  # None вне списка
        if trash_action and self.has_delete_permission(request):
            actions[trash_action.name] = trash_action
        return actions

    @admin.action(description="Переместить в корзину")
    def move_selected_to_trash(self, request, queryset):
        moved = 0
        for obj in queryset:
            obj.move_to_trash()
            self.log_change(request, obj, "Перемещено в корзину")
            moved += 1
        purge_expired(self.model)
        self.message_user(
            request, f"В корзину перемещено: {moved}. Восстановить — кнопка «Корзина» над списком.", messages.SUCCESS
        )

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied
        if request.method == "POST":
            obj.move_to_trash()
            self.log_change(request, obj, "Перемещено в корзину")
            purge_expired(self.model)
            self.message_user(
                request,
                f"«{obj}» — в корзине. Восстановить можно {TRASH_DAYS} дней: кнопка «Корзина» над списком.",
                messages.SUCCESS,
            )
            return redirect(self._changelist_url())
        context = {
            **self.admin_site.each_context(request),
            "title": "Переместить в корзину?",
            "object": obj,
            "opts": self.model._meta,
            "trash_days": TRASH_DAYS,
            "changelist_url": self._changelist_url(),
            **(extra_context or {}),
        }
        return TemplateResponse(request, "admin/trash/confirm.html", context)

    @action(description="Корзина", url_path="trash", permissions=["delete"], icon="delete")
    def trash(self, request):
        trashed = self.model._default_manager.filter(deleted_at__isnull=False).order_by("-deleted_at")
        if request.method == "POST":
            obj = get_object_or_404(trashed, pk=request.POST.get("pk"))
            if "restore" in request.POST:
                if not self.has_change_permission(request, obj):
                    raise PermissionDenied
                obj.restore()
                self.log_change(request, obj, "Восстановлено из корзины")
                self.message_user(
                    request, f"«{obj}» восстановлено черновиком — проверьте и опубликуйте.", messages.SUCCESS
                )
            elif "purge" in request.POST:
                name = str(obj)
                self.log_deletions(request, trashed.filter(pk=obj.pk))
                obj.delete()
                self.message_user(request, f"«{name}» удалено навсегда.", messages.SUCCESS)
            return redirect(request.path)
        purge_expired(self.model)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Корзина: {self.model._meta.verbose_name_plural}",
            "opts": self.model._meta,
            "items": [(obj, obj.deleted_at + timedelta(days=TRASH_DAYS)) for obj in trashed],
            "trash_days": TRASH_DAYS,
            "changelist_url": self._changelist_url(),
        }
        return render(request, "admin/trash/list.html", context)


def move_to_top(model, selected) -> int:
    """Ставит выбранные записи в начало списка (между собой — в прежнем порядке), остальные — следом."""
    picked = list(selected.order_by("order", "id").only("pk", "order"))
    picked_ids = {obj.pk for obj in picked}
    rest = [
        obj for obj in model._default_manager.order_by("order", "id").only("pk", "order") if obj.pk not in picked_ids
    ]
    rows = [*picked, *rest]
    for position, obj in enumerate(rows, start=1):
        obj.order = position
    model._default_manager.bulk_update(rows, ["order"])
    return len(picked)


def thumbnail_html(obj, spec_name: str, size: int = 64) -> str:
    """Генерирует HTML для превью фото в админке."""
    url = safe_spec_url(obj, spec_name)
    if not url:
        return "—"
    return format_html(
        '<img src="{}" alt="" loading="lazy" style="height:{}px;width:auto;border-radius:6px;object-fit:cover">',
        url,
        size,
    )


def image_preview(spec_name: str, size: int = 64):
    @admin.display(description="Фото")
    def preview(_model_admin, obj):
        return thumbnail_html(obj, spec_name, size)

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
