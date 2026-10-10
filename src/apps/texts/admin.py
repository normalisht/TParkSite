from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from simple_history.admin import SimpleHistoryAdmin

from apps.core.admin_utils import SiteModelAdmin
from apps.texts.models import SiteText
from apps.texts.registry import BY_KEY


class SiteTextForm(forms.ModelForm):
    class Meta:
        model = SiteText
        fields = ["text"]

    def clean_text(self):
        text = self.cleaned_data["text"]  # форма уже обрезала пробелы и переводы строк по краям
        item = BY_KEY.get(self.instance.key)
        if not text and item and item.required:
            raise forms.ValidationError("Этот текст обязателен: без него на сайте останется пустой заголовок.")
        return text


@admin.register(SiteText)
class SiteTextAdmin(SimpleHistoryAdmin, SiteModelAdmin):
    form = SiteTextForm
    list_display = ["label", "page", "short_text", "updated_at"]
    list_filter = ["page"]
    search_fields = ["label", "text", "key"]
    fields = ["label", "page", "where", "text", "default_text", "key"]
    readonly_fields = ["label", "page", "where", "default_text", "key"]
    list_before_template = "admin/texts/list_before.html"

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 80 else obj.text[:79] + "…"

    @admin.display(description="Где на сайте")
    def where(self, obj):
        item = BY_KEY.get(obj.key)
        return item.where if item else "—"

    @admin.display(description="Текст по умолчанию")
    def default_text(self, obj):
        item = BY_KEY.get(obj.key)
        return item.default if item else "—"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        item = BY_KEY.get(obj.key) if obj else None
        text = form.base_fields["text"]
        text.widget.attrs["rows"] = 3
        text.help_text = "Обязательный текст." if item is None or item.required else "Пусто — блок на сайте скрыт."
        return form

    def history_form_view(self, request, object_id, version_id, extra_context=None):
        # simple-history сохраняет «Восстановить» при праве на просмотр истории — без права на изменение не даём.
        if request.method == "POST" and not self.has_change_permission(request):
            raise PermissionDenied
        return super().history_form_view(request, object_id, version_id, extra_context)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
