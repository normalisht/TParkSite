import copy
import html
import re
from dataclasses import replace

from django.contrib import admin, messages
from django.contrib.admin.options import ActionLocation
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path as url_path
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_prose_editor.fields import ProseEditorField
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.core import search
from apps.core.images import safe_spec_url
from apps.core.models import Redirect, next_order
from apps.core.request_cache import cached_on_request
from apps.core.slugs import slugify_ru
from apps.core.trash import TRASH_DAYS, purge_date, purge_expired


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
    # Поля, из которых модель собирает адрес (`slug_source()`): у черновика адрес следует за ними (`_draft_slug_follows`).
    slug_source_fields: tuple[str, ...] = ()
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
        draft_url = obj.get_absolute_url() if change and self._draft_slug_follows(obj, form) else None
        if draft_url:
            obj.slug = ""  # save() соберёт адрес заново — из нового названия
        super().save_model(request, obj, form, change)
        if draft_url:
            Redirect.objects.filter(old_path=draft_url).delete()  # адрес черновика на сайте не открывался

    def _draft_slug_follows(self, obj, form) -> bool:
        """Адрес черновика следует за названием (и годом мероприятия): у копии «Встреча (копия)» после правки
        названия и даты адрес «vstrecha-2027», а не «vstrecha-kopiia-2026». Не трогаем адрес опубликованной
        записи (он уже может быть в поиске) и заданный руками — не похожий на собранный из прежнего названия."""
        if not self.slug_source_fields or "slug" in form.changed_data or form.initial.get("is_published"):
            return False
        if not any(name in form.changed_data for name in self.slug_source_fields):
            return False
        before = copy.copy(obj)
        for name in self.slug_source_fields:
            setattr(before, name, form.initial.get(name))
        base = re.escape(slugify_ru(before.slug_source()))
        return re.fullmatch(rf"{base}(-\d+)?", form.initial.get("slug") or "") is not None

    def get_search_results(self, request, queryset, search_term):
        # Без учёта регистра и «ё»/«е» (apps/core/search.py); кроме SQLite — как в Django.
        search_fields = self.get_search_fields(request)
        if not (search_fields and search_term) or connections[queryset.db].vendor != "sqlite":
            return super().get_search_results(request, queryset, search_term)
        return search.search(queryset, search_fields, search_term)


def _readonly_html(sanitize):
    def render(contents: str) -> str:
        return mark_safe(sanitize(html.unescape(contents)))  # очищено nh3 — как при сохранении

    return render


