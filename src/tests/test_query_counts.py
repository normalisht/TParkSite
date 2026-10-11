"""Число запросов к БД не растёт с числом услуг и не повторяется на каждый шаблон админки."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Category, CategoryService, Service
from apps.core.models import SiteSettings

pytestmark = pytest.mark.django_db


def _queries_to(table: str, client, url: str) -> int:
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return sum(f'"{table}"' in q["sql"] for q in ctx.captured_queries)


def _category_with_services(n: int) -> Category:
    category = Category.objects.create(name=f"Парк {n}", is_published=True)
    for i in range(n):
        service = Service.objects.create(name=f"Услуга {n}-{i}", price="100")
        CategoryService.objects.create(category=category, service=service)
    return category


def test_category_page_settings_queries_do_not_grow_with_services(client):
    SiteSettings.load()
    small, big = _category_with_services(1), _category_with_services(6)
    small_count = _queries_to("core_sitesettings", client, small.get_absolute_url())
    assert _queries_to("core_sitesettings", client, big.get_absolute_url()) == small_count
    assert small_count <= 2  # контекст-процессор + make_seo (окончание заголовка)


def test_admin_form_loads_settings_once_per_request(admin_client):
    SiteSettings.load()
    category = Category.objects.create(name="Парк")
    url = reverse("admin:catalog_category_change", args=[category.pk])
    assert _queries_to("core_sitesettings", admin_client, url) <= 2  # контекст-процессор + справка SEO-вкладки
    # Меню витрины — 1; после задачи 6 поле «Группы меню» добавит ещё 2 (варианты и отмеченные). Без кеша — 5–6.
    assert _queries_to("catalog_categorygroup", admin_client, url) <= 3
