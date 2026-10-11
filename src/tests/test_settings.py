import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _settings_probe(env: dict, expr: str) -> subprocess.CompletedProcess:
    """Импортирует config.settings в чистом процессе с заданным окружением."""
    clean_env = {k: v for k, v in os.environ.items() if k not in {"SECRET_KEY", "DEBUG"}}
    clean_env.update(env)
    code = f"import config.settings as s; print({expr})"
    return subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=clean_env, capture_output=True, text=True, check=False
    )


@pytest.mark.django_db
def test_healthz_ok(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_missing_secret_key_in_production_fails():
    result = _settings_probe({"DEBUG": "0", "SECRET_KEY": ""}, "s.SECRET_KEY")
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_production_security_flags():
    result = _settings_probe(
        {"DEBUG": "0", "SECRET_KEY": "x"},
        "s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE, s.SECURE_PROXY_SSL_HEADER",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True True ('HTTP_X_FORWARDED_PROTO', 'https')"


def test_sqlite_options():
    result = _settings_probe({"DEBUG": "1"}, "s.DATABASES['default']['OPTIONS']['transaction_mode']")
    assert result.stdout.strip() == "IMMEDIATE"


def test_async_safety_not_disabled_for_regular_tests():
    """e2e-модуль (Playwright) отключает проверку async-safety Django только на время своих тестов, а не всей сессии."""
    assert "DJANGO_ALLOW_ASYNC_UNSAFE" not in os.environ


def test_ssl_redirect_goes_to_canonical_host_in_one_hop():
    # http://www.… с редиректом средствами Django должен вести сразу на https://<главный домен>, а не на https://www.…
    result = _settings_probe({"DEBUG": "0", "SECRET_KEY": "x", "CANONICAL_HOST": "t-camp.ru"}, "s.SECURE_SSL_HOST")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "t-camp.ru"
    result = _settings_probe({"DEBUG": "0", "SECRET_KEY": "x", "CANONICAL_HOST": ""}, "s.SECURE_SSL_HOST")
    assert result.stdout.strip() == "None"


def test_axes_admin_is_disabled_in_settings():
    result = _settings_probe({"DEBUG": "1"}, "s.AXES_ENABLE_ADMIN")
    assert result.stdout.strip() == "False"


def test_hsts_default_is_one_day():
    # Смотрим исходник: в окружении разработчика HSTS_SECONDS может прийти из .env и перекрыть значение по умолчанию.
    source = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'os.environ.get("HSTS_SECONDS", "86400")' in source
