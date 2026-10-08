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
