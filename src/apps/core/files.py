"""Удаление файлов вместе с записью и при замене файла — только после коммита транзакции,
чтобы откат (например, неудачный импорт) не оставлял записи без файлов."""

from django.db import models, transaction
from django.db.models.signals import post_delete, pre_save


def _file_fields(model):
    return [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]


def _delete_later(field_file) -> None:
    if field_file and field_file.name:
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))


def register_file_cleanup(model) -> None:
    fields = _file_fields(model)

    def on_delete(sender, instance, **kwargs):
        for field in fields:
            _delete_later(getattr(instance, field.name))

    def on_save(sender, instance, **kwargs):
        if not instance.pk:
            return
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is None:
            return
        for field in fields:
            old_file, new_file = getattr(old, field.name), getattr(instance, field.name)
            if old_file and old_file.name != (new_file.name if new_file else None):
                _delete_later(old_file)

    post_delete.connect(on_delete, sender=model, weak=False, dispatch_uid=f"cleanup-delete-{model._meta.label}")
    pre_save.connect(on_save, sender=model, weak=False, dispatch_uid=f"cleanup-save-{model._meta.label}")
