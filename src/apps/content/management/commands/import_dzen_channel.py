from django.core.management.base import BaseCommand

from apps.catalog.models import Service
from apps.content.dzen_import import import_channel, load_channel
from apps.content.models import Video, VideoCollection, VideoCollectionItem


class Command(BaseCommand):
    help = (
        "Переносит ролики и подборки канала Дзена из apps/content/data/dzen_channel.json. Повторный запуск ничего "
        "не дублирует и докачивает обложки, которые не скачались (ролик без обложки — черновик)."
    )

    def handle(self, *args, **options):
        import_channel(
            Video=Video,
            VideoCollection=VideoCollection,
            VideoCollectionItem=VideoCollectionItem,
            Service=Service,
            data=load_channel(),
            log=self.stdout.write,
        )