class TrashAdminMixin:
    """«Удалить» переносит запись в корзину (`TrashableModel`). Над списком — кнопка «Корзина (N)»
    (добавьте "trash" в `actions_list`): там «Восстановить» и «Удалить навсегда», по названию — просмотр записи
    (`trash/<pk>/`: обычная форма только для чтения)."""

    trash_enabled = True  # подпись «В корзину» вместо «Удалить» (templates/admin/submit_line.html)
    change_form_outer_before_template = "admin/trash/preview_banner.html"  # плашка просмотра из корзины

    @staticmethod
    def _trash_preview(request) -> bool:
        # Запрос открыт через trash_detail_view: видны только записи в корзине, править нельзя.
        return getattr(request, "_trash_preview", False)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted_at__isnull=not self._trash_preview(request))

    def has_add_permission(self, request):
        return not self._trash_preview(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return not self._trash_preview(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._trash_preview(request) and super().has_delete_permission(request, obj)

    def get_view_on_site_url(self, obj=None):
        # В просмотре из корзины ссылки «На сайте» нет: страница записи в корзине — 404.
        return None if obj is not None and obj.in_trash else super().get_view_on_site_url(obj)

    def _url_name(self, view: str) -> str:
        opts = self.model._meta
        return f"admin:{opts.app_label}_{opts.model_name}_{view}"

    def _changelist_url(self):
        return reverse(self._url_name("changelist"))

    def _trashed(self):
        return self.model._default_manager.filter(deleted_at__isnull=False)

    def _get_trashed_or_404(self, pk):
        try:
            pk = self.model._meta.pk.to_python(pk)
        except ValidationError:
            raise Http404 from None
        return get_object_or_404(self._trashed(), pk=pk)

    @property
    def readonly_preprocess_fields(self):
        # Форма только для чтения (просмотр из корзины): HTML-тексты — как на сайте, а не исходником.
        # Unfold отдаёт значение экранированным — возвращаем как было и очищаем ещё раз очисткой самого поля
        # (у инфо-страниц свой набор: таблицы, выноска).
        return {
            field.name: _readonly_html(field.sanitize)
            for field in self.model._meta.fields
            if isinstance(field, ProseEditorField)
        }

    def get_urls(self):
        opts = self.model._meta
        detail = url_path(
            "trash/<path:object_id>/",
            self.admin_site.admin_view(self.trash_detail_view),
            name=f"{opts.app_label}_{opts.model_name}_trash_detail",
        )
        return [detail, *super().get_urls()]  # раньше «<path:object_id>/» формы записи

    def get_actions_detail(self, request, object_id):
        # Просмотр из корзины — только для чтения: «Дублировать» и другие кнопки формы не нужны.
        return [] if self._trash_preview(request) else super().get_actions_detail(request, object_id)

    def get_actions_list(self, request):
        # Число записей в корзине — на кнопке над списком.
        actions = super().get_actions_list(request)
        name = self._url_name("trash").removeprefix("admin:")
        for index, unfold_action in enumerate(actions):
            if unfold_action.action_name == name and (count := self._trashed().count()):
                actions[index] = replace(unfold_action, description=f"{unfold_action.description} ({count})")
        return actions

    def get_actions(self, request, action_location=ActionLocation.CHANGE_LIST):
        actions = super().get_actions(request, action_location=action_location)
        actions.pop("delete_selected", None)
        trash_action = self.get_action("move_selected_to_trash", action_location)  # None вне списка
        if trash_action and self.has_delete_permission(request):
            actions[trash_action.name] = trash_action
        return actions

    @admin.action(description="Переместить в корзину")
    def move_selected_to_trash(self, request, queryset):
        with transaction.atomic():
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
            with transaction.atomic():
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
        if request.method == "POST":
            obj = self._get_trashed_or_404(request.POST.get("pk"))
            if "restore" in request.POST:
                if not self.has_change_permission(request, obj):
                    raise PermissionDenied
                with transaction.atomic():
                    obj.restore()
                    self.log_change(request, obj, "Восстановлено из корзины")
                self.message_user(
                    request, f"«{obj}» восстановлено черновиком — проверьте и опубликуйте.", messages.SUCCESS
                )
                return redirect(reverse(self._url_name("change"), args=[obj.pk]))
            if "purge" in request.POST:
                name = str(obj)
                with transaction.atomic():
                    self.log_deletions(request, self._trashed().filter(pk=obj.pk))
                    obj.delete()
                self.message_user(request, f"«{name}» удалено навсегда.", messages.SUCCESS)
            return redirect(request.path)
        purge_expired(self.model)
        items = [(obj, purge_date(obj)) for obj in self._trashed().order_by("-deleted_at")]
        title = f"Корзина: {self.model._meta.verbose_name_plural}"
        context = {
            **self.admin_site.each_context(request),
            "title": f"{title} ({len(items)})" if items else title,
            "opts": self.model._meta,
            "items": items,
            "trash_days": TRASH_DAYS,
            "changelist_url": self._changelist_url(),
        }
        return render(request, "admin/trash/list.html", context)

    def trash_detail_view(self, request, object_id):
        """Запись из корзины в обычной форме, только для чтения, с плашкой и кнопками корзины сверху."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        obj = self._get_trashed_or_404(object_id)
        trash_preview = {
            "deleted_at": obj.deleted_at,
            "purge_date": purge_date(obj),
            "trash_url": reverse(self._url_name("trash")),
            "can_restore": self.has_delete_permission(request) and self.has_change_permission(request, obj),
            "can_purge": self.has_delete_permission(request),
        }
        request._trash_preview = True
        # «История» ищет запись обычным get_queryset (без корзины) и ответила бы «не найдено» — ссылку прячем.
        extra_context = {"title": f"«{obj}» — в корзине", "trash_preview": trash_preview, "show_history": False}
        return self.changeform_view(request, str(obj.pk), extra_context=extra_context)


class DuplicateAdminMixin:
    """Тело кнопки «Дублировать» (`actions_detail`): GET — страница подтверждения, копию создаёт только POST
    (иначе любая страница могла бы создать запись в браузере администратора — CSRF). Модель задаёт `duplicate()`."""

    def duplicate_view(self, request, object_id, hint: str):
        original = self.get_object(request, unquote(object_id))  # None и для «abc», и для записи в корзине
        if original is None:
            raise Http404
        opts = self.model._meta
        change_name = f"admin:{opts.app_label}_{opts.model_name}_change"
        if request.method != "POST":
            context = {
                **self.admin_site.each_context(request),
                "title": "Дублировать",
                "object": original,
                "opts": opts,
                "change_url": reverse(change_name, args=[original.pk]),
            }
            return TemplateResponse(request, "admin/duplicate_confirm.html", context)
        copy = original.duplicate()
        self.log_addition(request, copy, f"Копия «{original}»")
        messages.success(request, f"Создана копия «{original}» — черновик. {hint}")
        return redirect(reverse(change_name, args=[copy.pk]))


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
