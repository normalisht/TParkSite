from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = "apps.content"
    verbose_name = "Контент"

    def ready(self):
        from apps.content.models import Event, GalleryPhoto, Partner, Review
        from apps.core.files import register_file_cleanup

        for model in (Event, Review, Partner, GalleryPhoto):
            register_file_cleanup(model)
