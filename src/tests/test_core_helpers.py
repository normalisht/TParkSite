import io
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.fields import UploadTo, sanitize_html, validate_image_upload
from apps.core.images import safe_spec_url
from apps.core.maps import route_links
from apps.core.opening_hours import human_opening_hours, opening_hours_spec
from apps.core.slugs import slugify_ru
from apps.core.templatetags.site_tags import nobr


def test_sanitize_keeps_allowed_and_strips_scripts():
    html = '<p><strong>Жирный</strong> <a href="https://t-camp.ru">ссылка</a></p><script>alert(1)</script>'
    cleaned = sanitize_html(html)
    assert "<strong>Жирный</strong>" in cleaned
    assert 'href="https://t-camp.ru"' in cleaned
    assert "script" not in cleaned


def test_sanitize_drops_inline_styles():
    assert "style" not in sanitize_html('<p style="color:red">x</p>')


def test_slugify_ru_transliterates():
    assert slugify_ru("Байдарки и SUP") == "baidarki-i-sup"


def test_slugify_ru_empty_falls_back():
    assert slugify_ru("!!!") == "item"


def test_upload_to_generates_unique_names():
    upload_to = UploadTo("gallery")
    first, second = upload_to(None, "Фото 1.JPG"), upload_to(None, "Фото 1.JPG")
    assert first.startswith("gallery/") and first.endswith(".jpg")
    assert first != second


def test_validate_accepts_jpeg(make_image):
    validate_image_upload(make_image())


def test_validate_rejects_gif(make_image):
    with pytest.raises(ValidationError, match="jpg, png или webp"):
        validate_image_upload(make_image("anim.gif", fmt="GIF"))


def test_validate_rejects_too_big(make_image):
    big = make_image()
    big.size = 20 * 1024 * 1024 + 1
    with pytest.raises(ValidationError, match="20 МБ"):
        validate_image_upload(big)


def test_validate_rejects_not_an_image():
    with pytest.raises(ValidationError):
        validate_image_upload(SimpleUploadedFile("fake.jpg", b"not an image"))


def test_validate_skips_already_stored_file():
    class Stored:
        _committed = True
        size = 10**9

    validate_image_upload(Stored())


def test_upload_rejects_decompression_bomb():
    # 8000×7000 = 56 Мп: PNG весит килобайты, а распакованный займёт сотни мегабайт при пережатии.
    buffer = io.BytesIO()
    Image.new("1", (8000, 7000)).save(buffer, "PNG")
    upload = SimpleUploadedFile("big.png", buffer.getvalue(), content_type="image/png")
    with pytest.raises(ValidationError, match="50 мегапикселей"):
        validate_image_upload(upload)


def test_upload_accepts_normal_photo(make_image):
    validate_image_upload(make_image(size=(4000, 3000)))


def test_safe_spec_url_swallows_errors():
    class Broken:
        @property
        def thumb(self):
            raise FileNotFoundError("нет файла")

    assert safe_spec_url(Broken(), "thumb") == ""
    assert safe_spec_url(object(), "missing") == ""
    assert safe_spec_url(None, "thumb") == ""


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1 отзыв"),
        (3, "3 отзыва"),
        (5, "5 отзывов"),
        (11, "11 отзывов"),
        (12, "12 отзывов"),
        (21, "21 отзыв"),
        (22, "22 отзыва"),
        (111, "111 отзывов"),
    ],
)
def test_ru_plural(n, expected):
    from apps.core.templatetags.site_tags import ru_plural

    assert ru_plural(n, "отзыв,отзыва,отзывов") == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Mo-Su 10:00-18:00", ["Ежедневно, 10:00–18:00"]),
        ("Mo-Fr 09:00-18:00; Sa,Su 10:00-16:00", ["Пн–пт, 09:00–18:00", "Сб, вс, 10:00–16:00"]),
        ("", []),
        ("Круглосуточно", []),
        ("Mo-Fr 09:00-18:00; что-то", []),
    ],
)
def test_human_opening_hours(value, expected):
    assert human_opening_hours(value) == expected


def test_route_links():
    assert route_links(None, 36.7) == {}
    links = route_links(Decimal("54.956545"), Decimal("36.769595"))
    assert links["yandex"] == "https://yandex.ru/maps/?rtext=~54.956545,36.769595&rtt=auto"
    assert links["coordinates"] == "54.956545, 36.769595"


def test_nobr_keeps_brand_on_one_line():
    assert nobr("Своё событие в Т-Парке") == 'Своё событие в <span class="whitespace-nowrap">Т-Парке</span>'
    assert nobr("Тренинг-парк Дмитрия") == '<span class="whitespace-nowrap">Тренинг-парк</span> Дмитрия'


def test_nobr_escapes_html():
    assert nobr("<b>Т-Парк</b>") == '&lt;b&gt;<span class="whitespace-nowrap">Т-Парк</span>&lt;/b&gt;'


FOUNDER_NAME, FOUNDER_LEAD = "Дмитрий Сергеев", "Этот человек придумал и создал Т-Парк"


def test_strip_founder_heading_removes_repeated_name_and_lead():
    from apps.core.about_defaults import strip_founder_heading

    text = (
        "<p><strong>Дмитрий Сергеев</strong></p>\n\n<p>Этот человек придумал и создал Т-парк:</p>\n\n"
        "<ul><li><p>Педагог</p></li></ul>"
    )
    assert strip_founder_heading(text, FOUNDER_NAME, FOUNDER_LEAD) == "<ul><li><p>Педагог</p></li></ul>"


def test_strip_founder_heading_keeps_other_text():
    from apps.core.about_defaults import strip_founder_heading

    text = "<p>Дмитрий Сергеев родился в Калуге.</p>\n\n<p>Этот человек придумал и создал Т-Парк:</p>"
    assert strip_founder_heading(text, FOUNDER_NAME, FOUNDER_LEAD) == text
    assert strip_founder_heading("", FOUNDER_NAME, FOUNDER_LEAD) == ""


def test_opening_hours_spec():
    assert opening_hours_spec("Mo-Fr 10:00-18:00; Sa,Su 11:00-16:00") == [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": [f"https://schema.org/{d}" for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")],
            "opens": "10:00",
            "closes": "18:00",
        },
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["https://schema.org/Saturday", "https://schema.org/Sunday"],
            "opens": "11:00",
            "closes": "16:00",
        },
    ]
    assert len(opening_hours_spec("Mo-Su 10:00-18:00")[0]["dayOfWeek"]) == 7


def test_opening_hours_spec_invalid_is_empty():
    assert opening_hours_spec("Пн-Пт 10-18") == []
    assert opening_hours_spec("") == []


def test_opening_hours_spec_pads_hours_to_two_digits():
    spec = opening_hours_spec("Mo-Fr 9:00-18:00")[0]
    assert (spec["opens"], spec["closes"]) == ("09:00", "18:00")
