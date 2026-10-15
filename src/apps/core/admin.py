from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db.models import Case, When
from django.forms.models import BaseInlineFormSet, ModelForm
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import format_lazy
from unfold.admin import StackedInline, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.core import seasons
from apps.core.admin_utils import (
    SEO_FIELDSET,
    OrderedInlineMixin,
    SiteModelAdmin,
    TrashAdminMixin,
    copy_url_button,
    seo_help,
)
from apps.core.maps import MapEmbedURLField
from apps.core.models import Announcement, FounderFact, InfoPage, ParkFormat, Phone, Redirect, Season, SiteSettings
from apps.texts.hints import texts_hint
from apps.texts.registry import Page

MESSENGER_FLAGS = (("is_whatsapp", "WhatsApp"), ("is_telegram", "Telegram"))


class PhoneForm(ModelForm):
    class Meta:
        model = Phone
        fields = ["number", "is_whatsapp", "is_telegram", "order"]

    def _get_validation_exclusions(self):
        # Флаги мессенджеров проверяются по всему набору в PhoneFormSet.clean: построчная проверка
        # ограничения видит в БД старый флаг и не даёт перенести его на другой номер.
        exclusions = super()._get_validation_exclusions()
        exclusions.add("settings")
        return exclusions


class PhoneFormSet(BaseInlineFormSet):
    def _alive_forms(self):
        return [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]

    def clean(self):
        super().clean()
        for flag, label in MESSENGER_FLAGS:
            if sum(1 for f in self._alive_forms() if f.cleaned_data.get(flag)) > 1:
                raise ValidationError(f"{label} можно отметить только у одного номера.")

    def save(self, commit=True):
        # Снимаем флаг с прежнего владельца, если в форме он поставлен другому номеру, — иначе при
        # сохранении нового владельца раньше старого сработает уникальное ограничение. С самого владельца
        # флаг не снимаем: неизменённая строка формы не пересохраняется, и флаг бы потерялся.
        for flag, _ in MESSENGER_FLAGS:
            owners = [f for f in self._alive_forms() if f.cleaned_data.get(flag)]
            if owners:
                owner_pk = owners[0].instance.pk
                Phone.objects.filter(settings=self.instance, **{flag: True}).exclude(pk=owner_pk).update(
                    **{flag: False}
                )
        return super().save(commit)


class PhoneInline(OrderedInlineMixin, TabularInline):
    model = Phone
    form = PhoneForm
    formset = PhoneFormSet
    extra = 0
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["number", "is_whatsapp", "is_telegram", "order"]
    tab = True  # своя вкладка: без неё таблица телефонов видна под любой вкладкой полей


class ParkFormatInline(OrderedInlineMixin, TabularInline):
    model = ParkFormat
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["name", "caption", "description", "category", "order"]


class FounderFactInline(OrderedInlineMixin, TabularInline):
    model = FounderFact
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["value", "label", "order"]


class SeasonInline(StackedInline):
    """Сезонное оформление: набор сезонов фиксирован (apps/core/seasons.py) — без добавления и удаления."""

    model = Season
    template = "admin/core/season/tabs_inline.html"  # сезоны — табами, а не формами подряд
    extra = 0
    tab = True
    can_delete = False
    fields = ["status", "mode", ("start", "end"), "logo"]
    readonly_fields = ["status"]

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        # По старшинству (seasons.PRIORITY): кто важнее при пересечении дат, тот выше.
        rank = Case(
            *(When(kind=kind, then=i) for i, kind in enumerate(seasons.PRIORITY)), default=len(seasons.PRIORITY)
        )
        return super().get_queryset(request).order_by(rank)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ("start", "end"):
            field.widget.attrs["placeholder"] = "ДД.ММ"
        return field

    @admin.display(description="Сейчас")
    def status(self, obj):
        return "Показывается на сайте" if seasons.pick(Season.objects.all()) == obj else "Не показывается"


