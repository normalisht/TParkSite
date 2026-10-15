"""Корзина: «Удалить» в админке у основных записей переносит их сюда (`TrashableModel.move_to_trash`).

Через `TRASH_DAYS` дней запись удаляется навсегда — `purge_expired` вызывается при открытии корзины и при каждом
переносе в неё, отдельный планировщик не нужен."""

from datetime import timedelta

from django.utils import timezone

TRASH_DAYS = 30


def purge_expired(model, now=None) -> int:
    limit = (now or timezone.now()) - timedelta(days=TRASH_DAYS)
    # QuerySet.delete шлёт post_delete по каждой записи — файлы фото удаляются после коммита (apps/core/files.py).
    _total, per_model = model._default_manager.filter(deleted_at__lt=limit).delete()
    return per_model.get(model._meta.label, 0)
