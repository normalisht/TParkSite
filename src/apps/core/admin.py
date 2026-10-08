from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet, ModelForm
from django.shortcuts import redirect
from django.urls import reverse
from unfold.admin import TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from unfold.widgets import UnfoldAdminTextareaWidget

from apps.core.admin_utils import SiteModelAdmin, copy_url_button
from apps.core.maps import MapEmbedURLField
from apps.core.models import InfoPage, Phone, SiteSettings

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


class PhoneInline(TabularInline):
    model = Phone
    form = PhoneForm
    formset = PhoneFormSet
    extra = 0
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["number", "is_whatsapp", "is_telegram", "order"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(SiteModelAdmin):
    inlines = [PhoneInline]
    # Unfold ставит URL-полям <input type="url">: браузер не пропустит вставленный код <iframe>.
    formfield_overrides = {MapEmbedURLField: {"widget": UnfoldAdminTextareaWidget(attrs={"rows": 3})}}
    fieldsets = (
        ("Контакты", {"classes": ["tab"], "fields": ["address", "map_embed_url", "vk_url", "reviews_url"]}),
        (
            "Тексты",
            {
                "classes": ["tab"],
                "fields": [
                    "home_intro",
                    "events_intro",
                    "about_text",
                    "philosophy_text",
                    "nearby_text",
                    "contacts_text",
                ],
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("admin:core_sitesettings_change", args=[SiteSettings.load().pk]))


@admin.register(InfoPage)
class InfoPageAdmin(SiteModelAdmin):
    list_display = ["title", "page_url", "is_published"]
    list_editable = ["is_published"]
    list_filter = ["is_published"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    fields = ["title", "slug", "page_url", "body", "is_published"]
    readonly_fields = ["page_url"]

    class Media:
        js = ["js/admin_copy.js"]

    @admin.display(description="Ссылка на страницу")
    def page_url(self, obj):
        if not obj.pk:
            return "Появится после сохранения"
        return copy_url_button(obj.get_absolute_url())


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, SiteModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, SiteModelAdmin):
    pass
