from django.db.models.signals import post_delete, post_save
from django.utils import timezone

from apps.content.models import VideoCollection, VideoCollectionItem


def touch_collection(sender, instance, **kwargs):
    """Ролик добавлен в подборку, убран или переставлен — страница подборки изменилась (lastmod в sitemap).

    Через update(): save() подборки ради одной даты снова слал бы IndexNow и проверял slug.
    """
    VideoCollection.objects.filter(pk=instance.collection_id).update(updated_at=timezone.now())


def connect_collection_signals():
    # Сигналы, а не save()/delete() модели: каскад при удалении ролика delete() связей не вызывает.
    post_save.connect(touch_collection, sender=VideoCollectionItem, dispatch_uid="touch-collection-save")
    post_delete.connect(touch_collection, sender=VideoCollectionItem, dispatch_uid="touch-collection-delete")
