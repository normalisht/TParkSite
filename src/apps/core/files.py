"""Удаление файлов вместе с записью и при замене файла — только после коммита транзакции,
чтобы откат (например, неудачный импорт) не оставлял записи без файлов.

Вместе с фото удаляются и его миниатюры imagekit (`CACHE/images/<путь фото>/`)."""

import os

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models.signals import post_delete, pre_save
from imagekit.cachefiles import ImageCacheFile
from imagekit.models.fields.utils import ImageSpecFileDescriptor


def _file_fields(model):
    return [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]


def _spec_descriptors(model) -> list[ImageSpecFileDescriptor]:
    return [
        attr for klass in model.__mro__ for attr in vars(klass).values() if isinstance(attr, ImageSpecFileDescriptor)
    ]


def _thumbnails(specs, field_name: str, field_file) -> list[ImageCacheFile]:
    """Миниатюры файла по всем спекам поля; имена считаются из имени исходника, сами файлы не нужны."""
    return [
        ImageCacheFile(spec.field.get_spec(source=field_file)) for spec in specs if spec.source_field_name == field_name
    ]


def _remove_thumbnail(thumb: ImageCacheFile) -> None:
    thumb.storage.delete(thumb.name)
    backend = thumb.cachefile_backend
    backend.cache.delete(backend.get_key(thumb))  # imagekit помнит «файл есть» без срока
    try:
        os.rmdir(os.path.dirname(thumb.storage.path(thumb.name)))  # папка миниатюр этого фото, если опустела
    except OSError, NotImplementedError:
        pass


def _delete_later(field_file, thumbnails=()) -> None:
    if field_file and field_file.name:
        storage, name, thumbnails = field_file.storage, field_file.name, list(thumbnails)

        def delete():
            storage.delete(name)
            for thumb in thumbnails:
                _remove_thumbnail(thumb)

        transaction.on_commit(delete)


def register_file_cleanup(model) -> None:
    fields = _file_fields(model)
    specs = _spec_descriptors(model)

    def delete_later(field, field_file):
        _delete_later(field_file, _thumbnails(specs, field.name, field_file) if field_file else ())

    def on_delete(sender, instance, **kwargs):
        for field in fields:
            delete_later(field, getattr(instance, field.name))

    def on_save(sender, instance, **kwargs):
        if not instance.pk:
            return
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is None:
            return
        for field in fields:
            old_file, new_file = getattr(old, field.name), getattr(instance, field.name)
            if old_file and old_file.name != (new_file.name if new_file else None):
                delete_later(field, old_file)

    post_delete.connect(on_delete, sender=model, weak=False, dispatch_uid=f"cleanup-delete-{model._meta.label}")
    pre_save.connect(on_save, sender=model, weak=False, dispatch_uid=f"cleanup-save-{model._meta.label}")


def clone_file(field_file) -> ContentFile | None:
    """Копия файла для новой записи: общий файл у двух записей нельзя — удаление одной стёрло бы его у другой.
    Новое имя даст `upload_to` поля. Файла нет на диске — None."""
    if not field_file:
        return None
    try:
        with field_file.storage.open(field_file.name, "rb") as source:
            return ContentFile(source.read(), name=os.path.basename(field_file.name))
    except OSError:  # в т. ч. FileNotFoundError
        return None
