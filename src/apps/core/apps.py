from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Сайт"

    def ready(self):
        from django.core.signals import request_finished, request_started
        from django.db.backends.signals import connection_created

        from apps.core import images, search
        from apps.core.files import register_file_cleanup
        from apps.core.models import InfoPage, Season, SiteSettings

        register_file_cleanup(SiteSettings)
        register_file_cleanup(InfoPage)
        register_file_cleanup(Season)
        request_started.connect(images.start_request_budget, dispatch_uid="thumbnail-budget-start")
        request_finished.connect(images.end_request_budget, dispatch_uid="thumbnail-budget-end")
        connection_created.connect(search.register, dispatch_uid="tp-fold")
