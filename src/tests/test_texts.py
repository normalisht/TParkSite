import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.db import connection
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Service
from apps.core.models import Phone, SiteSettings
from apps.texts.context_processors import site_texts
from apps.texts.models import SiteText
from apps.texts.registry import BY_KEY, TEXTS, Page, sync_texts

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_text():
    return SiteText.objects.create(key="test.sample", page="common", label="Проба", text="Было", order=0)


def test_admin_edit_records_version_with_author(admin_client, admin_user, site_text):
    response = admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    assert response.status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Стало"
    latest = site_text.history.first()
    assert latest.history_type == "~" and latest.history_user == admin_user and latest.text == "Стало"


def test_revert_restores_old_version_as_new_one(admin_client, site_text):
    admin_client.post(reverse("admin:texts_sitetext_change", args=[site_text.pk]), {"text": "Стало"})
    first = site_text.history.earliest("history_date")
    url = reverse("admin:texts_sitetext_simple_history", args=[site_text.pk, first.history_id])
    assert admin_client.get(url).status_code == 200
    assert admin_client.post(url, {"text": first.text}).status_code == 302
    site_text.refresh_from_db()
    assert site_text.text == "Было"
    assert site_text.history.count() == 3


def test_history_page_opens(admin_client, site_text):
    assert admin_client.get(reverse("admin:texts_sitetext_history", args=[site_text.pk])).status_code == 200


def test_registry_keys_unique_and_pages_known():
    assert len(TEXTS) == len(BY_KEY) == 48
    assert {item.page for item in TEXTS} <= set(Page.values)


def test_migration_created_all_texts_with_initial_version():
    assert dict(SiteText.objects.values_list("key", "text")) == {item.key: item.default for item in TEXTS}
    initial = SiteText.history.filter(history_type="+")
    assert initial.count() == len(TEXTS)
    assert set(initial.values_list("history_change_reason", flat=True)) == {"Начальный текст"}


def test_sync_keeps_edits_restores_labels_and_missing_rows():
    edited = SiteText.objects.get(key="service.booking_hint")
    edited.text, edited.label = "Свой текст", "Старое название"
    edited.save()
    SiteText.objects.filter(key="gallery.empty").delete()
    history = SiteText.history.model

    assert sync_texts(SiteText, history) == 1
    edited.refresh_from_db()
    assert edited.text == "Свой текст" and edited.label == BY_KEY["service.booking_hint"].label
    restored = SiteText.objects.get(key="gallery.empty")
    assert restored.text == BY_KEY["gallery.empty"].default and restored.page == "gallery"
    assert history.objects.filter(id=restored.pk, history_type="+").count() == 1
    assert sync_texts(SiteText, history) == 0


def _render(source: str, with_db: bool = True) -> str:
    context = site_texts(RequestFactory().get("/")) if with_db else {}
    return Template("{% load site_texts %}" + source).render(Context(context))


def test_tag_outputs_db_text_with_nobr():
    SiteText.objects.filter(key="home.cta_title").update(text="Ждём в Т-Парке")
    assert _render('{% text "home.cta_title" %}') == 'Ждём в <span class="whitespace-nowrap">Т-Парке</span>'


def test_tag_escapes_html():
    SiteText.objects.filter(key="home.cta_title").update(text='<b>Жирно</b> & "кавычки"')
    assert _render('{% text "home.cta_title" %}') == "&lt;b&gt;Жирно&lt;/b&gt; &amp; &quot;кавычки&quot;"


def test_tag_falls_back_to_default_without_row_or_context():
    SiteText.objects.all().delete()
    default = BY_KEY["home.events_title"].default
    assert _render('{% text "home.events_title" %}') == default
    with CaptureQueriesContext(connection) as queries:
        assert _render('{% text "home.events_title" %}', with_db=False) == default
    assert len(queries) == 0


def test_empty_required_text_falls_back_to_default():
    SiteText.objects.filter(key="home.events_title").update(text="")
    assert _render('{% text "home.events_title" %}') == "Ближайшие мероприятия"


def test_empty_optional_text_hides_block():
    SiteText.objects.filter(key="service.booking_hint").update(text="")
    source = '{% text "service.booking_hint" as hint %}{% if hint %}<p>{{ hint }}</p>{% endif %}'
    assert _render(source) == ""


def test_as_stores_plain_string():
    assert _render('{% text "home.cta_title" as title %}[{{ title }}]') == "[Приезжайте в Т-Парк]"


