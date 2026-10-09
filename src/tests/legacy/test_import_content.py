import csv
from datetime import date

import pytest

from apps.catalog.models import Category
from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.legacy import runner

pytestmark = pytest.mark.django_db(transaction=True)


def test_events(legacy):
    legacy.insert(
        "event", id=2, title="Сплав", date="2022-09-24", link="https://vk.com/e", text_color="#ffffff", after_date=1
    )
    legacy.insert("event", id=3, title="Квест", date="2022-10-16 22:00:00.000000", text_color="red", after_date=None)
    legacy.insert("event", id=4, title="Без даты", date=None)
    legacy.image("events/2.jpg")
    legacy.image("events/0.jpg")
    report = legacy.run()
    splav = Event.objects.get(title="Сплав")
    assert (splav.date, splav.show_after_date, splav.link) == (
        date(2022, 9, 24),
        True,
        "https://vk.com/e",
    )
    assert splav.image
    kvest = Event.objects.get(title="Квест")
    assert (kvest.date, kvest.show_after_date) == (date(2022, 10, 16), False)
    assert not Event.objects.filter(title="Без даты").exists()
    assert any("слайдера" in w and "#2" in w for w in report.warnings)
    assert any("Без даты" in w or "#4" in w for w in report.warnings)


def test_reviews_partners_gallery(legacy):
    legacy.insert("comment", id=4, name="Анна", text='<p><a href="https://reviews.yandex.ru/x">Отзыв</a></p>')
    legacy.insert("comment", id=5, name="Борис", text="<p>Ещё</p>")
    legacy.image("comments/5.jpg")
    legacy.insert("partner", id=1, name="1", link="https://partner.ru")
    legacy.insert("partner", id=2, name="temp", link=None)
    legacy.image("partner/1.jpg")
    legacy.insert("employee", id=1, name="Сотрудник", position=None, photo=None)  # таблица больше не переносится
    for name in ["3.jpg", "12.jpg", "1.jpg"]:
        legacy.image(f"gallery/{name}", size=(30 + int(name.split(".")[0]), 30))
    report = legacy.run()
    assert not any("отрудник" in w for w in report.warnings)
    reviews = list(Review.objects.order_by("id"))
    assert (reviews[0].link, reviews[0].text) == ("https://reviews.yandex.ru/x", "<p>Отзыв</p>")
    assert not reviews[0].photo and reviews[1].photo
    partner = Partner.objects.get()
    assert (partner.name, partner.link) == ("", "https://partner.ru") and partner.logo
    assert [p.image.width for p in GalleryPhoto.objects.all()] == [31, 33, 42]


def test_price_csv(legacy, tmp_path):
    legacy.insert("price", id=1, service_id=21, price="500", time="час")
    target = tmp_path / "price.csv"
    legacy.run(price_csv=target)
    with target.open(encoding="utf-8-sig") as fh:
        assert list(csv.reader(fh)) == [["id", "service_id", "price", "time"], ["1", "21", "500", "час"]]


def test_corrupt_image_is_warning_not_failure(legacy):
    legacy.insert("comment", id=1, name="Анна", text="<p>x</p>")
    broken = legacy.images / "comments" / "1.jpg"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"not an image")
    report = legacy.run()
    assert Review.objects.get().photo.name in ("", None)
    assert any("1.jpg" in w for w in report.warnings)


def test_flush_replaces_content(legacy):
    Category.objects.create(name="Старая")
    legacy.insert("category", id=1, name="Новая", status=1, number=0)
    legacy.run(flush=True)
    assert list(Category.objects.values_list("name", flat=True)) == ["Новая"]


def test_failed_import_rolls_back_db_and_files(legacy, monkeypatch, media_root, make_image):
    from apps.content.models import GalleryPhoto as Photo

    kept = Photo.objects.create(image=make_image())
    kept_path = media_root / kept.image.name
    Category.objects.create(name="Старая")
    legacy.insert("category", id=1, name="Новая", status=1, number=0)
    legacy.image("category/1/1.jpg")

    def boom(*args, **kwargs):
        raise RuntimeError("сбой посередине")

    monkeypatch.setattr(runner, "import_content", boom)
    files_before = {p for p in media_root.rglob("*") if p.is_file()}
    with pytest.raises(RuntimeError):
        legacy.run(flush=True)
    assert list(Category.objects.values_list("name", flat=True)) == ["Старая"]
    assert Photo.objects.filter(pk=kept.pk).exists() and kept_path.exists()
    assert {p for p in media_root.rglob("*") if p.is_file()} == files_before


def test_event_link_without_scheme_is_dropped(legacy):
    legacy.insert("event", id=7, title="Без ссылки", date="2022-09-24", link="#")
    legacy.insert("event", id=8, title="Со ссылкой", date="2022-09-25", link=" https://vk.com/e ")
    legacy.run()
    assert Event.objects.get(title="Без ссылки").link == ""
    assert Event.objects.get(title="Со ссылкой").link == "https://vk.com/e"


def test_reviews_without_name(legacy):
    legacy.insert("comment", id=1, name=None, text='<p><a href="https://reviews.yandex.ru/u">20.07.2022</a></p>')
    legacy.insert("comment", id=2, name=" ", text="<p>Без ссылки</p>")
    report = legacy.run()
    reviews = list(Review.objects.order_by("id"))
    assert reviews[0].source_label == "Яндекс Карты"
    assert not any("Отзыв #" in w for w in report.warnings)


def test_review_lead_link_moves_to_fields(legacy):
    legacy.insert(
        "comment",
        id=1,
        name=None,
        text='<p><a href="https://reviews.yandex.ru/u?a=1&amp;b=2" target="_blank">6.06.2021</a></p>\r\n\r\n'
        "<p>Отлично!</p>\r\n\r\n<p>&nbsp;</p>",
    )
    legacy.insert("comment", id=2, name="Анна", text='<p><a href="https://vk.com/p">Пост в VK</a></p><p>Текст</p>')
    legacy.insert("comment", id=3, name="Борис", text='<p>Начало <a href="https://vk.com/p">ссылка</a></p>')
    legacy.run()
    yandex, vk, inline = Review.objects.order_by("id")
    assert (yandex.link, yandex.date, yandex.text) == (
        "https://reviews.yandex.ru/u?a=1&b=2",
        date(2021, 6, 6),
        "<p>Отлично!</p>",
    )
    assert (vk.link, vk.date) == ("https://vk.com/p", None)
    assert vk.text.startswith("<p>Пост в VK</p>") and "<a" not in vk.text
    assert inline.link == "" and 'href="https://vk.com/p"' in inline.text


def test_pdf_instead_of_image_is_warning(legacy):
    legacy.insert("comment", id=1, name="Анна", text="<p>x</p>")
    pdf = legacy.images / "comments" / "1.jpg"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.5\n...")
    report = legacy.run()
    assert not Review.objects.get().photo
    assert any("1.jpg — это PDF" in w for w in report.warnings)


def test_unused_files_are_reported(legacy):
    legacy.insert("comment", id=1, name="Анна", text="<p>x</p>")
    legacy.image("comments/1.jpg")
    legacy.image("comments/10.jpg")
    legacy.image("comments/3.jpg")
    legacy.image("staff/0.jpg")
    report = legacy.run()
    assert "Не перенесены файлы из comments/: 3.jpg, 10.jpg" in report.warnings
    assert "Не перенесены файлы из staff/: 0.jpg" in report.warnings
    assert not any("1.jpg" in w for w in report.warnings)
