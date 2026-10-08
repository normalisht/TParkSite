"""Загрузка нескольких фото одним полем: валидация всей пачки, добавление в конец списка."""

from django import forms
from django.db.models import Max
from unfold.widgets import UnfoldAdminImageFieldWidget

from apps.core.fields import validate_image_upload


class MultipleImageInput(UnfoldAdminImageFieldWidget):
    """Виджет Unfold (как у обычных полей фото) — в нём работает перетаскивание из admin_dropzone.js."""

    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "help_text", "Можно выбрать несколько файлов: jpg, png или webp, до 20 МБ. Фото добавятся в конец списка."
        )
        super().__init__(*args, **kwargs)
        self.widget.attrs.setdefault("accept", "image/jpeg,image/png,image/webp")

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = []
        for file in files:
            file = super().clean(file, initial)
            validate_image_upload(file)
            cleaned.append(file)
        if self.required and not cleaned:
            raise forms.ValidationError("Выберите хотя бы один файл.")
        return cleaned


class BulkUploadForm(forms.Form):
    photos = MultipleImageField(label="Фото", required=True)


def append_images(model, files, **parent) -> list:
    """Создаёт записи `model(image=file, order=…, **parent)` после текущего максимума order."""
    start = (model.objects.filter(**parent).aggregate(m=Max("order"))["m"] or 0) + 1
    return [model.objects.create(image=file, order=start + i, **parent) for i, file in enumerate(files)]
