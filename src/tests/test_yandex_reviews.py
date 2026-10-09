import json
from datetime import date

import pytest
from django.urls import reverse

from apps.content import yandex
from apps.content.yandex import ReviewFetchError, YandexReview, parse_review, review_key

URL = "https://reviews.yandex.ru/user/15t758y7kbyj7gx9f73r3242ww?main_tab=org&boostId=/sprav/17031236197"


def _page(reviews: dict) -> str:
    """Страница пользователя на Яндекс Отзывах: отзывы — в JSON внутри скрипта, по ключу организации."""
    data = {"globalData": {}, "pageData": {"initialState": {"reviews": {"all": reviews}}}}
    return f"<html><script>try {{\n window.__PRELOADED_DATA = {json.dumps(data, ensure_ascii=False)}\n}}catch (e) {{}}</script>"


def test_parse_review_picks_review_by_org_key():
    page = _page(
        {
            "/sprav/1": {"text": "Чужой отзыв", "timestamp": 1754911492503},
            "/sprav/17031236197": {"text": "Прекрасное место.\nСплав <по> Протве.\n\n", "timestamp": 1698338430720},
        }
    )
    assert parse_review(page, "/sprav/17031236197") == YandexReview(
        text="<p>Прекрасное место.</p><p>Сплав &lt;по&gt; Протве.</p>", date=date(2023, 10, 26)
    )


def test_parse_review_without_timestamp_has_no_date():
    assert parse_review(_page({"/sprav/1": {"text": "Текст"}}), "/sprav/1").date is None


@pytest.mark.parametrize(
    "page",
    ["<html>капча</html>", _page({"/sprav/2": {"text": "Другой"}}), _page({"/sprav/1": {"text": " \n "}})],
    ids=["no-data", "no-review", "empty-text"],
)
def test_parse_review_errors(page):
    with pytest.raises(ReviewFetchError):
        parse_review(page, "/sprav/1")


def test_review_key():
    assert review_key(URL) == "/sprav/17031236197"
    for bad in ["https://yandex.ru/maps/org/1/reviews/", "http://reviews.yandex.ru/user/x?boostId=/sprav/1"]:
        with pytest.raises(ReviewFetchError):
            review_key(bad)
    with pytest.raises(ReviewFetchError, match="boostId"):
        review_key("https://reviews.yandex.ru/user/x")


@pytest.mark.django_db
def test_admin_fetch_view(admin_client, monkeypatch):
    fetch_url = reverse("admin:content_review_fetch_yandex")
    monkeypatch.setattr(yandex, "urlopen", None)  # в тестах в сеть не ходим
    monkeypatch.setattr(
        "apps.content.admin.fetch_review", lambda url: YandexReview("<p>Классно</p>", date(2023, 10, 26))
    )
    response = admin_client.get(fetch_url, {"url": URL})
    assert response.json() == {"text": "<p>Классно</p>", "date": "26.10.2023"}

    def fail(url):
        raise ReviewFetchError("Яндекс не ответил")

    monkeypatch.setattr("apps.content.admin.fetch_review", fail)
    response = admin_client.get(fetch_url, {"url": URL})
    assert response.status_code == 400 and response.json() == {"error": "Яндекс не ответил"}


@pytest.mark.django_db
def test_admin_review_form_has_fetch_button_hook(admin_client):
    html = admin_client.get(reverse("admin:content_review_add")).content.decode()
    assert f'data-yandex-fetch-url="{reverse("admin:content_review_fetch_yandex")}"' in html
    assert "js/admin_review_fetch.js" in html and "js/admin_unsaved.js" in html


@pytest.mark.django_db
def test_admin_fetch_view_requires_staff(client):
    response = client.get(reverse("admin:content_review_fetch_yandex"), {"url": URL})
    assert response.status_code == 302  # на страницу входа
