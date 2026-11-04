"""Переобход поисковиками: Last-Modified и 304 на If-Modified-Since (Яндекс), IndexNow после сохранения записи."""

import json
from datetime import date, timedelta
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest
from django.urls import reverse
from django.utils.http import http_date

from apps.catalog.models import Category, Service
from apps.content.models import Event
from apps.core import indexnow
from apps.core.models import InfoPage, PageVersion, SiteSettings

pytestmark = pytest.mark.django_db


# --- Last-Modified ---


def test_page_has_last_modified_and_answers_304(client):
    SiteSettings.load()
    first = client.get("/about/")
    assert first.status_code == 200
    assert first.has_header("Last-Modified") and first.has_header("ETag")
    again = client.get("/about/", HTTP_IF_MODIFIED_SINCE=first["Last-Modified"])
    assert again.status_code == 304
    assert again["Last-Modified"] == first["Last-Modified"]


def test_changed_page_gets_newer_date(client):
    settings_obj = SiteSettings.load()
    first = client.get("/about/")
    settings_obj.about_motto = "Новый девиз парка"
    settings_obj.save()
    second = client.get("/about/", HTTP_IF_MODIFIED_SINCE=first["Last-Modified"])
    assert second.status_code == 200
    assert second["Last-Modified"] != first["Last-Modified"]


def test_version_date_follows_etag():
    first = PageVersion.modified_at_for("/about/", '"a"')
    assert PageVersion.modified_at_for("/about/", '"a"') == first
    second = PageVersion.modified_at_for("/about/", '"b"')
    assert second > first
    # Возврат к прежнему HTML — новая дата, а не старая: робот с копией «b» иначе получил бы 304.
    assert PageVersion.modified_at_for("/about/", '"a"') > second


def test_version_update_does_not_overwrite_newer_row():
    first = PageVersion.modified_at_for("/about/", '"a"')
    PageVersion.objects.filter(path="/about/").update(etag='"b"', modified_at=first + timedelta(seconds=5))
    PageVersion.modified_at_for("/about/", '"c"')
    assert PageVersion.objects.get(path="/about/").etag == '"c"'


@pytest.mark.parametrize("url", ["/about/?utm_source=vk", "/no-such-page/"])
def test_no_last_modified_for_query_string_and_404(client, url):
    SiteSettings.load()
    assert not client.get(url).has_header("Last-Modified")
    assert not PageVersion.objects.exists()


def test_no_last_modified_in_admin(admin_client):
    response = admin_client.get(reverse("admin:index"))
    assert response.status_code == 200
    assert not response.has_header("Last-Modified")


def test_no_last_modified_for_draft_preview(admin_client):
    category = Category.objects.create(name="Черновик", is_published=False)
    response = admin_client.get(category.get_absolute_url())
    assert response.status_code == 200
    assert not response.has_header("Last-Modified")


def test_last_modified_is_http_date(client):
    SiteSettings.load()
    response = client.get("/about/")
    stored = PageVersion.objects.get(path="/about/").modified_at
    assert response["Last-Modified"] == http_date(stored.timestamp())


# --- IndexNow ---


@pytest.fixture
def indexnow_on(settings, monkeypatch):
    settings.INDEXNOW_KEY = "test-key-123"
    settings.CANONICAL_HOST = "t-camp.ru"
    monkeypatch.setattr(indexnow, "_pending", set())
    monkeypatch.setattr(indexnow, "_sent_at", {})
    sent = []
    monkeypatch.setattr(indexnow, "notify", sent.extend)
    return sent


def _save(obj, django_capture_on_commit_callbacks, **fields):
    for name, value in fields.items():
        setattr(obj, name, value)
    with django_capture_on_commit_callbacks(execute=True):
        obj.save()