@pytest.mark.parametrize("source", ['{% text "nope.missing" %}', "{% text home.title %}", '{% text "home.title" as %}'])
def test_bad_tag_fails_at_compile_time(source):
    with pytest.raises(TemplateSyntaxError):
        Template("{% load site_texts %}" + source)


def test_all_texts_loaded_with_one_query():
    with CaptureQueriesContext(connection) as queries:
        _render('{% text "home.title" %}{% text "home.events_title" %}{% text "home.reviews_title" %}')
    assert len([q for q in queries if "texts_sitetext" in q["sql"]]) == 1


def _change_url(key: str) -> str:
    return reverse("admin:texts_sitetext_change", args=[SiteText.objects.get(key=key).pk])


def test_change_form_shows_where_and_default(admin_client):
    html = admin_client.get(_change_url("service.booking_hint")).content.decode()
    assert "Страница услуги, под ценой и кнопками связи" in html
    assert "Бронируйте заранее — в тёплый сезон даты разбирают быстро." in html
    assert "Пусто — блок на сайте скрыт" in html


def test_required_text_cannot_be_emptied(admin_client):
    response = admin_client.post(_change_url("home.events_title"), {"text": "  "})
    assert response.status_code == 200
    assert SiteText.objects.get(key="home.events_title").text == "Ближайшие мероприятия"


def test_optional_text_can_be_emptied_and_is_stripped(admin_client):
    assert admin_client.post(_change_url("service.booking_hint"), {"text": ""}).status_code == 302
    assert SiteText.objects.get(key="service.booking_hint").text == ""
    admin_client.post(_change_url("service.booking_hint"), {"text": "  Звоните заранее.\n"})
    assert SiteText.objects.get(key="service.booking_hint").text == "Звоните заранее."


def test_no_add_or_delete(admin_client):
    model_admin = admin.site._registry[SiteText]
    request = RequestFactory().get("/")
    request.user = User.objects.get(is_superuser=True)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_changelist_filters_by_page_and_links_settings(admin_client):
    html = admin_client.get(reverse("admin:texts_sitetext_changelist") + "?page__exact=gallery").content.decode()
    assert "Фото скоро появятся." in html and "Отзывов пока нет." not in html
    assert reverse("admin:core_sitesettings_changelist") in html


def test_initial_version_shows_dash_instead_of_none(admin_client):
    url = reverse("admin:texts_sitetext_history", args=[SiteText.objects.get(key="gallery.empty").pk])
    html = admin_client.get(url).content.decode()
    assert "Начальный текст" in html
    assert not re.search(r">\s*None\s*<", html) and "/user/None/" not in html


def test_history_page_is_russian(admin_client):
    url = reverse("admin:texts_sitetext_history", args=[SiteText.objects.get(key="gallery.empty").pk])
    html = admin_client.get(url).content.decode()
    for english in ("Changed by", "Date/time", "Change reason", "Changes"):
        assert english not in html, english


TEXT_TAG = re.compile(r"""\{%\s*text\s+["']([\w.]+)["']""")


def test_registry_matches_templates():
    used = set()
    for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
        used |= set(TEXT_TAG.findall(path.read_text(encoding="utf-8")))
    assert used == set(BY_KEY)


def _service_page(client) -> str:
    Phone.objects.create(settings=SiteSettings.load(), number="9029856594")
    service = Service.objects.create(name="Сплав", price="2000", has_page=True)
    return client.get(service.get_absolute_url()).content.decode()


def test_edited_text_shows_on_site_and_empty_hides_block(client):
    assert "Бронируйте заранее" in _service_page(client)
    SiteText.objects.filter(key="service.booking_hint").update(text="Звоните заранее.")
    html = client.get(Service.objects.get().get_absolute_url()).content.decode()
    assert "Звоните заранее." in html and "Бронируйте" not in html
    SiteText.objects.filter(key="service.booking_hint").update(text="")
    html = client.get(Service.objects.get().get_absolute_url()).content.decode()
    assert "Звоните заранее." not in html and 'text-sm text-ink/65"></p>' not in html


def test_pages_render_defaults_when_table_is_empty(client):
    SiteText.objects.all().delete()
    assert "Кажется, вы сошли с тропы" in client.get("/no-such-page/").content.decode()
    assert "Скоро анонсируем новые мероприятия" in client.get("/events/").content.decode()
