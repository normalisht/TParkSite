from django.db.models import Prefetch

from apps.catalog.models import Category, CategoryGroup


def menu(request):
    groups = CategoryGroup.objects.prefetch_related(
        Prefetch(
            "categories",
            queryset=Category.objects.published().order_by("order", "id"),
            to_attr="published_categories",
        )
    )
    return {"menu_groups": [g for g in groups if g.published_categories]}
