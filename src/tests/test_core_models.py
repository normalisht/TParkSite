import importlib

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError

from apps.content.models import Partner
from apps.core.models import InfoPage, Phone, SiteSettings
from apps.core.privacy_defaults import PRIVACY_SLUG, ensure_privacy_page

pytestmark = pytest.mark.django_db


def test_site_settings_is_singleton():
    first = SiteSettings.load()
    second = SiteSettings.load()
    assert first.pk == second.pk == 1
    SiteSettings(address="другой").save()
    assert SiteSettings.objects.count() == 1
    assert SiteSettings.load().address == "другой"


def test_phone_links():
    phone = Phone(settings=SiteSettings.load(), number="9029856594")
    assert phone.tel_url == "tel:+79029856594"
    assert phone.whatsapp_url == "https://wa.me/79029856594"
    assert phone.telegram_url == "https://t.me/+79029856594"
    assert phone.display == "+7 (902) 985-65-94"


@pytest.mark.parametrize("flag", ["is_whatsapp", "is_telegram"])
def test_only_one_phone_per_messenger(flag):
    site = SiteSettings.load()
    Phone.objects.create(settings=site, number="9000000001", **{flag: True})
    with pytest.raises(IntegrityError):
        Phone.objects.create(settings=site, number="9000000002", **{flag: True})


def test_one_phone_can_have_both_flags():
    Phone.objects.create(settings=SiteSettings.load(), number="9000000001", is_whatsapp=True, is_telegram=True)


def test_info_page_slug_is_generated_and_unique():
    first = InfoPage.objects.create(title="Правила безопасности", body="<p>x</p>")
    second = InfoPage.objects.create(title="Правила безопасности", body="<p>y</p>")
    assert first.slug == "pravila-bezopasnosti"
    assert second.slug == "pravila-bezopasnosti-2"


def test_info_page_published_queryset():
    InfoPage.objects.create(title="A", is_published=True)
    InfoPage.objects.create(title="B", is_published=False)
    assert list(InfoPage.objects.published().values_list("title", flat=True)) == ["A"]


def test_files_deleted_after_commit(make_image, media_root, django_capture_on_commit_callbacks):
    partner = Partner.objects.create(logo=make_image())
    path = media_root / partner.logo.name
    assert path.exists()
    with django_capture_on_commit_callbacks(execute=True):
        partner.delete()
    assert not path.exists()


def test_replaced_file_deleted_after_commit(make_image, media_root, django_capture_on_commit_callbacks):
    partner = Partner.objects.create(logo=make_image())
    old_path = media_root / partner.logo.name
    with django_capture_on_commit_callbacks(execute=True):
        partner.logo = make_image("new.jpg")
        partner.save()
    assert not old_path.exists()
    assert (media_root / partner.logo.name).exists()


def test_files_kept_when_transaction_rolls_back(make_image, media_root):
    partner = Partner.objects.create(logo=make_image())
    path = media_root / partner.logo.name
    partner.delete()  # без выполнения on_commit — как при откате
    assert path.exists()


def _privacy_migration():
    return importlib.import_module("apps.core.migrations.0014_privacy_policy")


def _footer_migration():
    return importlib.import_module("apps.core.migrations.0021_info_page_layout")


def test_footer_migration_keeps_footer_links_from_settings():
    site = SiteSettings.load()
    site.safety_page = InfoPage.objects.create(title="Правила", body="<p>x</p>")
    site.save()
    other = InfoPage.objects.create(title="Цены", body="<p>y</p>")
    _footer_migration().footer_links_and_order(django_apps, None)
    assert InfoPage.objects.get(pk=site.safety_page.pk).show_in_footer
    assert InfoPage.objects.get(slug=PRIVACY_SLUG).show_in_footer
    assert not InfoPage.objects.get(pk=other.pk).show_in_footer
    # Порядок — прежний, по алфавиту.
    titles = list(InfoPage.objects.values_list("title", flat=True))
    assert titles == sorted(titles)


def test_privacy_page_created_unpublished_and_selected(client):
    InfoPage.objects.filter(slug=PRIVACY_SLUG).delete()  # миграция могла создать её в тестовой БД
    site = SiteSettings.load()
    _privacy_migration().forwards(django_apps, None)
    _footer_migration().footer_links_and_order(django_apps, None)
    page = InfoPage.objects.get(slug=PRIVACY_SLUG)
    assert page.title == "Политика конфиденциальности" and not page.is_published
    for required in (
        "152-ФЗ",
        "Оператор",
        "Яндекс Метрика",
        "cookie",
        "Роскомнадзор",
        "[укажите ИНН]",
        "[укажите e-mail]",
    ):
        assert required in page.body, required
    assert page.body.count("<h2>") == 10
    site.refresh_from_db()
    assert site.privacy_page == page
    assert page.get_absolute_url() not in client.get("/").content.decode()  # пока не опубликована — ссылки нет
    page.is_published = True
    page.save()
    assert page.get_absolute_url() in client.get("/").content.decode().split("<footer", 1)[1]


def test_ensure_privacy_page_keeps_existing_choice():
    InfoPage.objects.filter(slug=PRIVACY_SLUG).delete()
    site = SiteSettings.load()
    own = InfoPage.objects.create(title="Наша политика", body="<p>x</p>")
    site.privacy_page = own
    site.save()
    page = ensure_privacy_page(InfoPage, SiteSettings)
    assert ensure_privacy_page(InfoPage, SiteSettings) == page  # второй вызов ничего не создаёт
    assert InfoPage.objects.filter(slug=PRIVACY_SLUG).count() == 1
    site.refresh_from_db()
    assert site.privacy_page == own


def test_founder_text_migration_drops_repeated_heading():
    site = SiteSettings.load()
    site.founder_text = "<p><strong>Дмитрий Сергеев</strong></p>\n\n<p>Этот человек придумал и создал Т-парк:</p>\n\n<ul><li>Педагог</li></ul>"
    site.save()
    importlib.import_module("apps.core.migrations.0015_founder_text_heading").forwards(django_apps, None)
    site.refresh_from_db()
    assert site.founder_text == "<ul><li>Педагог</li></ul>"
