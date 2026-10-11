"""Общие фикстуры браузерных тестов (make e2e)."""

from pathlib import Path

import pytest
from django.conf import settings


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
def built_css():
    if not (Path(settings.BASE_DIR) / "static/css/tailwind.css").exists():
        pytest.skip("Нет static/css/tailwind.css: uv run manage.py tailwind build")
