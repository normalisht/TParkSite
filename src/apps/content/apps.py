from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = "apps.content"
    verbose_name = "Контент"

    def ready(self):
        from apps.content.models import Event, GalleryPhoto, Partner, Review, Video, VideoCollection
        from apps.content.signals import connect_collection_signals
        from apps.core.files import register_file_cleanup

        connect_collection_signals()

        for model in (Event, Review, Partner, GalleryPhoto, Video, VideoCollection):
            register_file_cleanup(model)
