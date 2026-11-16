"""Ролики с Дзена в галерее: нормализация кода «Встроить» и данные ролика для кнопки «Подтянуть» в админке.

Официального API нет: название, описание, длительность и обложку берём со страницы плеера (https://dzen.ru/embed/<id>).
Если Дзен поменяет разметку, кнопка вернёт ошибку и поля заполняются вручную.
"""

import html
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models

from apps.core.fields import validate_image_upload

TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
)
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_POSTER_BYTES = 10 * 1024 * 1024
PAGE_HOST = "dzen.ru"
IMAGE_HOST = "avatars.dzeninfra.ru"

EMBED_ERROR = (
    "Нужен код из Дзена: под видео „⋯“ → „Поделиться“ → „Встроить“, "
    "скопируйте код целиком. Обычная ссылка на видео (dzen.ru/video/watch/…) не подойдёт"
)

_IFRAME_SRC_RE = re.compile(r"""<iframe\b[^>]*?\ssrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_EMBED_URL_RE = re.compile(r"https://dzen\.ru/embed/[A-Za-z0-9_-]+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_JSON_TITLE_RE = re.compile(r'"title":"((?:[^"\\]|\\.)*)"')
_DESCRIPTION_RE = re.compile(r'"description":"((?:[^"\\]|\\.)*)"')
_THUMBNAIL_RE = re.compile(r'"thumbnail":"((?:[^"\\]|\\.)*)"')
_DURATION_RE = re.compile(r'"duration":(\d+)')
_TITLE_SUFFIX = " | Дзен"


def extract_embed_url(value: str) -> str:
    """Из кода <iframe …> или ссылки достаёт адрес плеера без параметров; не-Дзен возвращает как есть."""
    value = (value or "").strip()
    match = _IFRAME_SRC_RE.search(value)
    url = html.unescape(match.group(1)).strip() if match else value
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname == PAGE_HOST and parts.path.startswith("/embed/"):
        return f"https://{PAGE_HOST}{parts.path.rstrip('/')}"
    return url


def validate_embed_url(value: str) -> None:
    if not _EMBED_URL_RE.fullmatch(value or ""):
        raise ValidationError(EMBED_ERROR)


class DzenEmbedFormField(forms.URLField):
    def to_python(self, value):
        return super().to_python(extract_embed_url(value))

    def widget_attrs(self, widget):
        # Ограничение длины — на извлечённую ссылку, а не на вставляемый код <iframe>, он заметно длиннее.
        attrs = super().widget_attrs(widget)
        attrs.pop("maxlength", None)
        return attrs


class DzenEmbedURLField(models.URLField):
    default_validators = [*models.URLField.default_validators, validate_embed_url]

    def formfield(self, **kwargs):
        kwargs.setdefault("form_class", DzenEmbedFormField)
        kwargs.setdefault("widget", forms.Textarea(attrs={"rows": 3}))
        return super().formfield(**kwargs)


class DzenFetchError(Exception):
    """Текст исключения показывается в админке."""


@dataclass(frozen=True)
class DzenVideo:
    title: str
    description: str
    duration: int | None
    thumbnail_url: str


class HostOnlyRedirects(HTTPRedirectHandler):
    """Редиректы — только на свой хост: запрос идёт с сервера по адресу из админки."""

    def __init__(self, host: str):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != self.host:
            raise DzenFetchError("Дзен перенаправил на другой сайт — заполните поля вручную.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = build_opener(HostOnlyRedirects(PAGE_HOST))
_image_opener = build_opener(HostOnlyRedirects(IMAGE_HOST))


def _read_limited(response, limit: int) -> bytes:
    data = response.read(limit + 1)
    if len(data) > limit:
        raise DzenFetchError("Ответ Дзена слишком большой — заполните поля вручную.")
    return data


def _json_string(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except ValueError:
        return raw


def parse_video_page(page: str) -> DzenVideo:
    title_match = _TITLE_RE.search(page)
    title = html.unescape(title_match.group(1)).strip() if title_match else ""
    title = title.removesuffix(_TITLE_SUFFIX).strip()
    if not title and (match := _JSON_TITLE_RE.search(page)):
        title = _json_string(match.group(1)).strip()
    thumbnail = _THUMBNAIL_RE.search(page)
    if not title or not thumbnail:
        raise DzenFetchError("Не удалось найти данные ролика на странице Дзена — заполните поля вручную.")
    description = _DESCRIPTION_RE.search(page)
    duration = _DURATION_RE.search(page)
    return DzenVideo(
        title=title,
        description=_json_string(description.group(1)).strip() if description else "",
        duration=int(duration.group(1)) if duration else None,
        thumbnail_url=_json_string(thumbnail.group(1)),
    )


def fetch_video(embed_url: str) -> DzenVideo:
    try:
        validate_embed_url(embed_url)
    except ValidationError as exc:
        raise DzenFetchError(EMBED_ERROR) from exc
    request = Request(embed_url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru"})
    try:
        with _opener.open(request, timeout=TIMEOUT) as response:
            page = _read_limited(response, MAX_PAGE_BYTES).decode("utf-8", "replace")
    except OSError as exc:
        raise DzenFetchError("Дзен не ответил — попробуйте позже или заполните поля вручную.") from exc
    return parse_video_page(page)


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with _image_opener.open(request, timeout=TIMEOUT) as response:
        return _read_limited(response, MAX_POSTER_BYTES)


def download_poster(thumbnail_url: str) -> ContentFile:
    """Обложка в максимальном размере (`orig`), а если такого нет — та, что указана на странице."""
    parts = urlsplit(thumbnail_url)
    if parts.scheme != "https" or parts.hostname != IMAGE_HOST:
        raise DzenFetchError("Обложка лежит не на сервере Дзена — загрузите её вручную.")
    original = thumbnail_url.rsplit("/", 1)[0] + "/orig"
    data = None
    for url in (original, thumbnail_url):
        try:
            data = _download(url)
            break
        except OSError, DzenFetchError:
            continue
    if data is None:
        raise DzenFetchError("Не удалось скачать обложку — загрузите её вручную.")
    poster = ContentFile(data, name="poster.jpg")
    try:
        validate_image_upload(poster)
    except ValidationError as exc:
        raise DzenFetchError("Обложка Дзена не подошла — загрузите её вручную.") from exc
    return poster


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
