"""Текст и дата отзыва со страницы Яндекс Отзывов — для кнопки «Подтянуть» в админке.

Официального API нет: страница пользователя (https://reviews.yandex.ru/user/…) отдаёт все его отзывы
в JSON `window.__PRELOADED_DATA`, нужный находим по `boostId` из ссылки — это организация (`/sprav/<id>`).
Если Яндекс поменяет разметку или покажет капчу, кнопка вернёт ошибку и отзыв заполняется вручную.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from django.utils import timezone

from apps.core.fields import sanitize_html

TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
)
_DATA_START = re.compile(r"window\.__PRELOADED_DATA\s*=\s*")


class ReviewFetchError(Exception):
    """Текст исключения показывается в админке."""


@dataclass(frozen=True)
class YandexReview:
    text: str  # HTML: абзацы по строкам исходного текста
    date: date | None


def review_key(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.hostname != "reviews.yandex.ru":
        raise ReviewFetchError("Нужна ссылка на отзыв с Яндекса вида https://reviews.yandex.ru/user/…?boostId=…")
    key = parse_qs(parts.query).get("boostId", [""])[0]
    if not key:
        raise ReviewFetchError("В ссылке нет параметра boostId — скопируйте ссылку на отзыв целиком.")
    return key


def fetch_review(url: str) -> YandexReview:
    key = review_key(url)
    request = Request(url.strip(), headers={"User-Agent": USER_AGENT, "Accept-Language": "ru"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            page = response.read().decode("utf-8", "replace")
    except OSError as exc:
        raise ReviewFetchError("Яндекс не ответил — попробуйте позже или заполните отзыв вручную.") from exc
    return parse_review(page, key)


def parse_review(page: str, key: str) -> YandexReview:
    try:
        start = _DATA_START.search(page).end()
        data, _ = json.JSONDecoder().raw_decode(page, start)
        review = data["pageData"]["initialState"]["reviews"]["all"][key]
        text = review["text"]
    except (AttributeError, ValueError, KeyError, TypeError) as exc:
        raise ReviewFetchError("Не удалось найти отзыв на странице Яндекса — заполните его вручную.") from exc
    paragraphs = "".join(f"<p>{escape(line.strip())}</p>" for line in str(text).splitlines() if line.strip())
    if not paragraphs:
        raise ReviewFetchError("У отзыва на Яндексе нет текста.")
    return YandexReview(text=sanitize_html(paragraphs), date=_review_date(review.get("timestamp")))


def _review_date(timestamp) -> date | None:
    """Дата публикации — по миллисекундам `timestamp`, в часовом поясе сайта (как показывает Яндекс)."""
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.get_default_timezone()).date()
    except TypeError, ValueError, OverflowError, OSError:
        return None