@admin.register(SiteSettings)
class SiteSettingsAdmin(SiteModelAdmin):
    help_anchor = "settings"  # списка нет — сразу форма, вводная не нужна
    inlines = [PhoneInline, SeasonInline, ParkFormatInline, FounderFactInline]
    # Unfold ставит URL-полям <input type="url">: браузер не пропустит вставленный код <iframe>.
    formfield_overrides = {MapEmbedURLField: {"widget": UnfoldAdminTextareaWidget(attrs={"rows": 3})}}
    fieldsets = (
        ("Контакты", {"classes": ["tab"], "fields": ["address", "map_embed_url", "vk_url", "max_url", "reviews_url"]}),
        ("Логотип и политика", {"classes": ["tab"], "fields": ["header_logo", "privacy_page"]}),
        (
            "Главная",
            {"classes": ["tab"], "description": texts_hint(Page.HOME), "fields": ["home_intro", "home_show_events"]},
        ),
        (
            "Мероприятия и контакты",
            {
                "classes": ["tab"],
                "description": texts_hint(Page.EVENTS, Page.CONTACTS),
                "fields": ["events_intro", "contacts_text"],
            },
        ),
        (
            "О нас",
            {
                "classes": ["tab"],
                "description": format_lazy(
                    "{} {}",
                    "Форматы и цифры основателя — на вкладках «Форматы (О нас)» и «Основатель в цифрах (О нас)».",
                    texts_hint(Page.ABOUT),
                ),
                "fields": [
                    "about_motto",
                    "about_photo",
                    "about_text",
                    ("founder_name", "founder_lead"),
                    "founder_photo",
                    "founder_text",
                    "nearby_text",
                    "safety_page",
                ],
            },
        ),
        (
            "SEO",
            {
                "classes": ["tab"],
                "description": seo_help("site"),
                "fields": [
                    "seo_title_suffix",
                    "og_image",
                    *[
                        (f"seo_{page}_title", f"seo_{page}_description")
                        for page in ("home", "events", "about", "reviews", "gallery", "contacts")
                    ],
                ],
            },
        ),
        (
            "Разметка организации",
            {
                "classes": ["tab"],
                "description": seo_help("organization"),
                "fields": [
                    ("address_region", "address_locality"),
                    ("street_address", "postal_code"),
                    ("latitude", "longitude"),
                    ("opening_hours", "price_range"),
                    "yandex_maps_url",
                ],
            },
        ),
        (
            "Вебмастер и Метрика",
            {
                "classes": ["tab"],
                "description": seo_help("webmaster"),
                "fields": ["yandex_verification", "google_verification", "yandex_metrika_id"],
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("admin:core_sitesettings_change", args=[SiteSettings.load().pk]))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        Season.ensure_for(SiteSettings.load())  # после импорта со сбросом записей сезонов нет, а добавить их нельзя
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(Announcement)
class AnnouncementAdmin(TrashAdminMixin, SiteModelAdmin):
    help_intro = (
        "Полоса с текстом и ссылкой под шапкой на всех страницах: акции, корпоративы, изменения в работе. "
        "Убрать с сайта — снять галочку «Показывать»; одновременно видна одна плашка — первая по порядку."
    )
    help_anchor = "announcements"
    list_display = ["text", "link", "starts_on", "ends_on", "is_published", "status"]
    list_editable = ["is_published"]
    list_filter = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["text", "link", "is_published", ("starts_on", "ends_on")]
    actions_list = ["trash"]

    @admin.display(description="Сейчас")
    def status(self, obj):
        current = Announcement.objects.current(seasons.today())
        return "Показывается" if current is not None and current.pk == obj.pk else "—"


@admin.register(InfoPage)
class InfoPageAdmin(TrashAdminMixin, SiteModelAdmin):
    help_intro = (
        "Отдельные страницы с текстом: правила, политика конфиденциальности, вопросы и ответы. В меню их нет; "
        "ссылка внизу сайта — галочка «В подвале», другие ссылки — в «Настройках сайта» или копируются из формы. "
        "Вид страницы — поле «Оформление»."
    )
    help_anchor = "info-pages"
    list_display = ["title", "page_url", "layout", "show_in_footer", "is_published"]
    list_editable = ["show_in_footer", "is_published"]
    list_filter = ["is_published", "show_in_footer"]
    # Порядок — в списке админки и ссылок в подвале.
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (
            "Основное",
            {
                "classes": ["tab"],
                "fields": [
                    "title",
                    "slug",
                    "page_url",
                    "lead",
                    "cover",
                    "layout",
                    "body",
                    "show_in_footer",
                    "is_published",
                ],
            },
        ),
        SEO_FIELDSET,
    )
    readonly_fields = ["page_url"]
    actions_list = ["trash"]

    class Media:
        js = ["js/admin_copy.js"]

    @admin.display(description="Ссылка на страницу")
    def page_url(self, obj):
        if not obj.pk:
            return "Появится после сохранения"
        return copy_url_button(obj.get_absolute_url())


@admin.register(Redirect)
class RedirectAdmin(SiteModelAdmin):
    help_intro = (
        "Перенаправления со старых адресов на новые. Создаются сами, когда меняют «Адрес страницы»; "
        "вручную добавлять нужно редко."
    )
    help_anchor = "basics"
    list_display = ["old_path", "new_path", "created_at"]
    search_fields = ["old_path", "new_path"]
    fields = ["old_path", "new_path"]


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, SiteModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    help_intro = "Учётные записи для входа в админку."
    help_anchor = "access"


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, SiteModelAdmin):
    help_intro = "Наборы прав: какие разделы пользователь может смотреть и менять."
    help_anchor = "access"
