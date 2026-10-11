"""Смена адреса страницы (slug): старый адрес продолжает работать — 301 на новый (`RedirectFallbackMiddleware`)."""

from apps.core.models import Redirect


def remember_slug_change(instance) -> None:
    """Вызывать в `save()` модели со slug и `get_absolute_url()` — до записи, когда slug уже заполнен."""
    if instance.pk is None:
        return
    old_slug = type(instance)._default_manager.filter(pk=instance.pk).values_list("slug", flat=True).first()
    if not old_slug or old_slug == instance.slug:
        return
    old_path = type(instance)(slug=old_slug).get_absolute_url()
    new_path = instance.get_absolute_url()
    Redirect.objects.filter(old_path=new_path).delete()  # вернули прежний адрес — редирект с него больше не нужен
    Redirect.objects.filter(new_path=old_path).update(new_path=new_path)  # без цепочек редиректов
    Redirect.objects.update_or_create(old_path=old_path, defaults={"new_path": new_path})
