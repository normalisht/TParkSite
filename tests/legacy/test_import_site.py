import pytest
from django.core.management import CommandError, call_command

from apps.catalog.models import Category
from apps.core.models import InfoPage, Phone, SiteSettings

pytestmark = pytest.mark.django_db(transaction=True)


def add_texts(legacy, **texts):
    for title, text in texts.items():
        legacy.insert("text", title=title, text=text)


def test_site_texts_and_contacts(legacy):
    add_texts(
        legacy,
        main_text="<p>Добро пожаловать</p><script>x</script>",
        about="<p>О нас</p>",
        filosofi="<p>Философия</p>",
        structure="<p>Рядом</p>",
        contacts_info="<p>Как добраться</p>",
        address="Калужская область, село Восход ",
        geolocation="https://yandex.ru/maps/-/CCUufTqlWC",
        vk="https://vk.com/tparkprotva",
    )
    legacy.image("staff/map.jpg")
    legacy.run()
    site = SiteSettings.load()
    assert site.home_intro == site.events_intro == "<p>Добро пожаловать</p>"
    assert site.about_text == "<p>О нас</p>"
    assert site.philosophy_text == "<p>Философия</p>"
    assert site.nearby_text == "<p>Рядом</p>"
    assert site.contacts_text == "<p>Как добраться</p>"
    assert site.address == "Калужская область, село Восход"
    assert site.map_url.endswith("CCUufTqlWC")
    assert site.vk_url == "https://vk.com/tparkprotva"
    assert site.contacts_map and not site.about_map


def test_phones_and_messenger_flags(legacy):
    add_texts(legacy, phone_numbers="9029856594 9953056461 abc 9106087735", insta="tg://resolve?domain=+79953056461")
    report = legacy.run()
    phones = list(Phone.objects.values_list("number", "is_whatsapp", "is_telegram"))
    assert phones == [
        ("9029856594", True, False),
        ("9953056461", False, True),
        ("9106087735", False, False),
    ]
    assert any("abc" in w for w in report.warnings)


def test_info_pages_keep_id_and_get_title(legacy):
    legacy.insert(
        "text", id=11, title=None, text="<p><strong>Правила безопасности Т-парка</strong></p><p>&nbsp;</p>", status=1
    )
    legacy.insert("text", id=12, title=None, text="<p>просто текст</p>", status=None)
    legacy.run()
    rules = InfoPage.objects.get(id=11)
    assert rules.title == "Правила безопасности Т-парка"
    assert rules.is_published
    untitled = InfoPage.objects.get(id=12)
    assert untitled.title == "Страница 12"
    assert not untitled.is_published


def test_refuses_when_content_exists(legacy):
    Category.objects.create(name="Уже есть")
    with pytest.raises(CommandError, match="--flush"):
        call_command("import_legacy", "--db", str(legacy.db_path), "--images", str(legacy.images))


def test_missing_images_dir(legacy, tmp_path):
    with pytest.raises(CommandError, match="изображениями"):
        call_command("import_legacy", "--db", str(legacy.db_path), "--images", str(tmp_path / "nope"))


def test_command_prints_report(legacy, capsys, tmp_path):
    add_texts(legacy, phone_numbers="9029856594")
    call_command(
        "import_legacy",
        "--db",
        str(legacy.db_path),
        "--images",
        str(legacy.images),
        "--price-csv",
        str(tmp_path / "p.csv"),
    )
    out = capsys.readouterr().out
    assert "Телефоны: 1" in out
    assert "Импорт завершён" in out
