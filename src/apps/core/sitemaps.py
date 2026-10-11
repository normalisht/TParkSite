from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core.models import InfoPage, SiteSettings


class StaticSitemap(Sitemap):
    PAGES = [
        "catalog:home",
        "content:events",
        "content:about",
        "content:reviews",
        "content:gallery",
        "content:contacts",
    ]

    def items(self):
        return self.PAGES

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        # Sitemap зовёт lastmod дважды на страницу (для заголовка Last-Modified и для самой записи), а Sitemap
        # создаётся на каждый запрос: считаем даты один раз и кладём в экземпляр.
        if not hasattr(self, "_lastmods"):
            self._lastmods = self._compute_lastmods()
        return self._lastmods[item]

    @staticmethod
    def _newest(queryset):
        return queryset.aggregate(newest=Max("updated_at"))["newest"]

    def _compute_lastmods(self) -> dict:
        """Дата изменения каждой статической страницы по тому, из чего она собрана.

        Тексты «О нас» и «Контакты» живут в настройках сайта; главная — настройки, опубликованные категории и
        мероприятия; «Мероприятия» — настройки и видимые мероприятия. У отзывов и галереи своей даты изменения
        нет, поэтому для них lastmod не отдаём: ложная дата хуже её отсутствия.
        """
        settings_at = SiteSettings.load().updated_at
        events_at = self._newest(Event.objects.published().visible())
        categories_at = self._newest(Category.objects.published())

        def latest(*dates):
            return max((d for d in dates if d), default=None)

        return {
            "catalog:home": latest(settings_at, categories_at, events_at),
            "content:events": latest(settings_at, events_at),
            "content:about": settings_at,
            "content:contacts": settings_at,
            "content:reviews": None,
            "content:gallery": None,
        }


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
