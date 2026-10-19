"""Общие фикстуры браузерных тестов (make e2e)."""

import threading
from pathlib import Path

import pytest
from django.conf import settings
from django.db.backends.signals import connection_created


@pytest.fixture(scope="session", autouse=True)
def allow_orm_next_to_playwright():
    """Playwright держит в потоке теста event loop — без этого ORM (в т. ч. в сессионных фикстурах БД) падает
    с SynchronousOnlyOperation. Фикстура создаётся, только когда e2e-тесты выбраны, и снимает переменную после них:
    на уровне модуля она отключила бы проверку для всего прогона pytest.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        yield


@pytest.fixture(autouse=True)
def close_live_server_connections():
    """Потоки запросов live server открывают свои соединения к тестовой in-memory SQLite, а Django их не закрывает
    (`close()` у in-memory базы ничего не делает): без этого — ResourceWarning, а предупреждения в тестах — ошибки.
    База живёт, пока открыто соединение основного потока.
    """
    opened = []

    def remember(sender, connection, **kwargs):
        if threading.current_thread() is not threading.main_thread():
            opened.append(connection.connection)

    connection_created.connect(remember)
    yield
    connection_created.disconnect(remember)
    for conn in opened:
        conn.close()


@pytest.fixture(autouse=True)
def built_css():
    if not (Path(settings.BASE_DIR) / "static/css/tailwind.css").exists():
        pytest.skip("Нет static/css/tailwind.css: uv run manage.py tailwind build")
