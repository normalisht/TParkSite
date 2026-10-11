import pytest
from django.core.management import call_command

from apps.catalog.models import Service
from apps.content.models import GalleryPhoto
from apps.core.content_fixes import (
    describe_change,
    fix_caption,
    fix_name,
    fix_price,
    fix_text,
    fix_unit,
    has_unbalanced_quotes,
)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Правила безопасности Т-парка", "Правила безопасности Т-Парка"),
        ("<p>в Т-парке</p>", "<p>в Т-Парке</p>"),
        ("Нижняя веревочная трасса", "Нижняя верёвочная трасса"),
        ("Взнос 100 руб", "Взнос 100 ₽"),
        ("Стоимость 1000 р.", "Стоимость 1000 ₽"),
        ("Стоимость 1000 р", "Стоимость 1000 ₽"),
        ("5 рублей", "5 ₽"),
        ("10 раз, 1826 г.", "10 раз, 1826 г."),
        ("Генератор (1000 w)", "Генератор (1000 Вт)"),
        ("рекрасное место для отдыха", "Прекрасное место для отдыха"),
        ("друзья собирабтся", "друзья собираются"),
    ],
)
def test_fix_text(before, after):
    assert fix_text(before) == after


def test_fix_text_keeps_latin_formats():
    text = "философия тренинг-парка (T-park), лагеря (T-camp) — https://civilization.t-park.camp"
    assert fix_text(text) == text


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Сплав** На метеоритную ферму", "Сплав На метеоритную ферму"),
        ('Программа "Всё включено!"', "Программа «Всё включено!»"),
        (
            'Сплав на каноэ "На родину маршала Жукова, однодневный (летняя программа)',
            "Сплав на каноэ «На родину маршала Жукова», однодневный (летняя программа)",
        ),
        ("Встреча Клуба Т-парк", "Встреча Клуба Т-Парк"),
    ],
)
def test_fix_name(before, after):
    assert fix_name(before) == after


def test_fix_price_unit_and_caption():
    assert fix_price(" 15 000 ") == "15000"
    assert fix_price("договорная") == "договорная"
    assert fix_price("1500 руб") == "1500"
    assert fix_price("1500 р.") == "1500"
    assert fix_price("1500₽") == "1500"
    assert fix_price("1 500 рублей") == "1500"
    assert fix_price("от 3500 руб") == "от 3500"
    assert fix_price("от 3500") == "от 3500"
    assert fix_unit("человек") == "участник"
    assert fix_unit("чел.") == "участник"
    assert fix_unit("в день") == "день"
    assert fix_unit("30 минут") == "30 мин"
    assert fix_unit("1 прыжок") == "1 прыжок"
    assert fix_caption("123") == ""
    assert fix_caption("Зимой на тюбинге") == "Зимой на тюбинге"


def test_unbalanced_quotes_and_change_description():
    assert has_unbalanced_quotes('Сплав "На родину')
    assert not has_unbalanced_quotes("Сплав «На родину»")
    assert "Т-Парк" in describe_change("в Т-парке летом", "в Т-Парке летом")


@pytest.mark.django_db
def test_command_dry_run_changes_nothing(capsys):
    service = Service.objects.create(name="Сплав*", price="15 000", price_unit="человек")
    call_command("normalize_content")
    service.refresh_from_db()
    assert (service.name, service.price, service.price_unit) == ("Сплав*", "15 000", "человек")
    assert "без --apply" in capsys.readouterr().out


@pytest.mark.django_db
def test_command_applies_and_is_idempotent(capsys, make_image):
    service = Service.objects.create(name="Сплав*", price="15 000", price_unit="человек")
    photo = GalleryPhoto.objects.create(image=make_image(), caption="123")
    call_command("normalize_content", "--apply")
    service.refresh_from_db()
    photo.refresh_from_db()
    assert (service.name, service.price, service.price_unit) == ("Сплав", "15000", "участник")
    assert photo.caption == ""
    capsys.readouterr()
    call_command("normalize_content")
    assert ": 0 записей" in capsys.readouterr().out
