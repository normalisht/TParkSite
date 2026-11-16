import http.client
import io
from pathlib import Path
from urllib.request import Request

import pytest
from django.core.exceptions import ValidationError

from apps.content import dzen
from apps.content.dzen import (
    DzenFetchError,
    DzenVideo,
    download_poster,
    extract_embed_url,
    fetch_video,
    format_duration,
    parse_video_page,
    validate_embed_url,
)

EMBED = "https://dzen.ru/embed/oakZI1TIPAAA"
THUMB = "https://avatars.dzeninfra.ru/get-zen_doc/123/abc/smart_crop_516x290"


@pytest.fixture
def fixture_page():
    return (Path(__file__).parent / "fixtures" / "dzen_embed.html").read_text(encoding="utf-8")


class FakeResponse(io.BytesIO):
    pass


class FakeOpener:
    """Подмена opener модуля: словарь «адрес → байты или исключение», запросы запоминаются."""

    def __init__(self, responses):
        self.responses = responses
        self.requested = []

    def open(self, request, timeout=None):
        self.requested.append(request.full_url)
        result = self.responses[request.full_url]
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)


@pytest.mark.parametrize(
    "value",
    [
        '<iframe width="560" src="https://dzen.ru/embed/oakZI1TIPAAA?from_block=partner&amp;mute=0" allow="autoplay"></iframe>',
        "  https://dzen.ru/embed/oakZI1TIPAAA/ \n",
        "https://dzen.ru/embed/oakZI1TIPAAA#t=10",
    ],
)
def test_extract_embed_url_normalizes(value):
    assert extract_embed_url(value) == EMBED


def test_extract_embed_url_leaves_foreign_as_is():
    assert extract_embed_url("https://evil.ru/embed/abc?x=1") == "https://evil.ru/embed/abc?x=1"


def test_validate_embed_url_accepts():
    validate_embed_url(EMBED)


@pytest.mark.parametrize(
    "url",
    [
        "https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b",
        "http://dzen.ru/embed/abc",
        "https://evil.ru/embed/abc",
        "https://dzen.ru/embed/",
        "https://dzen.ru/embed/a/b",
    ],
)
def test_validate_embed_url_rejects(url):
    with pytest.raises(ValidationError, match="Поделиться"):
        validate_embed_url(url)


def test_form_field_extracts_iframe():
    field = dzen.DzenEmbedURLField().formfield()
    code = '<iframe src="https://dzen.ru/embed/abc?mute=0"></iframe>'
    assert field.clean(code) == "https://dzen.ru/embed/abc"
    assert "maxlength" not in field.widget.attrs


def test_parse_video_page(fixture_page):
    assert parse_video_page(fixture_page) == DzenVideo(
        "Т-парк. Фрироуп 3. Железный век", "Это третье видео…", 925, THUMB
    )


def test_parse_video_page_strips_suffix_and_unescapes():
    page = '<title>A &amp; B | Дзен</title>{"thumbnail":"https://avatars.dzeninfra.ru/x/y"}'
    assert parse_video_page(page).title == "A & B"


def test_parse_video_page_title_from_json():
    page = '{"title":"Из \\"JSON\\"","thumbnail":"https://avatars.dzeninfra.ru/x/y"}'
    assert parse_video_page(page).title == 'Из "JSON"'


def test_parse_video_page_without_duration(fixture_page):
    video = parse_video_page(fixture_page.replace('"duration":925,', ""))
    assert video.duration is None
    assert video.title and video.thumbnail_url


def test_parse_video_page_garbage_raises():
    with pytest.raises(DzenFetchError) as exc:
        parse_video_page("<html></html>")
    assert str(exc.value) == "Не удалось найти данные ролика на странице Дзена."


def test_fetch_video(monkeypatch, fixture_page):
    monkeypatch.setattr(dzen, "_opener", FakeOpener({EMBED: fixture_page.encode()}))
    assert fetch_video(EMBED).duration == 925


def test_fetch_video_rejects_redirect_off_dzen():
    handler = dzen.HostOnlyRedirects(dzen.PAGE_HOST)
    with pytest.raises(DzenFetchError) as exc:
        handler.redirect_request(Request(EMBED), None, 302, "Found", {}, "https://evil.ru/")
    assert str(exc.value) == "Дзен перенаправил на другой сайт."


def test_fetch_video_rejects_redirect_on_dzen():
    handler = dzen.HostOnlyRedirects(dzen.PAGE_HOST)
    new = handler.redirect_request(Request(EMBED), None, 302, "Found", {}, "https://dzen.ru/embed/other")
    assert new.full_url == "https://dzen.ru/embed/other"


@pytest.mark.parametrize(
    "error",
    [OSError("down"), http.client.IncompleteRead(b"x"), http.client.LineTooLong("header")],
    ids=["os-error", "incomplete-read", "line-too-long"],
)
def test_fetch_video_network_error(monkeypatch, error):
    monkeypatch.setattr(dzen, "_opener", FakeOpener({EMBED: error}))
    with pytest.raises(DzenFetchError) as exc:
        fetch_video(EMBED)
    # Только причина: совет «заполните вручную» добавляет форма админки (DZEN_ERROR).
    assert str(exc.value) == "Дзен не ответил."


def test_fetch_video_too_large(monkeypatch):
    monkeypatch.setattr(dzen, "MAX_PAGE_BYTES", 10)
    monkeypatch.setattr(dzen, "_opener", FakeOpener({EMBED: b"x" * 11}))
    with pytest.raises(DzenFetchError) as exc:
        fetch_video(EMBED)
    assert str(exc.value) == "Ответ Дзена слишком большой."


def test_fetch_video_rejects_foreign_url():
    with pytest.raises(DzenFetchError):
        fetch_video("https://evil.ru/embed/abc")


def test_download_poster_prefers_orig(monkeypatch, make_image):
    image = make_image().read()
    opener = FakeOpener({"https://avatars.dzeninfra.ru/get-zen_doc/123/abc/orig": image})
    monkeypatch.setattr(dzen, "_image_opener", opener)
    poster = download_poster(THUMB)
    assert opener.requested == ["https://avatars.dzeninfra.ru/get-zen_doc/123/abc/orig"]
    assert poster.name == "poster.jpg" and poster.read() == image


@pytest.mark.parametrize(
    "error", [OSError("404"), http.client.IncompleteRead(b"x")], ids=["os-error", "incomplete-read"]
)
def test_download_poster_falls_back_to_original(monkeypatch, make_image, error):
    image = make_image().read()
    opener = FakeOpener({"https://avatars.dzeninfra.ru/get-zen_doc/123/abc/orig": error, THUMB: image})
    monkeypatch.setattr(dzen, "_image_opener", opener)
    assert download_poster(THUMB).read() == image
    assert opener.requested[-1] == THUMB


def test_download_poster_rejects_foreign_host():
    with pytest.raises(DzenFetchError):
        download_poster("https://evil.ru/x.jpg")


def test_download_poster_rejects_non_image(monkeypatch):
    opener = FakeOpener({"https://avatars.dzeninfra.ru/get-zen_doc/123/abc/orig": b"not an image"})
    monkeypatch.setattr(dzen, "_image_opener", opener)
    with pytest.raises(DzenFetchError):
        download_poster(THUMB)


@pytest.mark.parametrize(("seconds", "text"), [(None, ""), (5, "0:05"), (925, "15:25"), (3723, "1:02:03")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text
