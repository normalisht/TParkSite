"""Защита входа в админку от подбора пароля (django-axes)."""

import pytest

pytestmark = pytest.mark.django_db

LOGIN = "/admin/login/"


@pytest.fixture(autouse=True)
def axes_on(settings):
    settings.AXES_ENABLED = True  # в settings_test выключен: тестовый client.login() не передаёт request


@pytest.fixture
def boss(django_user_model):
    return django_user_model.objects.create_superuser("boss", password="right-pass-123")


def _login(client, username, password, ip):
    return client.post(LOGIN, {"username": username, "password": password}, HTTP_X_REAL_IP=ip)


def test_lockout_after_five_failures(client, boss):
    for _ in range(5):
        _login(client, "boss", "wrong", "203.0.113.5")
    response = _login(client, "boss", "right-pass-123", "203.0.113.5")
    assert response.status_code in (403, 429)


def test_lockout_is_per_username_and_ip(client, boss, django_user_model):
    django_user_model.objects.create_superuser("editor", password="editor-pass-123")
    for _ in range(5):
        _login(client, "boss", "wrong", "203.0.113.5")
    # Тот же логин с другого IP и другой логин с того же IP входят.
    assert _login(client, "boss", "right-pass-123", "198.51.100.7").status_code == 302
    client.logout()
    assert _login(client, "editor", "editor-pass-123", "203.0.113.5").status_code == 302


def test_successful_login_works(client, boss):
    assert _login(client, "boss", "right-pass-123", "203.0.113.5").status_code == 302
