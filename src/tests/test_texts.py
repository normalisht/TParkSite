import pytest
from django.db import connection
from django.template import Context, Template, TemplateSyntaxError
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

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
