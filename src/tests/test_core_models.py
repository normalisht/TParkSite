import pytest
from django.db import IntegrityError

from apps.content.models import Partner
from apps.core.models import InfoPage, Phone, SiteSettings

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
