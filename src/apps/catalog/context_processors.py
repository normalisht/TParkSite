from django.db.models import Prefetch

from apps.catalog.models import Category, CategoryGroup

FOOTER_CATEGORIES = 8


def menu(request):
    groups = CategoryGroup.objects.published().prefetch_related(
        Prefetch(
            "categories",
            queryset=Category.objects.published().order_by("order", "id"),
            to_attr="published_categories",
        )
    )
    menu_groups = [g for g in groups if g.published_categories]
    # Категории подвала: в порядке меню, без повторов (категория может быть в нескольких группах).
    footer_categories = list({c.pk: c for g in menu_groups for c in g.published_categories}.values())
    return {"menu_groups": menu_groups, "footer_categories": footer_categories[:FOOTER_CATEGORIES]}