def test_published_page_is_sent_after_commit(indexnow_on, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        category = Category.objects.create(name="Сплавы", slug="splavy", is_published=True)
    assert indexnow_on == ["https://t-camp.ru/category/splavy/"]
    assert category.pk


def test_draft_is_not_sent(indexnow_on, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        Category.objects.create(name="Черновик", is_published=False)
        Service.objects.create(name="Без страницы", has_page=False, is_published=True)
    assert indexnow_on == []


def test_unpublished_and_trashed_pages_are_sent(indexnow_on, django_capture_on_commit_callbacks):
    page = InfoPage.objects.create(title="Правила", slug="rules", is_published=True)
    event = Event.objects.create(title="Праздник", date=date(2026, 8, 1), is_published=True)
    indexnow_on.clear()
    _save(page, django_capture_on_commit_callbacks, is_published=False)
    with django_capture_on_commit_callbacks(execute=True):
        event.move_to_trash()
    assert indexnow_on == ["https://t-camp.ru/info/rules/", f"https://t-camp.ru{event.get_absolute_url()}"]


def test_slug_change_sends_old_and_new_address(indexnow_on, django_capture_on_commit_callbacks):
    service = Service.objects.create(name="Сплав", slug="splav", has_page=True, is_published=True)
    indexnow_on.clear()
    _save(service, django_capture_on_commit_callbacks, slug="splav-na-kanoe")
    assert sorted(indexnow_on) == ["https://t-camp.ru/service/splav-na-kanoe/", "https://t-camp.ru/service/splav/"]


def test_nothing_sent_without_key(settings, monkeypatch, django_capture_on_commit_callbacks):
    settings.CANONICAL_HOST = "t-camp.ru"
    sent = []
    monkeypatch.setattr(indexnow, "notify", sent.extend)
    with django_capture_on_commit_callbacks(execute=True):
        Category.objects.create(name="Сплавы", is_published=True)
    assert sent == []


@pytest.fixture
def flush_env(settings, monkeypatch):
    settings.INDEXNOW_KEY = "test-key-123"
    settings.CANONICAL_HOST = "t-camp.ru"
    monkeypatch.setattr(indexnow, "_pending", set())
    monkeypatch.setattr(indexnow, "_sent_at", {})
    clock = {"now": 1000.0}
    monkeypatch.setattr(indexnow.time, "monotonic", lambda: clock["now"])
    timers = []

    class FakeTimer:
        def __init__(self, wait, fn, args):
            timers.append(wait)
            self.daemon = False

        def start(self):
            pass

    monkeypatch.setattr(indexnow.threading, "Timer", FakeTimer)
    sent = []
    monkeypatch.setattr(indexnow, "send", sent.append)
    monkeypatch.setattr(indexnow, "run_in_background", lambda fn: fn())
    return clock, timers, sent


def test_pending_urls_go_in_one_request(flush_env):
    _, timers, sent = flush_env
    indexnow._pending.update({"https://t-camp.ru/b/", "https://t-camp.ru/a/"})
    indexnow._flush()
    assert sent == [["https://t-camp.ru/a/", "https://t-camp.ru/b/"]]
    assert timers == []


def test_repeat_within_ten_minutes_is_postponed(flush_env):
    clock, timers, sent = flush_env
    indexnow.notify(["https://t-camp.ru/a/"])
    clock["now"] += 100
    indexnow.notify(["https://t-camp.ru/a/", "https://t-camp.ru/b/"])
    assert sent == [["https://t-camp.ru/a/"], ["https://t-camp.ru/b/"]]
    assert timers == [500]
    clock["now"] += 500
    indexnow._flush()
    assert sent[-1] == ["https://t-camp.ru/a/"]


def _fake_urlopen(captured, status=200):
    class Response:
        def __init__(self):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout):
        captured.append(request)
        return Response()

    return urlopen


def test_send_posts_json_with_key(settings, monkeypatch):
    settings.INDEXNOW_KEY = "test-key-123"
    settings.CANONICAL_HOST = "t-camp.ru"
    captured = []
    monkeypatch.setattr(indexnow, "urlopen", _fake_urlopen(captured))
    indexnow.send(["https://t-camp.ru/about/"])
    request = captured[0]
    assert request.full_url == indexnow.API_URL and request.get_method() == "POST"
    assert json.loads(request.data) == {
        "host": "t-camp.ru",
        "key": "test-key-123",
        "urlList": ["https://t-camp.ru/about/"],
    }


def test_send_logs_rejection(settings, monkeypatch, caplog):
    settings.INDEXNOW_KEY = "test-key-123"
    settings.CANONICAL_HOST = "t-camp.ru"

    def urlopen(request, timeout):
        raise HTTPError(indexnow.API_URL, 403, "Forbidden", Message(), BytesIO(b""))

    monkeypatch.setattr(indexnow, "urlopen", urlopen)
    indexnow.send(["https://t-camp.ru/about/"])
    assert "HTTP 403" in caplog.text


def test_key_file(client, settings):
    settings.INDEXNOW_KEY = "test-key-123"
    response = client.get("/test-key-123.txt")
    assert response.status_code == 200
    assert response.content == b"test-key-123"
    assert response["Content-Type"].startswith("text/plain")
    assert client.get("/other-key-1.txt").status_code == 404


def test_key_file_missing_without_key(client):
    assert client.get("/test-key-123.txt").status_code == 404
