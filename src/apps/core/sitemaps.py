from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core.models import InfoPage, SiteSettings


class StaticSitemap(Sitemap):
    def items(self):
        return [
            "catalog:home",
            "content:events",
            "content:about",
            "content:reviews",
            "content:gallery",
            "content:contacts",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        # Тексты и SEO статических страниц хранятся в настройках сайта.
        return SiteSettings.load().updated_at


class ModelSitemap(Sitemap):
    """Страницы моделей с `SeoModel.updated_at`: lastmod подсказывает поисковикам, что переобойти."""

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(ModelSitemap):
    def items(self):
        return Category.objects.published().order_by("order", "id")


class ServiceSitemap(ModelSitemap):
    def items(self):
        # Только услуги, которые видно через навигацию: со своей страницей и хотя бы в одной опубликованной категории.
        return (
            Service.objects.published()
            .filter(has_page=True, category_links__category__is_published=True)
            .distinct()
            .order_by("id")
        )


class InfoPageSitemap(ModelSitemap):
    def items(self):
        return InfoPage.objects.published().order_by("id")


class EventSitemap(ModelSitemap):
    def items(self):
        return Event.objects.published().visible().order_by("-date", "-id")


SITEMAPS = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "services": ServiceSitemap,
    "info": InfoPageSitemap,
    "events": EventSitemap,
}
