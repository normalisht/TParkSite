from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core.models import InfoPage


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


class CategorySitemap(Sitemap):
    def items(self):
        return Category.objects.published().order_by("order", "id")


class ServiceSitemap(Sitemap):
    def items(self):
        return Service.objects.published().filter(has_page=True).order_by("id")


class InfoPageSitemap(Sitemap):
    def items(self):
        return InfoPage.objects.published().order_by("id")


class EventSitemap(Sitemap):
    def items(self):
        return Event.objects.visible().order_by("-date", "-id")


SITEMAPS = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "services": ServiceSitemap,
    "info": InfoPageSitemap,
    "events": EventSitemap,
}
