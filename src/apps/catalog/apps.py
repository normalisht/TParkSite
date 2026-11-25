from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    verbose_name = "Каталог"

    def ready(self):
        from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, ServicePhoto
        from apps.core.files import register_file_cleanup

        for model in (CategoryGroup, Category, CategoryPhoto, ServicePhoto):
            register_file_cleanup(model)
