from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Сайт"

    def ready(self):
        from apps.core.files import register_file_cleanup
        from apps.core.models import SiteSettings

        register_file_cleanup(SiteSettings)
