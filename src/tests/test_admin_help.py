import re

import pytest
from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.urls import resolve, reverse

from apps.catalog.models import Category, CategoryGroup, Service
from apps.content.models import GalleryPhoto, Partner, Review
from apps.core.admin import SiteSettingsAdmin
from apps.core.admin_help import HELP_ANCHORS, HELP_SECTIONS
from apps.core.models import InfoPage, Phone, SiteSettings
from apps.texts.models import SiteText
from apps.texts.registry import BY_KEY

pytestmark = pytest.mark.django_db


def _help_html(client) -> str:
    response = client.get(reverse("admin_help"))
    assert response.status_code == 200
    return response.content.decode()


def test_help_requires_staff(client, django_user_model):
    url = reverse("admin_help")
    login = reverse("admin:login")
    assert client.get(url).url.startswith(login)
    django_user_model.objects.create_user("guest", password="p")
    client.login(username="guest", password="p")
    assert client.get(url).url.startswith(login)


def test_help_open_for_plain_staff(client, django_user_model):
    django_user_model.objects.create_user("staff", password="p", is_staff=True)
    client.login(username="staff", password="p")
    assert "Как устроен сайт" in _help_html(client)


def test_sidebar_links_to_help(admin_client):
    html = admin_client.get(reverse("admin:index")).content.decode()
    assert f'href="{reverse("admin_help")}"' in html


def test_toc_points_to_existing_sections(admin_client):
    html = _help_html(admin_client)
    ids = set(re.findall(r'<section id="([\w-]+)"', html))
    assert ids == HELP_ANCHORS
    toc = re.findall(r'href="#([\w-]+)"', html)
    assert set(toc) - {"toc"} == HELP_ANCHORS
    assert [s.anchor for s in HELP_SECTIONS] == list(dict.fromkeys(a for a in toc if a != "toc"))


def test_help_admin_links_open(admin_client):
    html = _help_html(admin_client)
    links = sorted(set(re.findall(r'href="(/admin/[^"#]*)', html)) - {reverse("admin_help")})
    assert links
    for link in links:
        response = admin_client.get(link.replace("&amp;", "&"), follow=True)
        assert response.status_code == 200, link


def test_help_covers_basics_photos_catalog(admin_client):
    html = _help_html(admin_client)
    for anchor in ("basics", "photos", "catalog"):
        assert f'<section id="{anchor}">' in html
    for phrase in ("перетаскиванием", "20 МБ", "16:9", "Отдельная страница", "«Ещё в категории»"):
        assert phrase in html, phrase


def test_help_covers_events_reviews_gallery(admin_client):
    html = _help_html(admin_client)
    for anchor in ("events", "reviews", "gallery"):
        assert f'<section id="{anchor}">' in html
    for phrase in ("«Показывать после даты»", "«Подтянуть»", "«Гость Т-Парка»", "«О нас»"):
        assert phrase in html, phrase


EXPECTED_SECTIONS = [
    "structure",
    "not-visible",
    "basics",
    "photos",
    "catalog",
    "events",
    "reviews",
    "gallery",
    "settings",
    "texts",
    "info-pages",
    "seo",
    "access",
]


def test_help_sections_complete(admin_client):
    assert [s.anchor for s in HELP_SECTIONS] == EXPECTED_SECTIONS
    html = _help_html(admin_client)
    for phrase in ("WhatsApp", "«Восстановить»", "[укажите", "Вебмастер", "30 минут"):
        assert phrase in html, phrase


def _sidebar_admins():
    for group in settings.UNFOLD["SIDEBAR"]["navigation"]:
        for item in group["items"]:
            model_admin = getattr(resolve(str(item["link"])).func, "model_admin", None)
            if model_admin is not None:
                yield model_admin


def test_every_sidebar_section_has_help():
    admins = list(_sidebar_admins())
    assert len(admins) == 13
    for model_admin in admins:
        assert model_admin.help_anchor in HELP_ANCHORS, model_admin
        if not isinstance(model_admin, SiteSettingsAdmin):
            assert model_admin.help_intro, model_admin


def test_help_anchors_exist():
    for model_admin in admin.site._registry.values():
        if getattr(model_admin, "help_anchor", ""):
            assert model_admin.help_anchor in HELP_ANCHORS, model_admin


def test_changelist_shows_intro_and_help_link(admin_client):
    html = admin_client.get(reverse("admin:content_galleryphoto_changelist")).content.decode()
    assert "Как это выглядит" in html
    assert f"{reverse('admin_help')}#gallery" in html


def test_every_admin_form_links_to_help(admin_client):
    for model, model_admin in admin.site._registry.items():
        if not getattr(model_admin, "help_anchor", ""):
            continue
        info = (model._meta.app_label, model._meta.model_name)
        response = admin_client.get(reverse("admin:{}_{}_changelist".format(*info)), follow=True)
        if model_admin.has_add_permission(response.wsgi_request):
            response = admin_client.get(reverse("admin:{}_{}_add".format(*info)))
        html = response.content.decode()
        assert f"{reverse('admin_help')}#{model_admin.help_anchor}" in html, model


def _help(model, field):
    return str(model._meta.get_field(field).help_text)


def test_fields_explain_where_they_show():
    assert "без даты" in _help(Review, "date")
    assert "кружок" in _help(Review, "photo")
    assert "без обрезки" in _help(Partner, "logo")
    assert "плитка" in _help(Partner, "name")
    assert "квадрат" in _help(GalleryPhoto, "image")
    assert "весь экран" in _help(GalleryPhoto, "caption")
    assert "только у одного" in _help(Phone, "is_whatsapp")
    assert "только у одного" in _help(Phone, "is_telegram")
    assert "Связаться" in _help(Phone, "number")
    assert "подвале" in _help(InfoPage, "is_published")
    assert "меню «Услуги»" in _help(CategoryGroup, "name")
    assert "под заголовком" in _help(Category, "description")
    assert "подвал" in _help(SiteSettings, "address")
    assert "поисковиков" in _help(SiteSettings, "home_intro")


def test_fixed_hints_match_site():
    assert "Все отзывы на Яндекс Картах" in _help(SiteSettings, "reviews_url")
    assert "Снятая — услуги нет на сайте" in _help(Service, "is_published")
    assert "«О нас»" in _help(SiteSettings, "safety_page")
    assert "cookie" in _help(SiteSettings, "privacy_page")
    assert "рядом с «© Т-Парк»" in _help(InfoPage, "show_in_footer")
    assert "прямой ссылке" in _help(Service, "is_published")
    assert "Отзывы" in BY_KEY["common.photo_strip_title"].where


def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run", verbosity=0)


def test_help_text_has_no_wrong_claims(admin_client):
    html = _help_html(admin_client)
    assert "маленькие не растягивает" not in html
    assert "размытыми" in html
    assert "у неё сменился адрес. Старый адрес сам ведёт на новый" not in html


def test_texts_intro_and_form_link(admin_client):
    html = admin_client.get(reverse("admin:texts_sitetext_changelist")).content.decode()
    assert "Короткие фразы и заголовки блоков витрины." in html
    intro = html.split("Короткие фразы и заголовки блоков витрины.", 1)[1].split("</p>", 1)[0]
    assert reverse("admin:core_sitesettings_changelist") in intro
    text = SiteText.objects.first()
    html = admin_client.get(reverse("admin:texts_sitetext_change", args=[text.pk])).content.decode()
    assert f"{reverse('admin_help')}#texts" in html
