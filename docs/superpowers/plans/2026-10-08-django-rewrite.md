# Сайт Т-Парка на Django: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переписать сайт t-camp.ru на Django 6.1 (шаблоны + Tailwind, админка Unfold), перенести данные старой Flask-версии командой `import_legacy` и упаковать в docker compose за внешним reverse-proxy.

**Architecture:** Один Django-проект в корне репозитория: `config/` (настройки и URL), три приложения — `apps/core` (настройки сайта, телефоны, инфо-страницы, общие хелперы, SEO, редиректы, импорт, бэкап), `apps/catalog` (группы, категории, услуги, фото), `apps/content` (мероприятия, отзывы, партнёры, сотрудники, галерея). Страницы рендерятся сервером. Изображения — `ImageField` (django-imagekit), HTML — `django-prose-editor` с очисткой `nh3`. В продакшене два контейнера: `web` (gunicorn + WhiteNoise) и `media` (nginx), оба во внешней сети прокси.

**Tech Stack:** Python 3.14, Django 6.1.2, uv, SQLite, django-unfold, django-prose-editor + nh3, django-imagekit + Pillow, django-tailwind-cli (Tailwind v4), Alpine.js, Swiper, GLightbox, unidecode, WhiteNoise, gunicorn, pytest + pytest-django, ruff, Docker.

**Spec:** `docs/superpowers/specs/2026-10-08-django-rewrite-design.md` (журнал решений — `docs/decisions.md`, старый функционал — `docs/current-functionality.md`, старый код — `old_version/`).

## Global Constraints

- Python 3.14; Django `>=6.1.2,<6.2`; зависимости только через uv (`pyproject.toml` + `uv.lock`), dev-зависимости в группе `dev`.
- БД — SQLite с `transaction_mode="IMMEDIATE"`, WAL (`init_command`), `timeout` 20 с.
- Весь пользовательский текст (сайт, админка, сообщения команд) — на русском; `LANGUAGE_CODE = "ru"`, `TIME_ZONE = "Europe/Moscow"`, `USE_TZ = True`.
- Изображения при загрузке пережимаются до ≤1920×1080, JPEG q85 (превью категорий — 1080×720); миниатюры — WebP через `ImageSpecField`. Допустимые форматы загрузки: jpg, jpeg, png, webp; до 20 МБ на файл.
- Порядок везде — поле `order` (PositiveIntegerField, индекс), сортировка `("order", "id")`, в админке — перетаскивание Unfold (`ordering_field="order"`, `hide_ordering_field=True`).
- HTML-поля — только через `apps.core.fields.HtmlField` (общий набор расширений: абзацы, жирный, курсив, h2–h3, списки, ссылки, перенос строки).
- Файлы удаляются вместе с записью и при замене — только после коммита транзакции (`transaction.on_commit`).
- Неопубликованное → 404 на публичной части; на пустой БД (нет настроек, категорий, мероприятий) все публичные страницы отдают 200.
- Фронт без Node и без CDN: Tailwind через standalone-бинарник `django-tailwind-cli`, JS-библиотеки — vendored-файлы в `static/vendor/`.
- Старый код в `old_version/` не меняем; он исключён из ruff и pre-commit.
- Коммиты — на русском, с завершающей строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Перенос флага WhatsApp/Telegram с одного номера на другой за одно сохранение формы** — должен сохраняться без ошибки (Django проверяет ограничения модели построчно и видит старый флаг в БД). Тест: Task 6, `test_phone_flag_can_move_between_numbers`.
2. **Отсутствующий или битый файл изображения** (в медиа или в старой папке `../../../src/old_migrate/images/`) не должен ронять ни страницу, ни импорт: страница рендерится без картинки, импорт пишет предупреждение. Тесты: Task 7 `test_home_survives_missing_preview_file`, Task 13 `test_corrupt_image_is_warning_not_failure`.
3. **Мусор в параметрах старых URL** (`/category?category_id=abc`, пустой параметр) — 404, а не 500. Тест: Task 9 `test_legacy_redirect_bad_param_is_404`.
4. **Откат импорта** (ошибка посередине, в том числе с `--flush`) — БД возвращается к исходному состоянию, новые файлы удалены, файлы старого контента не удалены. Тест: Task 13 `test_failed_import_rolls_back_db_and_files`.
5. **Коллизия имён сервисов во внешней сети прокси** — у контейнеров уникальные алиасы `tpark-web` и `tpark-media`, а не общие `web`/`media`. Проверка: Task 15, шаг проверки `docker compose config`.

---

## Структура файлов

```
pyproject.toml, uv.lock, manage.py, .env.example, .gitignore, .dockerignore, CLAUDE.md, README.md
config/__init__.py, settings.py, settings_test.py, urls.py, wsgi.py
apps/__init__.py
apps/core/
  apps.py, models.py, admin.py, views.py, urls.py, context_processors.py, sitemaps.py
  fields.py          HtmlField, sanitize_html, photo_field, image_spec, UploadTo, validate_image_upload
  files.py           register_file_cleanup
  slugs.py           slugify_ru, unique_slug
  images.py          safe_spec_url
  seo.py             plaintext, make_seo
  bulk_upload.py     MultipleImageField, BulkUploadForm, append_images
  admin_utils.py     image_preview
  legacy_redirects.py
  templatetags/site_tags.py
  legacy/            reader.py, report.py, media.py, html.py, site.py, catalog.py, content.py, runner.py
  management/commands/import_legacy.py, backup_db.py
apps/catalog/  apps.py, models.py, admin.py, views.py, urls.py, context_processors.py
apps/content/  apps.py, models.py, admin.py, views.py, urls.py
templates/     base.html, 404.html, 500.html, partials/, icons/, catalog/, content/, core/, admin/
static/        img/, js/site.js, vendor/
tailwind/source.css
tests/         conftest.py, test_*.py, legacy/schema.sql, legacy/conftest.py
Dockerfile, compose.yaml, docker/entrypoint.sh, docker/nginx-media.conf, scripts/backup.sh
```

Все команды ниже выполняются из корня репозитория.

---

### Task 1: Каркас проекта, настройки, healthcheck

**Files:**
- Create: `pyproject.toml` (через `uv init`), `uv.lock`, `manage.py`, `config/__init__.py`, `config/settings.py`, `config/settings_test.py`, `config/urls.py`, `config/wsgi.py`, `apps/__init__.py`, `apps/core/__init__.py`, `apps/core/apps.py`, `apps/core/views.py`, `.env.example`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_settings.py`
- Modify: `.gitignore` (полностью заменить)

**Interfaces:**
- Produces: `config.settings` (`env_bool`, `env_list`, `BASE_DIR`), url-имя `healthz` (`/healthz/`), view `apps.core.views.healthz(request) -> HttpResponse`.

- [ ] **Step 1: Инициализировать uv-проект и поставить зависимости**

```bash
uv init --bare --python 3.14 --name tpark
uv add "django>=6.1.2,<6.2" django-unfold django-prose-editor nh3 django-imagekit pillow django-tailwind-cli whitenoise gunicorn unidecode
uv add --dev pytest pytest-django ruff pre-commit
uv run django-admin --version
```
Expected: последняя строка — `6.1.2` (или более новый патч 6.1.x).

- [ ] **Step 2: Дописать в `pyproject.toml` конфиг pytest и ruff**

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings_test"
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"

[tool.ruff]
target-version = "py314"
extend-exclude = ["old_version"]
```

- [ ] **Step 3: Заменить `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
/db.sqlite3*
/media/
/staticfiles/
/static/css/tailwind.css
/.django_tailwind_cli/
/backups/
/price_legacy.csv
.pytest_cache/
.ruff_cache/
.idea/
.DS_Store
/old_version/app/static/images
```

- [ ] **Step 4: Написать падающий тест настроек**

`tests/__init__.py` — пустой. `tests/conftest.py`:

```python
import pytest


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Каждый тест пишет медиафайлы во временную папку."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT
```

`tests/test_settings.py`:

```python
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
        [sys.executable, "-c", code], cwd=ROOT, env=clean_env, capture_output=True, text=True
    )


@pytest.mark.django_db
def test_healthz_ok(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.content == b"ok"


def test_missing_secret_key_in_production_fails(tmp_path):
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
    result = _settings_probe(
        {"DEBUG": "1"}, "s.DATABASES['default']['OPTIONS']['transaction_mode']"
    )
    assert result.stdout.strip() == "IMMEDIATE"
```

Внимание: `_settings_probe` запускается без `.env` в корне (его нет в репозитории); если у разработчика `.env` существует, он может подставить `SECRET_KEY` — тест `test_missing_secret_key_in_production_fails` явно передаёт пустой `SECRET_KEY`, а загрузчик `.env` использует `setdefault`, поэтому пустое значение из окружения выигрывает.

- [ ] **Step 5: Запустить тесты — убедиться, что падают**

Run: `uv run pytest tests/test_settings.py`
Expected: FAIL / ERROR (нет `config.settings_test`).

- [ ] **Step 6: Создать `manage.py`, `config/*`, `apps/core/*`**

`manage.py`:

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`config/__init__.py`, `apps/__init__.py`, `apps/core/__init__.py` — пустые.

`config/settings.py`:

```python
"""Настройки проекта. Значения, зависящие от окружения, читаются из переменных окружения
(локально — из файла .env в корне репозитория)."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-insecure-key"
    else:
        raise ImproperlyConfigured("Задайте SECRET_KEY в окружении (или DEBUG=1 для разработки).")

# localhost нужен healthcheck'у контейнера.
ALLOWED_HOSTS = [*env_list("ALLOWED_HOSTS"), "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django_prose_editor",
    "imagekit",
    "django_tailwind_cli",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "3600"))
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

`config/settings_test.py`:

```python
import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DEBUG", "0")

from config.settings import *  # noqa: E402,F403

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

`config/wsgi.py`:

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`config/urls.py`:

```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.core.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

`apps/core/apps.py`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Сайт"
```

`apps/core/views.py`:

```python
from django.db import connection
from django.http import HttpResponse


def healthz(request):
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")
```

`.env.example`:

```dotenv
DEBUG=1
SECRET_KEY=
ALLOWED_HOSTS=t-camp.ru,www.t-camp.ru
CSRF_TRUSTED_ORIGINS=https://t-camp.ru,https://www.t-camp.ru
# Только для docker compose:
PROXY_NETWORK=proxy
WEB_CONCURRENCY=3
HSTS_SECONDS=3600
```

- [ ] **Step 7: Запустить тесты — убедиться, что проходят**

Run: `uv run pytest tests/test_settings.py`
Expected: 4 passed.

- [ ] **Step 8: Проверить запуск и линтер**

```bash
DEBUG=1 uv run manage.py check
uv run ruff check . && uv run ruff format --check .
```
Expected: `System check identified no issues`, ruff без ошибок.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock manage.py config apps .env.example .gitignore tests
git commit -m "Каркас Django-проекта: настройки из окружения, healthcheck, pytest

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Общие хелперы core — HTML, изображения, slug

**Files:**
- Create: `apps/core/fields.py`, `apps/core/slugs.py`, `apps/core/images.py`, `tests/test_core_helpers.py`
- Modify: `tests/conftest.py` (добавить `make_image`)

**Interfaces:**
- Produces:
  - `apps.core.fields.HTML_EXTENSIONS: dict`; `HtmlField(verbose_name: str, **kwargs) -> ProseEditorField` (blank=True, sanitize=True); `sanitize_html(html: str) -> str`;
  - `UploadTo(prefix: str)` — deconstructible callable `(instance, filename) -> f"{prefix}/{uuid4().hex}{ext}"`;
  - `validate_image_upload(file) -> None` (ValidationError на чужой формат или > 20 МБ); `MAX_UPLOAD_BYTES = 20 * 1024 * 1024`; `ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}`;
  - `photo_field(verbose_name, prefix, *, size=(1920, 1080), fmt="JPEG", **kwargs) -> ProcessedImageField`;
  - `image_spec(source: str, width: int, height: int, *, crop: bool = True) -> ImageSpecField` (WebP q80);
  - `apps.core.slugs.slugify_ru(value: str) -> str`; `unique_slug(instance, value: str, field: str = "slug") -> str`;
  - `apps.core.images.safe_spec_url(obj, spec_name: str) -> str` (пустая строка при любой ошибке).
  - фикстура `make_image(name="photo.jpg", size=(64, 48), fmt="JPEG") -> SimpleUploadedFile`.

- [ ] **Step 1: Добавить фикстуру `make_image` в `tests/conftest.py`**

```python
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


@pytest.fixture
def make_image():
    def _make(name: str = "photo.jpg", size=(64, 48), fmt: str = "JPEG") -> SimpleUploadedFile:
        buffer = io.BytesIO()
        Image.new("RGB", size, "orange").save(buffer, fmt)
        content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}[fmt]
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    return _make
```

(Импорты `io`, `SimpleUploadedFile`, `Image` — в начало файла рядом с `import pytest`.)

- [ ] **Step 2: Написать падающие тесты**

`tests/test_core_helpers.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.fields import UploadTo, sanitize_html, validate_image_upload
from apps.core.images import safe_spec_url
from apps.core.slugs import slugify_ru


def test_sanitize_keeps_allowed_and_strips_scripts():
    html = '<p><strong>Жирный</strong> <a href="https://t-camp.ru">ссылка</a></p><script>alert(1)</script>'
    cleaned = sanitize_html(html)
    assert "<strong>Жирный</strong>" in cleaned
    assert 'href="https://t-camp.ru"' in cleaned
    assert "script" not in cleaned


def test_sanitize_drops_inline_styles():
    assert "style" not in sanitize_html('<p style="color:red">x</p>')


def test_slugify_ru_transliterates():
    assert slugify_ru("Байдарки и SUP") == "baidarki-i-sup"


def test_slugify_ru_empty_falls_back():
    assert slugify_ru("!!!") == "item"


def test_upload_to_generates_unique_names():
    upload_to = UploadTo("gallery")
    first, second = upload_to(None, "Фото 1.JPG"), upload_to(None, "Фото 1.JPG")
    assert first.startswith("gallery/") and first.endswith(".jpg")
    assert first != second


def test_validate_accepts_jpeg(make_image):
    validate_image_upload(make_image())


def test_validate_rejects_gif(make_image):
    with pytest.raises(ValidationError, match="jpg, png или webp"):
        validate_image_upload(make_image("anim.gif", fmt="GIF"))


def test_validate_rejects_too_big(make_image):
    big = make_image()
    big.size = 20 * 1024 * 1024 + 1
    with pytest.raises(ValidationError, match="20 МБ"):
        validate_image_upload(big)


def test_validate_rejects_not_an_image():
    with pytest.raises(ValidationError):
        validate_image_upload(SimpleUploadedFile("fake.jpg", b"not an image"))


def test_validate_skips_already_stored_file():
    class Stored:
        _committed = True
        size = 10**9

    validate_image_upload(Stored())


def test_safe_spec_url_swallows_errors():
    class Broken:
        @property
        def thumb(self):
            raise FileNotFoundError("нет файла")

    assert safe_spec_url(Broken(), "thumb") == ""
    assert safe_spec_url(object(), "missing") == ""
```

- [ ] **Step 3: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_core_helpers.py`
Expected: ERROR (`ModuleNotFoundError: apps.core.fields`).

- [ ] **Step 4: Реализовать хелперы**

`apps/core/fields.py`:

```python
"""Общие поля моделей: HTML с очисткой и изображения с пережатием."""

from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django_prose_editor.fields import ProseEditorField, create_sanitizer
from imagekit.models import ImageSpecField, ProcessedImageField
from imagekit.processors import ResizeToFill, ResizeToFit
from PIL import Image

HTML_EXTENSIONS = {
    "Bold": True,
    "Italic": True,
    "Heading": {"levels": [2, 3]},
    "BulletList": True,
    "OrderedList": True,
    "ListItem": True,
    "HardBreak": True,
    "Link": {"enableTarget": True, "protocols": ["http", "https", "mailto", "tel"]},
}

_sanitizer = create_sanitizer(HTML_EXTENSIONS)


def sanitize_html(html: str) -> str:
    """Та же очистка, что применяет редактор при сохранении формы (нужна импорту)."""
    return _sanitizer(html or "")


def HtmlField(verbose_name: str, **kwargs) -> ProseEditorField:  # noqa: N802 — фабрика поля
    kwargs.setdefault("blank", True)
    return ProseEditorField(verbose_name, extensions=HTML_EXTENSIONS, sanitize=True, **kwargs)


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(file) -> None:
    if getattr(file, "_committed", False):
        return  # файл уже в хранилище — проверяли при загрузке; отсутствие файла на диске не должно блокировать сохранение
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Файл больше 20 МБ.")
    try:
        position = file.tell()
        with Image.open(file) as image:
            image_format = image.format
        file.seek(position)
    except Exception as exc:
        raise ValidationError("Файл не похож на изображение.") from exc
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Допустимые форматы: jpg, png или webp.")


@deconstructible
class UploadTo:
    """Кладёт файл в папку `prefix` под случайным именем — без коллизий и кириллицы в путях."""

    def __init__(self, prefix: str):
        self.prefix = prefix

    def __call__(self, instance, filename: str) -> str:
        return f"{self.prefix}/{uuid4().hex}{Path(filename).suffix.lower()}"

    def __eq__(self, other):
        return isinstance(other, UploadTo) and other.prefix == self.prefix


def photo_field(verbose_name: str, prefix: str, *, size=(1920, 1080), fmt="JPEG", **kwargs):
    kwargs.setdefault("blank", True)
    return ProcessedImageField(
        verbose_name=verbose_name,
        upload_to=UploadTo(prefix),
        processors=[ResizeToFit(*size, upscale=False)],
        format=fmt,
        options={"quality": 85},
        validators=[validate_image_upload],
        **kwargs,
    )


def image_spec(source: str, width: int, height: int, *, crop: bool = True) -> ImageSpecField:
    processor = ResizeToFill(width, height) if crop else ResizeToFit(width, height, upscale=False)
    return ImageSpecField(source=source, processors=[processor], format="WEBP", options={"quality": 80})
```

Примечание: если `create_sanitizer` в установленной версии `django-prose-editor` переедет, импорт поправить по `django_prose_editor/fields.py` (в версии 0.27 функция находится там).

`apps/core/slugs.py`:

```python
from django.utils.text import slugify
from unidecode import unidecode


def slugify_ru(value: str, max_length: int = 200) -> str:
    return slugify(unidecode(value or ""))[:max_length].strip("-") or "item"


def unique_slug(instance, value: str, field: str = "slug") -> str:
    """Slug из `value`, уникальный среди записей той же модели (суффиксы -2, -3, …)."""
    base = slugify_ru(value)
    manager = type(instance)._default_manager
    candidate, counter = base, 2
    while manager.filter(**{field: candidate}).exclude(pk=instance.pk).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
```

`apps/core/images.py`:

```python
import logging

logger = logging.getLogger(__name__)


def safe_spec_url(obj, spec_name: str) -> str:
    """URL миниатюры imagekit или пустая строка, если исходника нет или он битый."""
    try:
        spec = getattr(obj, spec_name)
        return spec.url if spec else ""
    except Exception:
        logger.warning("Не удалось получить %s для %r", spec_name, obj, exc_info=True)
        return ""
```

- [ ] **Step 5: Запустить — убедиться, что проходят**

Run: `uv run pytest tests/test_core_helpers.py`
Expected: 11 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/core tests
git commit -m "Хелперы core: очистка HTML, поля изображений, slug, безопасные миниатюры

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Модели core — настройки сайта, телефоны, инфо-страницы, очистка файлов

**Files:**
- Create: `apps/core/models.py`, `apps/core/files.py`, `apps/core/migrations/0001_initial.py` (через makemigrations), `tests/test_core_models.py`
- Modify: `apps/core/apps.py` (подключить очистку файлов)

**Interfaces:**
- Consumes: `HtmlField`, `photo_field`, `unique_slug` (Task 2).
- Produces:
  - `apps.core.models.OrderedModel` (abstract, `order`, `Meta.ordering = ["order", "id"]`); `PublishedQuerySet.published()`;
  - `SiteSettings` (поля: `address`, `map_url`, `vk_url`, `home_intro`, `events_intro`, `about_text`, `philosophy_text`, `nearby_text`, `contacts_text`, `contacts_map`, `about_map`), `SiteSettings.load() -> SiteSettings`;
  - `Phone` (`settings` FK related_name `phones`, `number`, `order`, `is_whatsapp`, `is_telegram`; свойства `tel_url`, `whatsapp_url`, `telegram_url`, `display`);
  - `InfoPage` (`title`, `slug`, `body`, `is_published`; `objects.published()`; `get_absolute_url()` → `reverse("core:info", args=[slug])` — маршрут появится в Task 8);
  - `apps.core.files.register_file_cleanup(model) -> None`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_core_models.py`:

```python
import pytest
from django.db import IntegrityError

from apps.core.models import InfoPage, Phone, SiteSettings

pytestmark = pytest.mark.django_db


def test_site_settings_is_singleton():
    first = SiteSettings.load()
    second = SiteSettings.load()
    assert first.pk == second.pk == 1
    SiteSettings(address="другой").save()
    assert SiteSettings.objects.count() == 1
    assert SiteSettings.load().address == "другой"


def test_phone_links():
    phone = Phone(settings=SiteSettings.load(), number="9029856594")
    assert phone.tel_url == "tel:+79029856594"
    assert phone.whatsapp_url == "https://wa.me/79029856594"
    assert phone.telegram_url == "https://t.me/+79029856594"
    assert phone.display == "+7 (902) 985-65-94"


@pytest.mark.parametrize("flag", ["is_whatsapp", "is_telegram"])
def test_only_one_phone_per_messenger(flag):
    site = SiteSettings.load()
    Phone.objects.create(settings=site, number="9000000001", **{flag: True})
    with pytest.raises(IntegrityError):
        Phone.objects.create(settings=site, number="9000000002", **{flag: True})


def test_one_phone_can_have_both_flags():
    Phone.objects.create(settings=SiteSettings.load(), number="9000000001", is_whatsapp=True, is_telegram=True)


def test_info_page_slug_is_generated_and_unique():
    first = InfoPage.objects.create(title="Правила безопасности", body="<p>x</p>")
    second = InfoPage.objects.create(title="Правила безопасности", body="<p>y</p>")
    assert first.slug == "pravila-bezopasnosti"
    assert second.slug == "pravila-bezopasnosti-2"


def test_info_page_published_queryset():
    InfoPage.objects.create(title="A", is_published=True)
    InfoPage.objects.create(title="B", is_published=False)
    assert list(InfoPage.objects.published().values_list("title", flat=True)) == ["A"]


def test_files_deleted_after_commit(make_image, media_root, django_capture_on_commit_callbacks):
    site = SiteSettings.load()
    site.contacts_map = make_image()
    site.save()
    path = media_root / site.contacts_map.name
    assert path.exists()
    with django_capture_on_commit_callbacks(execute=True):
        site.delete()
    assert not path.exists()


def test_replaced_file_deleted_after_commit(make_image, media_root, django_capture_on_commit_callbacks):
    site = SiteSettings.load()
    site.about_map = make_image()
    site.save()
    old_path = media_root / site.about_map.name
    with django_capture_on_commit_callbacks(execute=True):
        site.about_map = make_image("new.jpg")
        site.save()
    assert not old_path.exists()
    assert (media_root / site.about_map.name).exists()


def test_files_kept_when_transaction_rolls_back(make_image, media_root):
    site = SiteSettings.load()
    site.contacts_map = make_image()
    site.save()
    path = media_root / site.contacts_map.name
    site.delete()  # без выполнения on_commit — как при откате
    assert path.exists()
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_core_models.py`
Expected: ERROR (`cannot import name 'InfoPage'`).

- [ ] **Step 3: Реализовать модели и очистку файлов**

`apps/core/models.py`:

```python
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.fields import HtmlField, photo_field
from apps.core.slugs import unique_slug


class OrderedModel(models.Model):
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class SiteSettings(models.Model):
    address = models.CharField("Адрес", max_length=255, blank=True)
    map_url = models.URLField("Ссылка на карту", max_length=500, blank=True)
    vk_url = models.URLField("VK", max_length=500, blank=True)
    home_intro = HtmlField("Вступление на главной")
    events_intro = HtmlField("Вступление на странице мероприятий")
    about_text = HtmlField("О нас")
    philosophy_text = HtmlField("Философия")
    nearby_text = HtmlField("Что рядом")
    contacts_text = HtmlField("Текст на странице контактов")
    contacts_map = photo_field("Карта на странице контактов", "site")
    about_map = photo_field("Карта на странице «О нас»", "site")

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Phone(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="phones")
    number = models.CharField(
        "Номер",
        max_length=10,
        validators=[RegexValidator(r"^\d{10}$", "10 цифр без +7 и 8, например 9029856594.")],
    )
    order = models.PositiveIntegerField("Порядок", default=0, db_index=True)
    is_whatsapp = models.BooleanField("WhatsApp", default=False)
    is_telegram = models.BooleanField("Telegram", default=False)

    class Meta:
        verbose_name = "Телефон"
        verbose_name_plural = "Телефоны"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["settings"], condition=Q(is_whatsapp=True), name="one_whatsapp_phone"),
            models.UniqueConstraint(fields=["settings"], condition=Q(is_telegram=True), name="one_telegram_phone"),
        ]

    def __str__(self):
        return self.display

    @property
    def tel_url(self) -> str:
        return f"tel:+7{self.number}"

    @property
    def whatsapp_url(self) -> str:
        return f"https://wa.me/7{self.number}"

    @property
    def telegram_url(self) -> str:
        return f"https://t.me/+7{self.number}"

    @property
    def display(self) -> str:
        n = self.number
        return f"+7 ({n[:3]}) {n[3:6]}-{n[6:8]}-{n[8:]}" if len(n) == 10 else n


class InfoPage(models.Model):
    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    body = HtmlField("Текст")
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Инфо-страница"
        verbose_name_plural = "Инфо-страницы"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("core:info", args=[self.slug])
```

`apps/core/files.py`:

```python
"""Удаление файлов вместе с записью и при замене файла — только после коммита транзакции,
чтобы откат (например, неудачный импорт) не оставлял записи без файлов."""

from django.db import models, transaction
from django.db.models.signals import post_delete, pre_save


def _file_fields(model):
    return [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]


def _delete_later(field_file) -> None:
    if field_file and field_file.name:
        storage, name = field_file.storage, field_file.name
        transaction.on_commit(lambda: storage.delete(name))


def register_file_cleanup(model) -> None:
    fields = _file_fields(model)

    def on_delete(sender, instance, **kwargs):
        for field in fields:
            _delete_later(getattr(instance, field.name))

    def on_save(sender, instance, **kwargs):
        if not instance.pk:
            return
        old = sender._default_manager.filter(pk=instance.pk).first()
        if old is None:
            return
        for field in fields:
            old_file, new_file = getattr(old, field.name), getattr(instance, field.name)
            if old_file and old_file.name != (new_file.name if new_file else None):
                _delete_later(old_file)

    post_delete.connect(on_delete, sender=model, weak=False, dispatch_uid=f"cleanup-delete-{model._meta.label}")
    pre_save.connect(on_save, sender=model, weak=False, dispatch_uid=f"cleanup-save-{model._meta.label}")
```

`apps/core/apps.py` — добавить `ready`:

```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Сайт"

    def ready(self):
        from apps.core.files import register_file_cleanup
        from apps.core.models import SiteSettings

        register_file_cleanup(SiteSettings)
```

- [ ] **Step 4: Сгенерировать миграцию**

Run: `DEBUG=1 uv run manage.py makemigrations core`
Expected: `Create model InfoPage`, `Create model SiteSettings`, `Create model Phone`.

- [ ] **Step 5: Запустить тесты**

Run: `uv run pytest tests/test_core_models.py`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/core tests
git commit -m "Модели core: настройки сайта, телефоны с флагами мессенджеров, инфо-страницы

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Модели каталога

**Files:**
- Create: `apps/catalog/__init__.py`, `apps/catalog/apps.py`, `apps/catalog/models.py`, `apps/catalog/migrations/0001_initial.py`, `tests/test_catalog_models.py`
- Modify: `config/settings.py` (`INSTALLED_APPS` += `"apps.catalog"`)

**Interfaces:**
- Consumes: `OrderedModel`, `PublishedQuerySet`, `HtmlField`, `photo_field`, `image_spec`, `unique_slug`, `register_file_cleanup`.
- Produces:
  - `CategoryGroup(name, order, categories M2M → Category, related_name "groups")`;
  - `Category(name, slug, description, preview, is_published, order)`, спецификация `preview_card` (640×427), `objects.published()`, `get_absolute_url()` → `reverse("catalog:category", args=[slug])`, `published_services() -> list[Service]`;
  - `CategoryPhoto(category FK related_name "photos", image, order)`, спецификации `slide` (1600×900, без обрезки) и `thumb` (320×240);
  - `Service(name, slug, short_description, description, price, price_unit, is_published, has_page)`, свойство `price_display`, `objects.published()`, `get_absolute_url()` → `reverse("catalog:service", args=[slug])`;
  - `CategoryService(category FK related_name "service_links", service FK related_name "category_links", order)`, unique `(category, service)`;
  - `ServicePhoto(service FK related_name "photos", image, order)`, спецификации `slide`, `thumb`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_catalog_models.py`:

```python
import pytest
from django.db import IntegrityError

from apps.catalog.models import Category, CategoryService, Service

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("price", "unit", "expected"),
    [("1500", "час", "1500 руб / час"), ("1500", "", "1500 руб"), ("", "час", ""), ("", "", "")],
)
def test_price_display(price, unit, expected):
    assert Service(name="x", price=price, price_unit=unit).price_display == expected


def test_slugs_generated():
    assert Category.objects.create(name="Байдарки").slug == "baidarki"
    assert Service.objects.create(name="Байдарки").slug == "baidarki"


def test_published_services_order_and_visibility():
    category = Category.objects.create(name="Сплавы", is_published=True)
    late = Service.objects.create(name="Поздняя")
    early = Service.objects.create(name="Ранняя")
    hidden = Service.objects.create(name="Скрытая", is_published=False)
    CategoryService.objects.create(category=category, service=late, order=5)
    CategoryService.objects.create(category=category, service=early, order=1)
    CategoryService.objects.create(category=category, service=hidden, order=0)
    assert category.published_services() == [early, late]


def test_category_service_unique():
    category = Category.objects.create(name="A")
    service = Service.objects.create(name="B")
    CategoryService.objects.create(category=category, service=service)
    with pytest.raises(IntegrityError):
        CategoryService.objects.create(category=category, service=service)


def test_category_defaults_hidden():
    assert Category.objects.create(name="Новая").is_published is False
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_catalog_models.py`
Expected: ERROR (`No module named 'apps.catalog'`).

- [ ] **Step 3: Реализовать приложение**

`apps/catalog/__init__.py` — пустой. `apps/catalog/apps.py`:

```python
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    verbose_name = "Каталог"

    def ready(self):
        from apps.catalog.models import Category, CategoryPhoto, ServicePhoto
        from apps.core.files import register_file_cleanup

        for model in (Category, CategoryPhoto, ServicePhoto):
            register_file_cleanup(model)
```

`apps/catalog/models.py`:

```python
from django.db import models
from django.urls import reverse

from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet
from apps.core.slugs import unique_slug


class CategoryGroup(OrderedModel):
    name = models.CharField("Название", max_length=128)
    categories = models.ManyToManyField("Category", related_name="groups", blank=True, verbose_name="Категории")

    class Meta(OrderedModel.Meta):
        verbose_name = "Группа категорий"
        verbose_name_plural = "Группы категорий"

    def __str__(self):
        return self.name


class Category(OrderedModel):
    name = models.CharField("Название", max_length=128)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    description = HtmlField("Описание")
    preview = photo_field("Превью для главной", "catalog/previews", size=(1080, 720))
    preview_card = image_spec("preview", 640, 427)
    is_published = models.BooleanField("Опубликовано", default=False)

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", args=[self.slug])

    def published_services(self) -> list["Service"]:
        links = (
            self.service_links.filter(service__is_published=True)
            .select_related("service")
            .order_by("order", "id")
        )
        return [link.service for link in links]


class CategoryPhoto(OrderedModel):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="photos")
    image = photo_field("Фото", "catalog/categories", blank=False)
    slide = image_spec("image", 1600, 900, crop=False)
    thumb = image_spec("image", 320, 240)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото категории"
        verbose_name_plural = "Фото категории"

    def __str__(self):
        return f"Фото #{self.pk}"


class Service(models.Model):
    name = models.CharField("Название", max_length=128)
    slug = models.SlugField("Адрес страницы", max_length=255, unique=True, blank=True)
    short_description = HtmlField("Краткое описание")
    description = HtmlField("Полное описание")
    price = models.CharField("Цена", max_length=32, blank=True, help_text="Например: 1500 или «договорная».")
    price_unit = models.CharField("За что", max_length=128, blank=True, help_text="Например: час, сутки, человек.")
    is_published = models.BooleanField("Опубликовано", default=True)
    has_page = models.BooleanField(
        "Отдельная страница", default=False, help_text="Карточка в категории ведёт на страницу услуги."
    )

    objects = PublishedQuerySet.as_manager()

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("catalog:service", args=[self.slug])

    @property
    def price_display(self) -> str:
        if not self.price:
            return ""
        return f"{self.price} руб / {self.price_unit}" if self.price_unit else f"{self.price} руб"


class CategoryService(OrderedModel):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="service_links", verbose_name="Категория")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="category_links", verbose_name="Услуга")

    class Meta(OrderedModel.Meta):
        verbose_name = "Услуга в категории"
        verbose_name_plural = "Услуги в категории"
        unique_together = [("category", "service")]

    def __str__(self):
        return f"{self.category} → {self.service}"


class ServicePhoto(OrderedModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="photos")
    image = photo_field("Фото", "catalog/services", blank=False)
    slide = image_spec("image", 1600, 900, crop=False)
    thumb = image_spec("image", 320, 240)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото услуги"
        verbose_name_plural = "Фото услуги"

    def __str__(self):
        return f"Фото #{self.pk}"
```

`config/settings.py`: в `INSTALLED_APPS` после `"apps.core"` добавить `"apps.catalog",`.

- [ ] **Step 4: Миграция и тесты**

```bash
DEBUG=1 uv run manage.py makemigrations catalog
uv run pytest tests/test_catalog_models.py
```
Expected: миграция создана; 8 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/catalog config/settings.py tests
git commit -m "Модели каталога: группы, категории, услуги, фото, порядок услуг в категории

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Модели контента

**Files:**
- Create: `apps/content/__init__.py`, `apps/content/apps.py`, `apps/content/models.py`, `apps/content/migrations/0001_initial.py`, `tests/test_content_models.py`
- Modify: `config/settings.py` (`INSTALLED_APPS` += `"apps.content"`)

**Interfaces:**
- Consumes: `OrderedModel`, `PublishedQuerySet`, `HtmlField`, `photo_field`, `image_spec`, `register_file_cleanup`.
- Produces:
  - `Event(title, date, description, link, text_color, show_after_date, image)`, спецификация `card` (800×600); `Event.objects.upcoming(today=None)` (дата ≥ сегодня, по возрастанию), `Event.objects.past_visible(today=None)` (дата < сегодня и `show_after_date`, по убыванию); `today` по умолчанию — `timezone.localdate()`;
  - `Review(author, text [HTML], photo, is_published, order)`, спецификация `avatar` (160×160), `objects.published()`;
  - `Partner(name, link, logo, order)`, спецификация `logo_small` (300×150, без обрезки);
  - `Employee(name, position, photo, order)`, спецификация `portrait` (400×500);
  - `GalleryPhoto(image, caption, order)`, спецификация `thumb` (600×600).

Примечание к спецификации: тексты отзывов в старой БД — HTML со ссылками на Яндекс-отзывы, поэтому `Review.text` — `HtmlField`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_content_models.py`:

```python
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.content.models import Event, GalleryPhoto

pytestmark = pytest.mark.django_db

TODAY = date(2026, 7, 1)


def make_event(title, day, show_after=False):
    return Event.objects.create(title=title, date=day, show_after_date=show_after)


def test_upcoming_includes_today_sorted():
    later = make_event("Позже", date(2026, 7, 10))
    today = make_event("Сегодня", TODAY)
    make_event("Вчера", date(2026, 6, 30))
    assert list(Event.objects.upcoming(TODAY)) == [today, later]


def test_past_visible_only_flagged_newest_first():
    older = make_event("Старое", date(2026, 5, 1), show_after=True)
    newer = make_event("Новое", date(2026, 6, 1), show_after=True)
    make_event("Скрытое", date(2026, 6, 15))
    assert list(Event.objects.past_visible(TODAY)) == [newer, older]


def test_text_color_must_be_hex():
    event = Event(title="x", date=TODAY, text_color="red; background:url(x)")
    with pytest.raises(ValidationError):
        event.full_clean()


def test_gallery_photo_file_removed_on_delete(make_image, media_root, django_capture_on_commit_callbacks):
    photo = GalleryPhoto.objects.create(image=make_image())
    path = media_root / photo.image.name
    assert path.exists()
    with django_capture_on_commit_callbacks(execute=True):
        photo.delete()
    assert not path.exists()


def test_uploaded_photo_is_downscaled(make_image, media_root):
    from PIL import Image

    photo = GalleryPhoto.objects.create(image=make_image(size=(4000, 3000)))
    with Image.open(media_root / photo.image.name) as image:
        assert image.size == (1440, 1080)
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_content_models.py`
Expected: ERROR (`No module named 'apps.content'`).

- [ ] **Step 3: Реализовать приложение**

`apps/content/__init__.py` — пустой. `apps/content/apps.py`:

```python
from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = "apps.content"
    verbose_name = "Контент"

    def ready(self):
        from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
        from apps.core.files import register_file_cleanup

        for model in (Event, Review, Partner, Employee, GalleryPhoto):
            register_file_cleanup(model)
```

`apps/content/models.py`:

```python
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.core.fields import HtmlField, image_spec, photo_field
from apps.core.models import OrderedModel, PublishedQuerySet


class EventQuerySet(models.QuerySet):
    def upcoming(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__gte=today).order_by("date", "id")

    def past_visible(self, today=None):
        today = today or timezone.localdate()
        return self.filter(date__lt=today, show_after_date=True).order_by("-date", "-id")


class Event(models.Model):
    title = models.CharField("Заголовок", max_length=128)
    date = models.DateField("Дата")
    description = HtmlField("Описание")
    link = models.URLField("Ссылка", max_length=500, blank=True, help_text="Соцсеть или сайт мероприятия.")
    text_color = models.CharField(
        "Цвет текста на фото",
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Цвет в формате #RRGGBB.")],
        help_text="Необязательно. По умолчанию белый.",
    )
    show_after_date = models.BooleanField("Показывать после даты", default=False)
    image = photo_field("Фото", "events")
    card = image_spec("image", 800, 600)

    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.title} ({self.date:%d.%m.%Y})"


class Review(OrderedModel):
    author = models.CharField("Имя", max_length=128)
    text = HtmlField("Текст")
    photo = photo_field("Фото", "reviews")
    avatar = image_spec("photo", 160, 160)
    is_published = models.BooleanField("Опубликовано", default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta(OrderedModel.Meta):
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"

    def __str__(self):
        return self.author or f"Отзыв #{self.pk}"


class Partner(OrderedModel):
    name = models.CharField("Название", max_length=128, blank=True)
    link = models.URLField("Ссылка", max_length=500, blank=True)
    logo = photo_field("Логотип", "partners", size=(600, 300), fmt=None)
    logo_small = image_spec("logo", 300, 150, crop=False)

    class Meta(OrderedModel.Meta):
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"

    def __str__(self):
        return self.name or f"Партнёр #{self.pk}"


class Employee(OrderedModel):
    name = models.CharField("Имя", max_length=128)
    position = models.CharField("Должность", max_length=128, blank=True)
    photo = photo_field("Фото", "employees")
    portrait = image_spec("photo", 400, 500)

    class Meta(OrderedModel.Meta):
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return self.name


class GalleryPhoto(OrderedModel):
    image = photo_field("Фото", "gallery", blank=False)
    caption = models.CharField("Подпись", max_length=255, blank=True)
    thumb = image_spec("image", 600, 600)

    class Meta(OrderedModel.Meta):
        verbose_name = "Фото галереи"
        verbose_name_plural = "Галерея"

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"
```

`config/settings.py`: в `INSTALLED_APPS` после `"apps.catalog"` добавить `"apps.content",`.

- [ ] **Step 4: Миграция и тесты**

```bash
DEBUG=1 uv run manage.py makemigrations content
uv run pytest
```
Expected: миграция создана; все тесты проходят.

- [ ] **Step 5: Commit**

```bash
git add apps/content config/settings.py tests
git commit -m "Модели контента: мероприятия, отзывы, партнёры, сотрудники, галерея

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Админка Unfold

**Files:**
- Create: `apps/core/admin_utils.py`, `apps/core/bulk_upload.py`, `apps/core/admin.py`, `apps/catalog/admin.py`, `apps/content/admin.py`, `templates/admin/bulk_upload.html`, `tests/test_admin.py`
- Modify: `config/settings.py` (блок `UNFOLD`)

**Interfaces:**
- Consumes: все модели (Tasks 3–5), `validate_image_upload`.
- Produces:
  - `apps.core.admin_utils.image_preview(spec_name: str, size: int = 64)` → callable для `list_display`/`readonly_fields`;
  - `apps.core.bulk_upload.MultipleImageField`, `BulkUploadForm` (поле `photos`), `append_images(model, files, **parent) -> list`;
  - `apps.core.admin.PhoneFormSet` (валидация флагов по всему набору + перенос флага без ошибки);
  - url-имя `admin:content_galleryphoto_bulk_upload`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_admin.py`:

```python
import pytest
from django.contrib import admin
from django.urls import reverse

from apps.catalog.models import Category, CategoryPhoto
from apps.content.models import GalleryPhoto
from apps.core.models import Phone, SiteSettings

pytestmark = pytest.mark.django_db


def test_every_registered_model_list_and_add_open(admin_client):
    for model, model_admin in admin.site._registry.items():
        info = (model._meta.app_label, model._meta.model_name)
        response = admin_client.get(reverse("admin:%s_%s_changelist" % info), follow=True)
        assert response.status_code == 200, model
        if model_admin.has_add_permission(response.wsgi_request):
            assert admin_client.get(reverse("admin:%s_%s_add" % info)).status_code == 200, model


def test_site_settings_changelist_redirects_to_form(admin_client):
    response = admin_client.get(reverse("admin:core_sitesettings_changelist"))
    assert response.status_code == 302
    assert response.url == reverse("admin:core_sitesettings_change", args=[1])


def _settings_post(phones):
    """Данные формы настроек сайта с inline-телефонами."""
    data = {
        "address": "село Восход",
        "map_url": "",
        "vk_url": "",
        "phones-TOTAL_FORMS": str(len(phones)),
        "phones-INITIAL_FORMS": str(sum(1 for p in phones if p.get("id"))),
        "phones-MIN_NUM_FORMS": "0",
        "phones-MAX_NUM_FORMS": "1000",
    }
    for i, phone in enumerate(phones):
        for key, value in phone.items():
            if value is True:
                data[f"phones-{i}-{key}"] = "on"
            elif value is not False and value is not None:
                data[f"phones-{i}-{key}"] = str(value)
        data[f"phones-{i}-settings"] = "1"
    return data


def test_two_whatsapp_flags_rejected(admin_client):
    SiteSettings.load()
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(
        url,
        _settings_post(
            [
                {"number": "9000000001", "order": 0, "is_whatsapp": True},
                {"number": "9000000002", "order": 1, "is_whatsapp": True},
            ]
        ),
    )
    assert response.status_code == 200
    assert "WhatsApp можно отметить только у одного номера" in response.content.decode()
    assert Phone.objects.count() == 0


def test_phone_flag_can_move_between_numbers(admin_client):
    site = SiteSettings.load()
    first = Phone.objects.create(settings=site, number="9000000001", order=0, is_whatsapp=True)
    second = Phone.objects.create(settings=site, number="9000000002", order=1)
    url = reverse("admin:core_sitesettings_change", args=[1])
    response = admin_client.post(
        url,
        _settings_post(
            [
                {"id": first.id, "number": "9000000001", "order": 0, "is_whatsapp": False},
                {"id": second.id, "number": "9000000002", "order": 1, "is_whatsapp": True},
            ]
        ),
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    second.refresh_from_db()
    first.refresh_from_db()
    assert second.is_whatsapp and not first.is_whatsapp


def _category_post(category, **extra):
    data = {
        "name": category.name,
        "slug": category.slug,
        "description": "",
        "order": "0",
        "photos-TOTAL_FORMS": "0",
        "photos-INITIAL_FORMS": "0",
        "photos-MIN_NUM_FORMS": "0",
        "photos-MAX_NUM_FORMS": "1000",
        "service_links-TOTAL_FORMS": "0",
        "service_links-INITIAL_FORMS": "0",
        "service_links-MIN_NUM_FORMS": "0",
        "service_links-MAX_NUM_FORMS": "1000",
    }
    data.update(extra)
    return data


def test_bulk_upload_appends_photos_to_category(admin_client, make_image):
    category = Category.objects.create(name="Сплавы")
    CategoryPhoto.objects.create(category=category, image=make_image(), order=7)
    url = reverse("admin:catalog_category_change", args=[category.pk])
    response = admin_client.post(
        url, _category_post(category, bulk_photos=[make_image("a.jpg"), make_image("b.png", fmt="PNG")])
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert list(category.photos.values_list("order", flat=True)) == [7, 8, 9]


def test_bulk_upload_rejects_whole_batch_on_bad_file(admin_client, make_image):
    category = Category.objects.create(name="Сплавы")
    url = reverse("admin:catalog_category_change", args=[category.pk])
    response = admin_client.post(
        url, _category_post(category, bulk_photos=[make_image("a.jpg"), make_image("c.gif", fmt="GIF")])
    )
    assert response.status_code == 200
    assert category.photos.count() == 0


def test_gallery_bulk_upload_view(admin_client, make_image):
    url = reverse("admin:content_galleryphoto_bulk_upload")
    assert admin_client.get(url).status_code == 200
    response = admin_client.post(url, {"photos": [make_image("1.jpg"), make_image("2.jpg")]})
    assert response.status_code == 302
    assert list(GalleryPhoto.objects.values_list("order", flat=True)) == [1, 2]
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_admin.py`
Expected: FAIL (модели не зарегистрированы, `NoReverseMatch`).

- [ ] **Step 3: Хелперы админки**

`apps/core/admin_utils.py`:

```python
from django.contrib import admin
from django.utils.html import format_html

from apps.core.images import safe_spec_url


def image_preview(spec_name: str, size: int = 64):
    @admin.display(description="Фото")
    def preview(obj):
        url = safe_spec_url(obj, spec_name)
        if not url:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="height:{}px;width:auto;border-radius:6px;object-fit:cover">', url, size
        )

    return preview
```

`apps/core/bulk_upload.py`:

```python
"""Загрузка нескольких фото одним полем: валидация всей пачки, добавление в конец списка."""

from django import forms
from django.db.models import Max

from apps.core.fields import validate_image_upload


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault(
            "help_text", "Можно выбрать несколько файлов: jpg, png или webp, до 20 МБ. Фото добавятся в конец списка."
        )
        super().__init__(*args, **kwargs)
        self.widget.attrs.setdefault("accept", "image/jpeg,image/png,image/webp")

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = []
        for file in files:
            file = super().clean(file, initial)
            validate_image_upload(file)
            cleaned.append(file)
        if self.required and not cleaned:
            raise forms.ValidationError("Выберите хотя бы один файл.")
        return cleaned


class BulkUploadForm(forms.Form):
    photos = MultipleImageField(label="Фото", required=True)


def append_images(model, files, **parent) -> list:
    """Создаёт записи `model(image=file, order=…, **parent)` после текущего максимума order."""
    start = (model.objects.filter(**parent).aggregate(m=Max("order"))["m"] or 0) + 1
    return [model.objects.create(image=file, order=start + i, **parent) for i, file in enumerate(files)]
```

- [ ] **Step 4: Админка core**

`apps/core/admin.py`:

```python
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet, ModelForm
from django.shortcuts import redirect
from django.urls import reverse
from unfold.admin import ModelAdmin, TabularInline

from apps.core.models import InfoPage, Phone, SiteSettings

MESSENGER_FLAGS = (("is_whatsapp", "WhatsApp"), ("is_telegram", "Telegram"))


class PhoneForm(ModelForm):
    class Meta:
        model = Phone
        fields = ["number", "is_whatsapp", "is_telegram", "order"]

    def _get_validation_exclusions(self):
        # Флаги мессенджеров проверяются по всему набору в PhoneFormSet.clean: построчная проверка
        # ограничения видит в БД старый флаг и не даёт перенести его на другой номер.
        exclusions = super()._get_validation_exclusions()
        exclusions.add("settings")
        return exclusions


class PhoneFormSet(BaseInlineFormSet):
    def _alive_forms(self):
        return [f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]

    def clean(self):
        super().clean()
        for flag, label in MESSENGER_FLAGS:
            if sum(1 for f in self._alive_forms() if f.cleaned_data.get(flag)) > 1:
                raise ValidationError(f"{label} можно отметить только у одного номера.")

    def save(self, commit=True):
        # Снимаем флаг со всех номеров, если в форме он поставлен кому-то — иначе при сохранении
        # нового владельца флага раньше старого сработает уникальное ограничение.
        for flag, _ in MESSENGER_FLAGS:
            if any(f.cleaned_data.get(flag) for f in self._alive_forms()):
                Phone.objects.filter(settings=self.instance, **{flag: True}).update(**{flag: False})
        return super().save(commit)


class PhoneInline(TabularInline):
    model = Phone
    form = PhoneForm
    formset = PhoneFormSet
    extra = 0
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["number", "is_whatsapp", "is_telegram", "order"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    inlines = [PhoneInline]
    fieldsets = (
        ("Контакты", {"classes": ["tab"], "fields": ["address", "map_url", "vk_url"]}),
        (
            "Тексты",
            {
                "classes": ["tab"],
                "fields": ["home_intro", "events_intro", "about_text", "philosophy_text", "nearby_text", "contacts_text"],
            },
        ),
        ("Карты", {"classes": ["tab"], "fields": ["contacts_map", "about_map"]}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("admin:core_sitesettings_change", args=[SiteSettings.load().pk]))


@admin.register(InfoPage)
class InfoPageAdmin(ModelAdmin):
    list_display = ["title", "is_published"]
    list_filter = ["is_published"]
    search_fields = ["title"]
    prepopulated_fields = {"slug": ("title",)}
    fields = ["title", "slug", "body", "is_published"]
```

- [ ] **Step 5: Админка каталога**

`apps/catalog/admin.py`:

```python
from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.admin_utils import image_preview
from apps.core.bulk_upload import MultipleImageField, append_images


class CategoryPhotoInline(TabularInline):
    model = CategoryPhoto
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    fields = ["preview", "image", "order"]
    readonly_fields = ["preview"]
    preview = image_preview("thumb")


class ServicePhotoInline(CategoryPhotoInline):
    model = ServicePhoto


class CategoryServiceInline(TabularInline):
    model = CategoryService
    extra = 0
    tab = True
    ordering_field = "order"
    hide_ordering_field = True
    autocomplete_fields = ["service"]
    fields = ["service", "order"]
    verbose_name_plural = "Услуги"


class ServiceCategoryInline(TabularInline):
    model = CategoryService
    extra = 0
    tab = True
    autocomplete_fields = ["category"]
    fields = ["category"]
    verbose_name_plural = "Категории"


class CategoryAdminForm(forms.ModelForm):
    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")

    class Meta:
        model = Category
        fields = "__all__"


class ServiceAdminForm(forms.ModelForm):
    bulk_photos = MultipleImageField(label="Загрузить фото пачкой")

    class Meta:
        model = Service
        fields = "__all__"


@admin.register(CategoryGroup)
class CategoryGroupAdmin(ModelAdmin):
    list_display = ["name"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    filter_horizontal = ["categories"]
    fields = ["name", "categories", "order"]


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    form = CategoryAdminForm
    list_display = ["card", "name", "is_published"]
    list_display_links = ["name"]
    list_editable = ["is_published"]
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryPhotoInline, CategoryServiceInline]
    fieldsets = (
        ("Основное", {"fields": ["name", "slug", "description", "preview_image", "preview", "is_published", "order"]}),
        ("Загрузка фото", {"fields": ["bulk_photos"]}),
    )
    readonly_fields = ["preview_image"]
    # Не называть атрибут `preview`: так называется поле модели, и форма перестала бы его редактировать.
    card = image_preview("preview_card")
    preview_image = image_preview("preview_card", size=120)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        append_images(CategoryPhoto, form.cleaned_data.get("bulk_photos") or [], category=form.instance)


@admin.register(Service)
class ServiceAdmin(ModelAdmin):
    form = ServiceAdminForm
    list_display = ["name", "price_display", "is_published", "has_page"]
    list_filter = ["is_published", "has_page", "category_links__category"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ServicePhotoInline, ServiceCategoryInline]
    fieldsets = (
        (
            "Основное",
            {
                "fields": [
                    "name",
                    "slug",
                    ("price", "price_unit"),
                    "short_description",
                    "description",
                    ("is_published", "has_page"),
                ]
            },
        ),
        ("Загрузка фото", {"fields": ["bulk_photos"]}),
    )

    @admin.display(description="Цена")
    def price_display(self, obj):
        return obj.price_display or "—"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        append_images(ServicePhoto, form.cleaned_data.get("bulk_photos") or [], service=form.instance)
```

Примечание: имена полей `order` и `bulk_photos` в POST тестов из Step 1 должны совпадать с этой формой; если Unfold отрисовывает поле `order` у changelist только как скрытое — в форме изменения категории оно остаётся обычным полем (видно в `fieldsets`).

- [ ] **Step 6: Админка контента**

`apps/content/admin.py`:

```python
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import action

from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.admin_utils import image_preview
from apps.core.bulk_upload import BulkUploadForm, append_images


class EventPeriodFilter(admin.SimpleListFilter):
    title = "Период"
    parameter_name = "period"

    def lookups(self, request, model_admin):
        return [("upcoming", "Предстоящие"), ("past", "Прошедшие")]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == "upcoming":
            return queryset.filter(date__gte=today)
        if self.value() == "past":
            return queryset.filter(date__lt=today)
        return queryset


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ["preview", "title", "date", "show_after_date"]
    list_display_links = ["title"]
    list_filter = [EventPeriodFilter, "show_after_date"]
    date_hierarchy = "date"
    search_fields = ["title"]
    fields = ["title", "date", "description", "link", "image", "text_color", "show_after_date"]
    preview = image_preview("card")


class OrderedPhotoAdmin(ModelAdmin):
    ordering = ["order", "id"]
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Review)
class ReviewAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "author", "is_published"]
    list_display_links = ["author"]
    list_filter = ["is_published"]
    fields = ["author", "text", "photo", "is_published", "order"]
    preview = image_preview("avatar")


@admin.register(Partner)
class PartnerAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "name", "link"]
    list_display_links = ["preview", "name"]
    fields = ["name", "link", "logo", "order"]
    preview = image_preview("logo_small")


@admin.register(Employee)
class EmployeeAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "name", "position"]
    list_display_links = ["name"]
    fields = ["name", "position", "photo", "order"]
    preview = image_preview("portrait")


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(OrderedPhotoAdmin):
    list_display = ["preview", "caption"]
    list_display_links = ["preview", "caption"]
    fields = ["image", "caption", "order"]
    actions_list = ["bulk_upload"]
    preview = image_preview("thumb", size=96)

    @action(description="Загрузить фото пачкой", url_path="bulk-upload")
    def bulk_upload(self, request):
        form = BulkUploadForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            created = append_images(GalleryPhoto, form.cleaned_data["photos"])
            messages.success(request, f"Загружено фото: {len(created)}.")
            return redirect("admin:content_galleryphoto_changelist")
        context = {
            **self.admin_site.each_context(request),
            "title": "Загрузить фото в галерею",
            "opts": self.model._meta,
            "form": form,
        }
        return render(request, "admin/bulk_upload.html", context)
```

`templates/admin/bulk_upload.html`:

```html
{% extends "admin/base_site.html" %}

{% block content %}
<form method="post" enctype="multipart/form-data" class="flex max-w-xl flex-col gap-4">
  {% csrf_token %}
  {% if form.non_field_errors %}<div class="text-red-600">{{ form.non_field_errors }}</div>{% endif %}
  <label class="font-semibold" for="{{ form.photos.id_for_label }}">{{ form.photos.label }}</label>
  {{ form.photos }}
  <p class="text-sm opacity-70">{{ form.photos.help_text }}</p>
  {% if form.photos.errors %}<div class="text-red-600">{{ form.photos.errors }}</div>{% endif %}
  <div>
    <button type="submit" class="bg-primary-600 rounded-md px-4 py-2 font-semibold text-white">Загрузить</button>
  </div>
</form>
{% endblock %}
```

- [ ] **Step 7: Блок UNFOLD в настройках**

В `config/settings.py` в начало добавить `from django.urls import reverse_lazy`, в конец файла:

```python
UNFOLD = {
    "SITE_TITLE": "Т-Парк",
    "SITE_HEADER": "Т-Парк",
    "SITE_URL": "/",
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Каталог",
                "items": [
                    {"title": "Группы категорий", "icon": "workspaces", "link": reverse_lazy("admin:catalog_categorygroup_changelist")},
                    {"title": "Категории", "icon": "category", "link": reverse_lazy("admin:catalog_category_changelist")},
                    {"title": "Услуги", "icon": "inventory_2", "link": reverse_lazy("admin:catalog_service_changelist")},
                ],
            },
            {
                "title": "Контент",
                "separator": True,
                "items": [
                    {"title": "Мероприятия", "icon": "event", "link": reverse_lazy("admin:content_event_changelist")},
                    {"title": "Отзывы", "icon": "reviews", "link": reverse_lazy("admin:content_review_changelist")},
                    {"title": "Галерея", "icon": "photo_library", "link": reverse_lazy("admin:content_galleryphoto_changelist")},
                    {"title": "Партнёры", "icon": "handshake", "link": reverse_lazy("admin:content_partner_changelist")},
                    {"title": "Сотрудники", "icon": "badge", "link": reverse_lazy("admin:content_employee_changelist")},
                ],
            },
            {
                "title": "Сайт",
                "separator": True,
                "items": [
                    {"title": "Настройки сайта", "icon": "settings", "link": reverse_lazy("admin:core_sitesettings_changelist")},
                    {"title": "Инфо-страницы", "icon": "description", "link": reverse_lazy("admin:core_infopage_changelist")},
                ],
            },
            {
                "title": "Доступ",
                "separator": True,
                "items": [
                    {"title": "Пользователи", "icon": "person", "link": reverse_lazy("admin:auth_user_changelist")},
                    {"title": "Группы", "icon": "group", "link": reverse_lazy("admin:auth_group_changelist")},
                ],
            },
        ],
    },
}
```

Пользователи и группы Django должны отображаться в стиле Unfold: в `apps/core/admin.py` дописать перерегистрацию:

```python
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
```

- [ ] **Step 8: Запустить тесты**

Run: `uv run pytest tests/test_admin.py`
Expected: 7 passed. Если `test_phone_flag_can_move_between_numbers` падает с ошибкой ограничения на форме — проверить, что `PhoneForm._get_validation_exclusions` действительно исключает `settings` (в Django 6.1 это множество; если вернулся список — преобразовать в `set`).

- [ ] **Step 9: Ручная проверка админки**

```bash
DEBUG=1 uv run manage.py migrate
DEBUG=1 uv run manage.py createsuperuser
DEBUG=1 uv run manage.py runserver
```
Открыть `http://127.0.0.1:8000/admin/`: боковое меню из 4 групп; в категории — вкладки «Фото» и «Услуги», перетаскивание строк; галерея — кнопка «Загрузить фото пачкой»; редактор текста (prose-editor) в полях описаний.

- [ ] **Step 10: Commit**

```bash
git add apps config/settings.py templates tests
git commit -m "Админка на Unfold: меню, вкладки, сортировка, загрузка фото пачкой, настройки-синглтон

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Каркас фронта — Tailwind, base.html, контекст, главная

**Files:**
- Create: `tailwind/source.css`, `static/img/logo.png`, `static/js/site.js`, `static/vendor/*` (Alpine, Swiper, GLightbox), `templates/icons/*.svg`, `templates/base.html`, `templates/partials/{header,footer,contact_button,contact_links,nav_links}.html`, `templates/catalog/home.html`, `templates/catalog/partials/category_card.html`, `templates/404.html`, `templates/500.html`, `apps/core/context_processors.py`, `apps/core/seo.py`, `apps/core/templatetags/__init__.py`, `apps/core/templatetags/site_tags.py`, `apps/catalog/context_processors.py`, `apps/catalog/views.py`, `apps/catalog/urls.py`, `tests/test_pages_home.py`
- Modify: `config/settings.py` (контекст-процессоры, Tailwind), `config/urls.py`

**Interfaces:**
- Consumes: `SiteSettings.load()`, `Phone`, `CategoryGroup`, `Category.objects.published()`, `safe_spec_url`.
- Produces:
  - контекст во всех шаблонах: `site`, `phones`, `whatsapp_phone`, `telegram_phone`, `default_description`, `menu_groups` (список `CategoryGroup` с атрибутом `published_categories`);
  - `apps.core.seo.plaintext(html, limit=160) -> str`, `make_seo(title="", description_html="", image_url="") -> dict` (ключи `title`, `description`, `image`);
  - фильтры шаблонов `{% load site_tags %}`: `spec_url` (`obj|spec_url:"name"`), `plaintext`;
  - url-имя `catalog:home` (`/`); блок `content` в `base.html`, контекстная переменная `seo`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_pages_home.py`:

```python
import pytest

from apps.catalog.models import Category, CategoryGroup
from apps.core.models import Phone, SiteSettings
from apps.core.seo import plaintext

pytestmark = pytest.mark.django_db


def test_home_on_empty_db(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Скоро здесь появятся наши услуги" in response.content.decode()


def test_home_shows_only_published_categories(client):
    group = CategoryGroup.objects.create(name="Активный отдых")
    visible = Category.objects.create(name="Байдарки", is_published=True)
    hidden = Category.objects.create(name="Скрытая", is_published=False)
    group.categories.add(visible, hidden)
    CategoryGroup.objects.create(name="Пустая группа")
    html = client.get("/").content.decode()
    assert "Активный отдых" in html and "Байдарки" in html
    assert "Скрытая" not in html
    assert "Пустая группа" not in html


def test_contacts_in_footer_and_contact_button(client):
    site = SiteSettings.load()
    site.address = "село Восход"
    site.save()
    Phone.objects.create(settings=site, number="9029856594", is_whatsapp=True)
    html = client.get("/").content.decode()
    assert "село Восход" in html
    assert "tel:+79029856594" in html
    assert "https://wa.me/79029856594" in html
    assert "t.me/+7" not in html  # Telegram не отмечен ни у одного номера


def test_home_survives_missing_preview_file(client, make_image, media_root):
    group = CategoryGroup.objects.create(name="Группа")
    category = Category.objects.create(name="Без файла", is_published=True, preview=make_image())
    group.categories.add(category)
    (media_root / category.preview.name).unlink()
    response = client.get("/")
    assert response.status_code == 200
    assert "Без файла" in response.content.decode()


def test_404_page(client):
    response = client.get("/net-takoy-stranicy/")
    assert response.status_code == 404
    assert "Страница не найдена" in response.content.decode()


def test_plaintext_strips_and_truncates():
    assert plaintext("<p>Привет,&nbsp;<b>мир</b></p>") == "Привет, мир"
    long = "<p>" + "слово " * 100 + "</p>"
    result = plaintext(long)
    assert len(result) <= 160 and result.endswith("…")
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_pages_home.py`
Expected: FAIL / ERROR.

- [ ] **Step 3: Статика — логотип, vendored JS, иконки**

```bash
mkdir -p static/img static/js static/vendor templates/icons tailwind
cp old_version/app/static/logo.png static/img/logo.png
curl -fsSL -o static/vendor/alpine.min.js https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js
curl -fsSL -o static/vendor/swiper-bundle.min.js https://cdn.jsdelivr.net/npm/swiper@12/swiper-bundle.min.js
curl -fsSL -o static/vendor/swiper-bundle.min.css https://cdn.jsdelivr.net/npm/swiper@12/swiper-bundle.min.css
curl -fsSL -o static/vendor/glightbox.min.js https://cdn.jsdelivr.net/npm/glightbox@3/dist/js/glightbox.min.js
curl -fsSL -o static/vendor/glightbox.min.css https://cdn.jsdelivr.net/npm/glightbox@3/dist/css/glightbox.min.css
for i in phone map-pin menu x chevron-down chevron-right external-link; do
  curl -fsSL -o templates/icons/$i.svg https://cdn.jsdelivr.net/npm/lucide-static@latest/icons/$i.svg
done
for i in whatsapp telegram vk; do
  curl -fsSL -o templates/icons/$i.svg https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/$i.svg
done
head -c 300 static/vendor/alpine.min.js && ls -la static/vendor templates/icons
```
Expected: все файлы непустые. Если `swiper@12` недоступен — взять `swiper@11` (API, используемый в `site.js`, одинаков). Открыть `old_version/app/static/logo.png` и убедиться, что это основной логотип (если основной — `logo_2.png`, скопировать его).

У скачанных SVG из simple-icons нет `fill`; иконки красятся через `currentColor` в CSS (Step 4).

- [ ] **Step 4: Tailwind и JS**

`tailwind/source.css`:

```css
@import "tailwindcss";
@source "../templates";
@source "../apps";

@theme {
  --font-sans: "Montserrat", ui-sans-serif, system-ui, sans-serif;
  --color-brand-50: #fff8eb;
  --color-brand-100: #ffedc6;
  --color-brand-300: #ffcd5c;
  --color-brand-500: #ffa300;
  --color-brand-600: #e08600;
  --color-brand-700: #b96202;
  --color-ink: #1c1919;
  --color-tint: #eef2fc;
}

[x-cloak] { display: none !important; }

.icon { display: inline-flex; flex-shrink: 0; }
.icon svg { width: 100%; height: 100%; }
.icon-fill svg { fill: currentColor; }

.btn {
  @apply inline-flex items-center justify-center gap-2 rounded-full px-5 py-3 text-sm font-semibold transition;
}
.btn-primary { @apply bg-brand-500 text-ink hover:bg-brand-600; }
.btn-ghost { @apply bg-white text-ink ring-1 ring-ink/10 hover:ring-brand-500; }

.rich-text { @apply leading-relaxed text-ink/85; }
.rich-text > * + * { @apply mt-3; }
.rich-text h2 { @apply mt-6 text-xl font-bold text-ink; }
.rich-text h3 { @apply mt-4 text-lg font-semibold text-ink; }
.rich-text a { @apply text-brand-700 underline underline-offset-2 hover:text-brand-600; }
.rich-text ul { @apply list-disc pl-6; }
.rich-text ol { @apply list-decimal pl-6; }
.rich-text strong { @apply font-semibold text-ink; }
```

`static/js/site.js`:

```js
document.addEventListener("DOMContentLoaded", () => {
  const nav = (el) => ({
    nextEl: el.querySelector(".swiper-button-next"),
    prevEl: el.querySelector(".swiper-button-prev"),
  });

  document.querySelectorAll(".js-slider").forEach((el) => {
    const count = el.querySelectorAll(".swiper-slide").length;
    new Swiper(el, {
      loop: count >= 3,
      spaceBetween: 16,
      pagination: { el: el.querySelector(".swiper-pagination"), clickable: true },
      navigation: nav(el),
    });
  });

  document.querySelectorAll(".js-carousel").forEach((el) => {
    const count = el.querySelectorAll(".swiper-slide").length;
    new Swiper(el, {
      loop: count >= 6,
      spaceBetween: 24,
      slidesPerView: 1.1,
      breakpoints: { 768: { slidesPerView: 2.1 }, 1024: { slidesPerView: 3 } },
      navigation: nav(el),
    });
  });

  if (window.GLightbox && document.querySelector(".glightbox")) {
    GLightbox({ selector: ".glightbox" });
  }
});
```

В `config/settings.py` добавить:

```python
TAILWIND_CLI_SRC_CSS = "tailwind/source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"
```

и в `TEMPLATES[0]["OPTIONS"]["context_processors"]` добавить `"apps.core.context_processors.site"` и `"apps.catalog.context_processors.menu"`.

Собрать CSS: `DEBUG=1 uv run manage.py tailwind build` → Expected: создан `static/css/tailwind.css` (бинарник скачается в `.django_tailwind_cli/` при первом запуске).

- [ ] **Step 5: SEO-хелпер, теги шаблонов, контекст-процессоры**

`apps/core/seo.py`:

```python
import html
import re

from django.utils.html import strip_tags


def plaintext(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", html.unescape(strip_tags(value or ""))).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def make_seo(title: str = "", description_html: str = "", image_url: str = "") -> dict:
    return {"title": title, "description": plaintext(description_html), "image": image_url}
```

`apps/core/templatetags/__init__.py` — пустой. `apps/core/templatetags/site_tags.py`:

```python
from django import template

from apps.core.images import safe_spec_url
from apps.core.seo import plaintext as _plaintext

register = template.Library()


@register.filter
def spec_url(obj, spec_name: str) -> str:
    return safe_spec_url(obj, spec_name)


@register.filter
def plaintext(value, limit: int = 160) -> str:
    return _plaintext(value, int(limit))
```

`apps/core/context_processors.py`:

```python
from apps.core.models import SiteSettings
from apps.core.seo import plaintext


def site(request):
    settings_obj = SiteSettings.load()
    phones = list(settings_obj.phones.all())
    return {
        "site": settings_obj,
        "phones": phones,
        "whatsapp_phone": next((p for p in phones if p.is_whatsapp), None),
        "telegram_phone": next((p for p in phones if p.is_telegram), None),
        "default_description": plaintext(settings_obj.home_intro) or "Т-Парк — активный отдых в Калужской области.",
    }
```

`apps/catalog/context_processors.py`:

```python
from django.db.models import Prefetch

from apps.catalog.models import Category, CategoryGroup


def menu(request):
    groups = CategoryGroup.objects.prefetch_related(
        Prefetch(
            "categories",
            queryset=Category.objects.published().order_by("order", "id"),
            to_attr="published_categories",
        )
    )
    return {"menu_groups": [g for g in groups if g.published_categories]}
```

- [ ] **Step 6: Шаблоны каркаса**

`templates/base.html`:

```html
{% load static tailwind_cli %}<!doctype html>
<html lang="ru" class="scroll-smooth">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% if seo.title %}{{ seo.title }} — Т-Парк{% else %}Т-Парк — активный отдых{% endif %}</title>
  <meta name="description" content="{% firstof seo.description default_description %}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Т-Парк">
  <meta property="og:title" content="{% firstof seo.title 'Т-Парк' %}">
  <meta property="og:description" content="{% firstof seo.description default_description %}">
  {% if seo.image %}<meta property="og:image" content="{{ seo.image }}">{% endif %}
  <link rel="icon" href="{% static 'img/logo.png' %}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap&subset=cyrillic" rel="stylesheet">
  <link rel="stylesheet" href="{% static 'vendor/swiper-bundle.min.css' %}">
  <link rel="stylesheet" href="{% static 'vendor/glightbox.min.css' %}">
  {% tailwind_css %}
  <script defer src="{% static 'vendor/alpine.min.js' %}"></script>
</head>
<body class="flex min-h-screen flex-col bg-white font-sans text-ink antialiased">
  {% include "partials/header.html" %}
  <main class="flex-1">{% block content %}{% endblock %}</main>
  {% include "partials/footer.html" %}
  {% include "partials/contact_button.html" %}
  <script src="{% static 'vendor/swiper-bundle.min.js' %}"></script>
  <script src="{% static 'vendor/glightbox.min.js' %}"></script>
  <script src="{% static 'js/site.js' %}"></script>
</body>
</html>
```

Шрифты Google Fonts — единственный внешний ресурс; при проблемах со скоростью загрузки шрифт можно позже положить в `static/fonts/`.

`templates/partials/nav_links.html` (заполняется в Task 8; сейчас — пустой файл):

```html
```

`templates/partials/header.html`:

```html
{% load static %}
<header x-data="{ open: false, services: false }" class="sticky top-0 z-40 border-b border-ink/5 bg-white/90 backdrop-blur">
  <div class="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3">
    <a href="{% url 'catalog:home' %}" class="flex items-center gap-2" aria-label="Т-Парк, на главную">
      <img src="{% static 'img/logo.png' %}" alt="Т-Парк" class="h-10 w-auto">
    </a>

    <nav class="hidden items-center gap-6 text-sm font-medium md:flex">
      {% if menu_groups %}
      <div class="relative" @mouseleave="services = false">
        <button type="button" class="flex items-center gap-1 hover:text-brand-600"
                @click="services = !services" @mouseenter="services = true" :aria-expanded="services">
          Услуги <span class="icon h-4 w-4">{% include "icons/chevron-down.svg" %}</span>
        </button>
        <div x-show="services" x-transition x-cloak
             class="absolute left-0 top-full grid w-[40rem] grid-cols-2 gap-6 rounded-2xl bg-white p-6 shadow-xl ring-1 ring-ink/5">
          {% for group in menu_groups %}
          <div>
            <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/50">{{ group.name }}</p>
            <ul class="space-y-1">
              {% for category in group.published_categories %}
              <li><a class="hover:text-brand-600" href="{{ category.get_absolute_url }}">{{ category.name }}</a></li>
              {% endfor %}
            </ul>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endif %}
      {% include "partials/nav_links.html" with link_class="hover:text-brand-600" %}
    </nav>

    <button type="button" class="icon h-8 w-8 md:hidden" @click="open = !open" :aria-expanded="open" aria-label="Меню">
      <span x-show="!open">{% include "icons/menu.svg" %}</span>
      <span x-show="open" x-cloak>{% include "icons/x.svg" %}</span>
    </button>
  </div>

  <div x-show="open" x-transition x-cloak class="border-t border-ink/5 bg-white md:hidden">
    <nav class="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6">
      {% for group in menu_groups %}
      <div>
        <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/50">{{ group.name }}</p>
        <ul class="space-y-2">
          {% for category in group.published_categories %}
          <li><a class="text-lg" href="{{ category.get_absolute_url }}">{{ category.name }}</a></li>
          {% endfor %}
        </ul>
      </div>
      {% endfor %}
      <div class="flex flex-col gap-3 border-t border-ink/5 pt-4 text-lg font-medium">
        {% include "partials/nav_links.html" with link_class="" %}
      </div>
    </nav>
  </div>
</header>
```

`templates/partials/contact_links.html`:

```html
{% if phones %}
<a href="{{ phones.0.tel_url }}" class="btn btn-primary"><span class="icon h-5 w-5">{% include "icons/phone.svg" %}</span>{{ phones.0.display }}</a>
{% endif %}
{% if whatsapp_phone %}
<a href="{{ whatsapp_phone.whatsapp_url }}" class="btn btn-ghost" target="_blank" rel="noopener"><span class="icon icon-fill h-5 w-5 text-[#25D366]">{% include "icons/whatsapp.svg" %}</span>WhatsApp</a>
{% endif %}
{% if telegram_phone %}
<a href="{{ telegram_phone.telegram_url }}" class="btn btn-ghost" target="_blank" rel="noopener"><span class="icon icon-fill h-5 w-5 text-[#26A5E4]">{% include "icons/telegram.svg" %}</span>Telegram</a>
{% endif %}
```

`templates/partials/footer.html`:

```html
<footer class="mt-16 bg-ink text-white/80">
  <div class="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-3">
    <div>
      <p class="text-lg font-bold text-white">Т-Парк</p>
      {% if site.address %}
      <a href="{% firstof site.map_url '#' %}" class="mt-3 flex gap-2 hover:text-brand-300" {% if site.map_url %}target="_blank" rel="noopener"{% endif %}>
        <span class="icon mt-0.5 h-5 w-5">{% include "icons/map-pin.svg" %}</span>{{ site.address }}
      </a>
      {% endif %}
    </div>
    {% if phones %}
    <ul class="space-y-2">
      {% for phone in phones %}
      <li><a href="{{ phone.tel_url }}" class="flex items-center gap-2 hover:text-brand-300"><span class="icon h-4 w-4">{% include "icons/phone.svg" %}</span>{{ phone.display }}</a></li>
      {% endfor %}
    </ul>
    {% endif %}
    <div class="flex gap-4">
      {% if whatsapp_phone %}<a href="{{ whatsapp_phone.whatsapp_url }}" class="icon icon-fill h-8 w-8 hover:text-brand-300" target="_blank" rel="noopener" aria-label="WhatsApp">{% include "icons/whatsapp.svg" %}</a>{% endif %}
      {% if telegram_phone %}<a href="{{ telegram_phone.telegram_url }}" class="icon icon-fill h-8 w-8 hover:text-brand-300" target="_blank" rel="noopener" aria-label="Telegram">{% include "icons/telegram.svg" %}</a>{% endif %}
      {% if site.vk_url %}<a href="{{ site.vk_url }}" class="icon icon-fill h-8 w-8 hover:text-brand-300" target="_blank" rel="noopener" aria-label="VK">{% include "icons/vk.svg" %}</a>{% endif %}
    </div>
  </div>
</footer>
```

`templates/partials/contact_button.html`:

```html
{% if phones %}
<div x-data="{ open: false }" class="fixed bottom-4 right-4 z-50 md:hidden">
  <div x-show="open" x-transition x-cloak class="mb-3 flex flex-col items-end gap-2">
    {% include "partials/contact_links.html" %}
  </div>
  <button type="button" @click="open = !open" :aria-expanded="open" class="btn btn-primary shadow-lg">Связаться</button>
</div>
{% endif %}
```

`templates/catalog/partials/category_card.html`:

```html
{% load site_tags %}
<a href="{{ category.get_absolute_url }}" class="group block overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-ink/5 transition hover:-translate-y-1 hover:shadow-lg">
  <div class="aspect-[3/2] overflow-hidden bg-tint">
    {% with url=category|spec_url:"preview_card" %}{% if url %}
    <img src="{{ url }}" alt="{{ category.name }}" loading="lazy" class="h-full w-full object-cover transition duration-500 group-hover:scale-105">
    {% endif %}{% endwith %}
  </div>
  <div class="p-5"><h3 class="text-lg font-semibold group-hover:text-brand-600">{{ category.name }}</h3></div>
</a>
```

Важно: `spec_url` для пустого поля вернёт пустую строку — imagekit на пустом исходнике бросает исключение, которое ловит `safe_spec_url`.

`templates/catalog/home.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="bg-tint">
  <div class="mx-auto max-w-6xl px-4 py-14 md:py-20">
    <h1 class="text-4xl font-bold md:text-6xl">Т-Парк</h1>
    {% if site.home_intro %}<div class="rich-text mt-5 max-w-3xl text-lg">{{ site.home_intro|safe }}</div>{% endif %}
    <div class="mt-8 flex flex-wrap gap-3">{% include "partials/contact_links.html" %}</div>
  </div>
</section>

{% for group in menu_groups %}
<section class="mx-auto max-w-6xl px-4 py-10">
  <h2 class="mb-6 text-2xl font-bold md:text-3xl">{{ group.name }}</h2>
  <div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
    {% for category in group.published_categories %}{% include "catalog/partials/category_card.html" %}{% endfor %}
  </div>
</section>
{% empty %}
<p class="mx-auto max-w-6xl px-4 py-16 text-ink/60">Скоро здесь появятся наши услуги.</p>
{% endfor %}
{% endblock %}
```

`templates/404.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="mx-auto max-w-3xl px-4 py-24 text-center">
  <p class="text-7xl font-bold text-brand-500">404</p>
  <h1 class="mt-4 text-2xl font-bold">Страница не найдена</h1>
  <p class="mt-2 text-ink/60">Возможно, она переехала. Начните с главной.</p>
  <a href="{% url 'catalog:home' %}" class="btn btn-primary mt-8">На главную</a>
</div>
{% endblock %}
```

`templates/500.html` (без наследования: рендерится без контекста и без обращения к БД):

```html
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Ошибка — Т-Парк</title></head>
<body style="font-family:Arial,sans-serif;text-align:center;padding:80px 16px;color:#1c1919">
  <p style="font-size:64px;font-weight:700;color:#ffa300;margin:0">500</p>
  <h1>Что-то пошло не так</h1>
  <p>Мы уже разбираемся. Попробуйте обновить страницу чуть позже.</p>
  <a href="/" style="color:#b96202">На главную</a>
</body>
</html>
```

- [ ] **Step 7: View и URL главной**

`apps/catalog/views.py`:

```python
from django.shortcuts import render


def home(request):
    return render(request, "catalog/home.html")
```

`apps/catalog/urls.py`:

```python
from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
]
```

`config/urls.py` — добавить `include` и строку `path("", include("apps.catalog.urls")),` после `healthz`.

- [ ] **Step 8: Запустить тесты**

```bash
DEBUG=1 uv run manage.py tailwind build
uv run pytest
```
Expected: все тесты проходят. `{% tailwind_css %}` в тестах ссылается на `css/tailwind.css` — файл собран шагом выше; при `StaticFilesStorage` манифест не нужен.

- [ ] **Step 9: Визуальная проверка**

`DEBUG=1 uv run manage.py tailwind runserver`, открыть `http://127.0.0.1:8000/` на ширине 375 px и 1280 px: шапка, бургер, кнопка «Связаться» (видна только на мобильном), подвал. Завести в админке группу, категорию с превью и телефоны — проверить карточки.

- [ ] **Step 10: Commit**

```bash
git add tailwind static templates apps config tests
git commit -m "Каркас фронта: Tailwind, шапка, подвал, кнопка связи, главная, 404/500

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Публичные страницы

**Files:**
- Create: `templates/catalog/{category,service}.html`, `templates/catalog/partials/{slider,service_row}.html`, `templates/content/{events,about,reviews,gallery,contacts}.html`, `templates/core/info.html`, `apps/content/views.py`, `apps/content/urls.py`, `apps/core/urls.py`, `tests/test_pages.py`
- Modify: `apps/catalog/views.py`, `apps/catalog/urls.py`, `apps/core/views.py`, `config/urls.py`, `templates/partials/nav_links.html`

**Interfaces:**
- Consumes: модели, `make_seo`, `safe_spec_url`, контекст из Task 7.
- Produces: url-имена `catalog:category(slug)`, `catalog:service(slug)`, `content:events`, `content:about`, `content:reviews`, `content:gallery`, `content:contacts`, `core:info(slug)`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_pages.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Category, CategoryPhoto, CategoryService, Service
from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db

STATIC_PAGES = ["/events/", "/about/", "/reviews/", "/gallery/", "/contacts/"]


@pytest.mark.parametrize("url", STATIC_PAGES)
def test_static_pages_on_empty_db(client, url):
    assert client.get(url).status_code == 200


@pytest.fixture
def category(make_image):
    category = Category.objects.create(name="Сплавы", description="<p>Описание сплавов</p>", is_published=True)
    CategoryPhoto.objects.create(category=category, image=make_image(), order=0)
    return category


def test_category_page_lists_services(client, category):
    with_page = Service.objects.create(name="Однодневный сплав", price="2000", price_unit="человек", has_page=True)
    inline = Service.objects.create(name="Аренда байдарки", price="500", price_unit="час", short_description="<p>Весло включено</p>")
    hidden = Service.objects.create(name="Скрытая услуга", is_published=False)
    for order, service in enumerate([with_page, inline, hidden]):
        CategoryService.objects.create(category=category, service=service, order=order)
    html = client.get(category.get_absolute_url()).content.decode()
    assert "Описание сплавов" in html
    assert "2000 руб / человек" in html and with_page.get_absolute_url() in html
    assert "Весло включено" in html
    assert "Скрытая услуга" not in html
    assert "swiper-slide" in html


def test_unpublished_category_is_404(client):
    category = Category.objects.create(name="Черновик", is_published=False)
    assert client.get(category.get_absolute_url()).status_code == 404


def test_service_page(client):
    service = Service.objects.create(name="Сплав", description="<p>Полное описание</p>", price="2000", has_page=True)
    response = client.get(service.get_absolute_url())
    assert response.status_code == 200
    assert "Полное описание" in response.content.decode()


@pytest.mark.parametrize("kwargs", [{"has_page": False}, {"has_page": True, "is_published": False}])
def test_service_page_404(client, kwargs):
    service = Service.objects.create(name="Сплав", **kwargs)
    assert client.get(service.get_absolute_url()).status_code == 404


def test_events_page_order(client):
    today = timezone.localdate()
    Event.objects.create(title="Будущее", date=today + timedelta(days=5))
    Event.objects.create(title="Сегодня", date=today)
    Event.objects.create(title="Прошлое видимое", date=today - timedelta(days=5), show_after_date=True)
    Event.objects.create(title="Прошлое скрытое", date=today - timedelta(days=3))
    html = client.get("/events/").content.decode()
    assert html.index("Сегодня") < html.index("Будущее") < html.index("Прошлое видимое")
    assert "Прошлое скрытое" not in html


def test_events_page_placeholder(client):
    assert "Скоро анонсируем" in client.get("/events/").content.decode()


def test_about_page(client, make_image):
    Employee.objects.create(name="Иван", position="Инструктор")
    Partner.objects.create(name="Партнёр", link="https://example.com", logo=make_image())
    html = client.get("/about/").content.decode()
    assert "Иван" in html and "Инструктор" in html and "https://example.com" in html


def test_about_page_hides_empty_employees(client):
    assert "Команда" not in client.get("/about/").content.decode()


def test_reviews_manual_order_and_published(client):
    Review.objects.create(author="Второй", text="<p>b</p>", order=2)
    Review.objects.create(author="Первый", text="<p>a</p>", order=1)
    Review.objects.create(author="Скрытый", text="<p>c</p>", is_published=False)
    html = client.get("/reviews/").content.decode()
    assert html.index("Первый") < html.index("Второй")
    assert "Скрытый" not in html


def test_gallery_page(client, make_image):
    GalleryPhoto.objects.create(image=make_image(), caption="Закат")
    html = client.get("/gallery/").content.decode()
    assert "glightbox" in html and "Закат" in html


def test_info_page(client):
    page = InfoPage.objects.create(title="Правила", body="<p>Текст правил</p>")
    assert "Текст правил" in client.get(page.get_absolute_url()).content.decode()
    hidden = InfoPage.objects.create(title="Черновик", is_published=False)
    assert client.get(hidden.get_absolute_url()).status_code == 404


def test_nav_has_all_sections(client):
    html = client.get("/").content.decode()
    for url in STATIC_PAGES:
        assert f'href="{url}"' in html
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_pages.py`
Expected: FAIL (`NoReverseMatch`, 404).

- [ ] **Step 3: Views и URL**

`apps/catalog/views.py`:

```python
from django.shortcuts import get_object_or_404, render

from apps.catalog.models import Category, Service
from apps.core.images import safe_spec_url
from apps.core.seo import make_seo


def home(request):
    return render(request, "catalog/home.html")


def _absolute(request, url: str) -> str:
    return request.build_absolute_uri(url) if url else ""


def category_detail(request, slug):
    category = get_object_or_404(Category.objects.published(), slug=slug)
    photos = list(category.photos.all())
    image = safe_spec_url(category, "preview_card") or (safe_spec_url(photos[0], "slide") if photos else "")
    return render(
        request,
        "catalog/category.html",
        {
            "category": category,
            "photos": photos,
            "services": category.published_services(),
            "seo": make_seo(category.name, category.description, _absolute(request, image)),
        },
    )


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.published().filter(has_page=True), slug=slug)
    photos = list(service.photos.all())
    link = (
        service.category_links.filter(category__is_published=True)
        .select_related("category")
        .order_by("category__order", "category__id")
        .first()
    )
    image = safe_spec_url(photos[0], "slide") if photos else ""
    return render(
        request,
        "catalog/service.html",
        {
            "service": service,
            "photos": photos,
            "category": link.category if link else None,
            "seo": make_seo(service.name, service.short_description or service.description, _absolute(request, image)),
        },
    )
```

`apps/catalog/urls.py`:

```python
from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("", views.home, name="home"),
    path("category/<slug:slug>/", views.category_detail, name="category"),
    path("service/<slug:slug>/", views.service_detail, name="service"),
]
```

`apps/content/views.py`:

```python
from django.shortcuts import render
from django.utils import timezone

from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.images import safe_spec_url
from apps.core.models import SiteSettings
from apps.core.seo import make_seo


def events(request):
    today = timezone.localdate()
    upcoming = list(Event.objects.upcoming(today))
    past = list(Event.objects.past_visible(today))
    nearest = upcoming[0] if upcoming else None
    hero = safe_spec_url(nearest, "card") if nearest else ""
    return render(
        request,
        "content/events.html",
        {
            "events": upcoming + past,
            "nearest": nearest,
            "hero_image": hero,
            "seo": make_seo("Мероприятия", SiteSettings.load().events_intro),
        },
    )


def about(request):
    return render(
        request,
        "content/about.html",
        {
            "employees": list(Employee.objects.all()),
            "partners": list(Partner.objects.all()),
            "seo": make_seo("О нас", SiteSettings.load().about_text),
        },
    )


def reviews(request):
    return render(
        request, "content/reviews.html", {"reviews": Review.objects.published(), "seo": make_seo("Отзывы")}
    )


def gallery(request):
    return render(
        request, "content/gallery.html", {"photos": GalleryPhoto.objects.all(), "seo": make_seo("Галерея")}
    )


def contacts(request):
    return render(
        request, "content/contacts.html", {"seo": make_seo("Контакты", SiteSettings.load().contacts_text)}
    )
```

`apps/content/urls.py`:

```python
from django.urls import path

from apps.content import views

app_name = "content"

urlpatterns = [
    path("events/", views.events, name="events"),
    path("about/", views.about, name="about"),
    path("reviews/", views.reviews, name="reviews"),
    path("gallery/", views.gallery, name="gallery"),
    path("contacts/", views.contacts, name="contacts"),
]
```

`apps/core/views.py` — дописать:

```python
from django.shortcuts import get_object_or_404, render

from apps.core.models import InfoPage
from apps.core.seo import make_seo


def info_page(request, slug):
    page = get_object_or_404(InfoPage.objects.published(), slug=slug)
    return render(request, "core/info.html", {"page": page, "seo": make_seo(page.title, page.body)})
```

`apps/core/urls.py`:

```python
from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("info/<slug:slug>/", views.info_page, name="info"),
]
```

`config/urls.py` — `urlpatterns` после `healthz`:

```python
    path("", include("apps.catalog.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.core.urls")),
```

- [ ] **Step 4: Навигация**

`templates/partials/nav_links.html`:

```html
<a href="{% url 'content:events' %}" class="{{ link_class }}">Мероприятия</a>
<a href="{% url 'content:about' %}" class="{{ link_class }}">О нас</a>
<a href="{% url 'content:reviews' %}" class="{{ link_class }}">Отзывы</a>
<a href="{% url 'content:gallery' %}" class="{{ link_class }}">Галерея</a>
<a href="{% url 'content:contacts' %}" class="{{ link_class }}">Контакты</a>
```

- [ ] **Step 5: Шаблоны каталога**

`templates/catalog/partials/slider.html`:

```html
{% load site_tags %}
{% if photos %}
<div class="swiper js-slider overflow-hidden rounded-2xl bg-tint">
  <div class="swiper-wrapper">
    {% for photo in photos %}{% with url=photo|spec_url:"slide" %}{% if url %}
    <div class="swiper-slide">
      <img src="{{ url }}" alt="{{ alt }}" class="aspect-[16/9] w-full object-cover" {% if not forloop.first %}loading="lazy"{% endif %}>
    </div>
    {% endif %}{% endwith %}{% endfor %}
  </div>
  <div class="swiper-pagination"></div>
  <div class="swiper-button-prev !text-white"></div>
  <div class="swiper-button-next !text-white"></div>
</div>
{% endif %}
```

`templates/catalog/partials/service_row.html`:

```html
{% if service.has_page %}
<a href="{{ service.get_absolute_url }}" class="flex items-center justify-between gap-4 px-5 py-4 hover:bg-brand-50">
  <span class="font-medium">{{ service.name }}</span>
  <span class="flex shrink-0 items-center gap-2 text-ink/70">{{ service.price_display }}<span class="icon h-4 w-4">{% include "icons/chevron-right.svg" %}</span></span>
</a>
{% elif service.short_description %}
<div x-data="{ open: false }">
  <button type="button" @click="open = !open" :aria-expanded="open" class="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-brand-50">
    <span class="font-medium">{{ service.name }}</span>
    <span class="flex shrink-0 items-center gap-2 text-ink/70">{{ service.price_display }}<span class="icon h-4 w-4 transition" :class="open && 'rotate-180'">{% include "icons/chevron-down.svg" %}</span></span>
  </button>
  <div x-show="open" x-transition x-cloak class="rich-text px-5 pb-5">{{ service.short_description|safe }}</div>
</div>
{% else %}
<div class="flex items-center justify-between gap-4 px-5 py-4">
  <span class="font-medium">{{ service.name }}</span>
  <span class="shrink-0 text-ink/70">{{ service.price_display }}</span>
</div>
{% endif %}
```

`templates/catalog/category.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-8 md:py-12">
  <nav class="mb-4 text-sm text-ink/50"><a href="{% url 'catalog:home' %}" class="hover:text-brand-600">Главная</a> / {{ category.name }}</nav>
  <h1 class="text-3xl font-bold md:text-5xl">{{ category.name }}</h1>
  <div class="mt-8 grid gap-8 lg:grid-cols-5">
    {% if photos %}<div class="lg:col-span-3">{% include "catalog/partials/slider.html" with alt=category.name %}</div>{% endif %}
    <div class="rich-text {% if photos %}lg:col-span-2{% else %}lg:col-span-5 max-w-3xl{% endif %}">{{ category.description|safe }}</div>
  </div>
  {% if services %}
  <h2 class="mb-4 mt-12 text-2xl font-bold">Услуги и цены</h2>
  <ul class="divide-y divide-ink/10 overflow-hidden rounded-2xl bg-white ring-1 ring-ink/10">
    {% for service in services %}<li>{% include "catalog/partials/service_row.html" %}</li>{% endfor %}
  </ul>
  {% endif %}
  <div class="mt-10 flex flex-wrap gap-3">{% include "partials/contact_links.html" %}</div>
</div>
{% endblock %}
```

`templates/catalog/service.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-8 md:py-12">
  <nav class="mb-4 text-sm text-ink/50">
    <a href="{% url 'catalog:home' %}" class="hover:text-brand-600">Главная</a>
    {% if category %} / <a href="{{ category.get_absolute_url }}" class="hover:text-brand-600">{{ category.name }}</a>{% endif %}
    / {{ service.name }}
  </nav>
  <h1 class="text-3xl font-bold md:text-5xl">{{ service.name }}</h1>
  {% if service.price_display %}<p class="mt-3 inline-block rounded-full bg-brand-100 px-4 py-1 text-lg font-semibold">{{ service.price_display }}</p>{% endif %}
  {% if photos %}<div class="mt-8">{% include "catalog/partials/slider.html" with alt=service.name %}</div>{% endif %}
  <div class="rich-text mt-8 max-w-3xl">{{ service.description|safe }}</div>
  <div class="mt-10 flex flex-wrap gap-3">{% include "partials/contact_links.html" %}</div>
</div>
{% endblock %}
```

- [ ] **Step 6: Шаблоны контента и инфо-страницы**

`templates/content/events.html`:

```html
{% extends "base.html" %}
{% load site_tags %}
{% block content %}
<section class="relative overflow-hidden bg-ink text-white">
  {% if hero_image %}<img src="{{ hero_image }}" alt="" class="absolute inset-0 h-full w-full object-cover opacity-40">{% endif %}
  <div class="relative mx-auto max-w-6xl px-4 py-16 md:py-24">
    <h1 class="text-4xl font-bold md:text-6xl">Мероприятия</h1>
    {% if site.events_intro %}<div class="rich-text mt-5 max-w-3xl text-lg !text-white/90">{{ site.events_intro|safe }}</div>{% endif %}
    {% if nearest %}<p class="mt-6 text-brand-300">Ближайшее: {{ nearest.title }}, {{ nearest.date|date:"j E" }}</p>{% endif %}
  </div>
</section>

<section class="mx-auto max-w-6xl px-4 py-12">
  {% if events %}
  <div class="swiper js-carousel">
    <div class="swiper-wrapper">
      {% for event in events %}
      <article class="swiper-slide">
        <div class="relative aspect-[4/3] overflow-hidden rounded-2xl bg-ink">
          {% with url=event|spec_url:"card" %}{% if url %}<img src="{{ url }}" alt="{{ event.title }}" loading="lazy" class="absolute inset-0 h-full w-full object-cover">{% endif %}{% endwith %}
          <div class="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent"></div>
          <div class="absolute inset-x-0 bottom-0 p-5" style="color: {% firstof event.text_color '#ffffff' %}">
            <p class="text-sm font-semibold opacity-90">{{ event.date|date:"j E Y" }}</p>
            <h2 class="mt-1 text-xl font-bold">{{ event.title }}</h2>
          </div>
        </div>
        {% if event.description %}<div class="rich-text mt-4 text-sm">{{ event.description|safe }}</div>{% endif %}
        {% if event.link %}<a href="{{ event.link }}" target="_blank" rel="noopener" class="mt-3 inline-flex items-center gap-1 font-semibold text-brand-700 hover:text-brand-600">Подробнее<span class="icon h-4 w-4">{% include "icons/external-link.svg" %}</span></a>{% endif %}
      </article>
      {% endfor %}
    </div>
    <div class="mt-6 flex justify-end gap-2">
      <div class="swiper-button-prev !static !m-0 !h-10 !w-10 rounded-full bg-tint !text-ink after:!text-base"></div>
      <div class="swiper-button-next !static !m-0 !h-10 !w-10 rounded-full bg-tint !text-ink after:!text-base"></div>
    </div>
  </div>
  {% else %}
  <p class="py-10 text-center text-lg text-ink/60">Скоро анонсируем новые мероприятия.</p>
  {% endif %}
</section>
{% endblock %}
```

`templates/content/about.html`:

```html
{% extends "base.html" %}
{% load site_tags %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-12">
  <h1 class="text-4xl font-bold md:text-5xl">О нас</h1>
  <div class="mt-8 grid gap-10 lg:grid-cols-2">
    <div class="space-y-10">
      {% if site.about_text %}<div class="rich-text text-lg">{{ site.about_text|safe }}</div>{% endif %}
      {% if site.philosophy_text %}<div><h2 class="mb-3 text-2xl font-bold">Философия</h2><div class="rich-text">{{ site.philosophy_text|safe }}</div></div>{% endif %}
    </div>
    <div class="space-y-10">
      {% if site.nearby_text %}<div class="rounded-2xl bg-tint p-6"><h2 class="mb-3 text-2xl font-bold">Что рядом</h2><div class="rich-text">{{ site.nearby_text|safe }}</div></div>{% endif %}
      {% if site.about_map %}<a href="{{ site.about_map.url }}" class="glightbox block overflow-hidden rounded-2xl"><img src="{{ site.about_map.url }}" alt="Карта" loading="lazy" class="w-full"></a>{% endif %}
    </div>
  </div>

  {% if employees %}
  <h2 class="mb-6 mt-16 text-2xl font-bold">Команда</h2>
  <div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
    {% for employee in employees %}
    <figure>
      <div class="aspect-[4/5] overflow-hidden rounded-2xl bg-tint">{% with url=employee|spec_url:"portrait" %}{% if url %}<img src="{{ url }}" alt="{{ employee.name }}" loading="lazy" class="h-full w-full object-cover">{% endif %}{% endwith %}</div>
      <figcaption class="mt-3"><p class="font-semibold">{{ employee.name }}</p><p class="text-sm text-ink/60">{{ employee.position }}</p></figcaption>
    </figure>
    {% endfor %}
  </div>
  {% endif %}

  {% if partners %}
  <h2 class="mb-6 mt-16 text-2xl font-bold">Партнёры</h2>
  <div class="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
    {% for partner in partners %}
    {% with url=partner|spec_url:"logo_small" %}
    <a {% if partner.link %}href="{{ partner.link }}" target="_blank" rel="noopener"{% endif %} class="flex aspect-[2/1] items-center justify-center rounded-2xl bg-white p-4 ring-1 ring-ink/10 hover:ring-brand-500">
      {% if url %}<img src="{{ url }}" alt="{% firstof partner.name 'Партнёр' %}" loading="lazy" class="max-h-full max-w-full object-contain">{% else %}{{ partner.name }}{% endif %}
    </a>
    {% endwith %}
    {% endfor %}
  </div>
  {% endif %}
</div>
{% endblock %}
```

`templates/content/reviews.html`:

```html
{% extends "base.html" %}
{% load site_tags %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-12">
  <h1 class="text-4xl font-bold md:text-5xl">Отзывы</h1>
  {% if reviews %}
  <div class="mt-8 gap-6 sm:columns-2 lg:columns-3">
    {% for review in reviews %}
    <article class="mb-6 break-inside-avoid rounded-2xl bg-tint p-6">
      <div class="flex items-center gap-3">
        {% with url=review|spec_url:"avatar" %}{% if url %}<img src="{{ url }}" alt="" loading="lazy" class="h-12 w-12 rounded-full object-cover">{% endif %}{% endwith %}
        <p class="font-semibold">{{ review.author }}</p>
      </div>
      <div class="rich-text mt-4">{{ review.text|safe }}</div>
    </article>
    {% endfor %}
  </div>
  {% else %}
  <p class="mt-8 text-ink/60">Отзывов пока нет.</p>
  {% endif %}
</div>
{% endblock %}
```

`templates/content/gallery.html`:

```html
{% extends "base.html" %}
{% load site_tags %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-12">
  <h1 class="text-4xl font-bold md:text-5xl">Галерея</h1>
  {% if photos %}
  <div class="mt-8 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
    {% for photo in photos %}{% with url=photo|spec_url:"thumb" %}{% if url %}
    <a href="{{ photo.image.url }}" class="glightbox group block aspect-square overflow-hidden rounded-xl bg-tint" data-gallery="gallery" {% if photo.caption %}data-title="{{ photo.caption }}"{% endif %}>
      <img src="{{ url }}" alt="{{ photo.caption }}" loading="lazy" class="h-full w-full object-cover transition duration-500 group-hover:scale-105">
    </a>
    {% endif %}{% endwith %}{% endfor %}
  </div>
  {% else %}
  <p class="mt-8 text-ink/60">Фото скоро появятся.</p>
  {% endif %}
</div>
{% endblock %}
```

`templates/content/contacts.html`:

```html
{% extends "base.html" %}
{% block content %}
<div class="mx-auto max-w-6xl px-4 py-12">
  <h1 class="text-4xl font-bold md:text-5xl">Контакты</h1>
  <div class="mt-8 grid gap-10 lg:grid-cols-2">
    <div class="space-y-6">
      {% if site.address %}
      <p class="flex gap-2 text-lg"><span class="icon mt-1 h-5 w-5 text-brand-600">{% include "icons/map-pin.svg" %}</span>
        {% if site.map_url %}<a href="{{ site.map_url }}" target="_blank" rel="noopener" class="underline underline-offset-2 hover:text-brand-600">{{ site.address }}</a>{% else %}{{ site.address }}{% endif %}
      </p>
      {% endif %}
      {% if phones %}
      <ul class="space-y-2 text-lg">
        {% for phone in phones %}<li><a href="{{ phone.tel_url }}" class="hover:text-brand-600">{{ phone.display }}</a></li>{% endfor %}
      </ul>
      {% endif %}
      <div class="flex flex-wrap gap-3">{% include "partials/contact_links.html" %}</div>
      {% if site.contacts_text %}<div class="rich-text">{{ site.contacts_text|safe }}</div>{% endif %}
    </div>
    {% if site.contacts_map %}<a href="{{ site.contacts_map.url }}" class="glightbox block overflow-hidden rounded-2xl"><img src="{{ site.contacts_map.url }}" alt="Схема проезда" loading="lazy" class="w-full"></a>{% endif %}
  </div>
</div>
{% endblock %}
```

`templates/core/info.html`:

```html
{% extends "base.html" %}
{% block content %}
<article class="mx-auto max-w-3xl px-4 py-12">
  <h1 class="text-3xl font-bold md:text-4xl">{{ page.title }}</h1>
  <div class="rich-text mt-8">{{ page.body|safe }}</div>
</article>
{% endblock %}
```

- [ ] **Step 7: Запустить тесты**

```bash
DEBUG=1 uv run manage.py tailwind build
uv run pytest
```
Expected: все проходят.

- [ ] **Step 8: Визуальная проверка**

`DEBUG=1 uv run manage.py tailwind runserver`: пройти все страницы на 375 px и 1280 px; слайдер категории листается свайпом; аккордеон услуги раскрывается; галерея открывает лайтбокс; карусель мероприятий листается.

- [ ] **Step 9: Commit**

```bash
git add apps templates config tests
git commit -m "Публичные страницы: категории, услуги, мероприятия, о нас, отзывы, галерея, контакты, инфо

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Редиректы со старых URL

**Files:**
- Create: `apps/core/legacy_redirects.py`, `tests/test_legacy_redirects.py`
- Modify: `config/urls.py`

**Interfaces:**
- Consumes: `Category`, `Service`, `InfoPage` (id сохраняются импортом), url-имена из Task 8.
- Produces: маршруты `/TPark`, `/category`, `/category/`, `/category/service`, `/about_2`, `/info`.

Уточнение спецификации: старый URL услуги без «отдельной страницы» ведёт (301) на первую опубликованную категорию с этой услугой — на старом сайте у таких услуг страница была, и ссылка не должна превращаться в 404. Если категорий нет — 404.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_legacy_redirects.py`:

```python
import pytest

from apps.catalog.models import Category, CategoryService, Service
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db


def assert_301(response, url):
    assert response.status_code == 301
    assert response.url == url


def test_tpark_and_about(client):
    assert_301(client.get("/TPark"), "/")
    assert_301(client.get("/about_2"), "/about/")


def test_category(client):
    category = Category.objects.create(id=5, name="Байдарки", is_published=True)
    assert_301(client.get("/category?category_id=5"), category.get_absolute_url())
    assert_301(client.get("/category/?category_id=5"), category.get_absolute_url())


def test_hidden_category_is_404(client):
    Category.objects.create(id=6, name="Скрытая", is_published=False)
    assert client.get("/category?category_id=6").status_code == 404


def test_service_with_page(client):
    service = Service.objects.create(id=12, name="Сплав", has_page=True)
    assert_301(client.get("/category/service?service_id=12"), service.get_absolute_url())


def test_service_without_page_goes_to_category(client):
    category = Category.objects.create(name="Аренда", is_published=True)
    service = Service.objects.create(id=13, name="Палатка")
    CategoryService.objects.create(category=category, service=service)
    assert_301(client.get("/category/service?service_id=13"), category.get_absolute_url())


def test_info(client):
    page = InfoPage.objects.create(id=11, title="Правила")
    assert_301(client.get("/info?info_id=11"), page.get_absolute_url())


@pytest.mark.parametrize(
    "url",
    ["/category?category_id=abc", "/category", "/category?category_id=", "/category/service?service_id=-1", "/info?info_id=999"],
)
def test_legacy_redirect_bad_param_is_404(client, url):
    assert client.get(url).status_code == 404
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_legacy_redirects.py`
Expected: FAIL.

- [ ] **Step 3: Реализовать**

`apps/core/legacy_redirects.py`:

```python
"""301-редиректы со старых URL Flask-версии (сохраняем позиции в поиске и внешние ссылки)."""

from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from apps.catalog.models import Category, Service
from apps.core.models import InfoPage


def _id_param(request, name: str) -> int:
    value = request.GET.get(name, "")
    if not value.isdigit():
        raise Http404
    return int(value)


def category(request):
    obj = get_object_or_404(Category.objects.published(), pk=_id_param(request, "category_id"))
    return HttpResponsePermanentRedirect(obj.get_absolute_url())


def service(request):
    obj = get_object_or_404(Service.objects.published(), pk=_id_param(request, "service_id"))
    if obj.has_page:
        return HttpResponsePermanentRedirect(obj.get_absolute_url())
    link = (
        obj.category_links.filter(category__is_published=True)
        .select_related("category")
        .order_by("category__order", "category__id")
        .first()
    )
    if link is None:
        raise Http404
    return HttpResponsePermanentRedirect(link.category.get_absolute_url())


def info(request):
    obj = get_object_or_404(InfoPage.objects.published(), pk=_id_param(request, "info_id"))
    return HttpResponsePermanentRedirect(obj.get_absolute_url())
```

`config/urls.py` — импорты `from django.views.generic import RedirectView` и `from apps.core import legacy_redirects`; в `urlpatterns` перед `include`-ами:

```python
    path("TPark", RedirectView.as_view(url="/", permanent=True)),
    path("about_2", RedirectView.as_view(pattern_name="content:about", permanent=True)),
    path("category", legacy_redirects.category),
    path("category/", legacy_redirects.category),
    path("category/service", legacy_redirects.service),
    path("info", legacy_redirects.info),
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest`
Expected: все проходят.

- [ ] **Step 5: Commit**

```bash
git add apps/core config/urls.py tests
git commit -m "301-редиректы со старых URL сайта

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: SEO — sitemap.xml, robots.txt, Open Graph

**Files:**
- Create: `apps/core/sitemaps.py`, `tests/test_seo.py`
- Modify: `apps/core/views.py` (robots), `config/urls.py`

**Interfaces:**
- Consumes: `get_absolute_url` моделей, url-имена страниц.
- Produces: `/sitemap.xml`, `/robots.txt`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_seo.py`:

```python
import pytest

from apps.catalog.models import Category, Service
from apps.core.models import InfoPage

pytestmark = pytest.mark.django_db


def test_sitemap_lists_only_public_pages(client):
    Category.objects.create(name="Открытая", is_published=True)
    Category.objects.create(name="Закрытая", is_published=False)
    Service.objects.create(name="Со страницей", has_page=True)
    Service.objects.create(name="Без страницы")
    InfoPage.objects.create(title="Правила")
    xml = client.get("/sitemap.xml").content.decode()
    assert "/category/otkrytaia/" in xml
    assert "zakrytaia" not in xml
    assert "/service/so-stranitsei/" in xml
    assert "bez-stranitsy" not in xml
    assert "/info/pravila/" in xml
    assert "/events/" in xml and "/about/" in xml


def test_robots(client):
    response = client.get("/robots.txt")
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "Disallow: /admin/" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_category_meta(client, make_image):
    category = Category.objects.create(
        name="Байдарки", description="<p>Сплавы по Протве для всей семьи</p>", is_published=True, preview=make_image()
    )
    html = client.get(category.get_absolute_url()).content.decode()
    assert "<title>Байдарки — Т-Парк</title>" in html
    assert 'name="description" content="Сплавы по Протве для всей семьи"' in html
    assert 'property="og:image" content="http://testserver/media/' in html
```

Примечание: slug «Открытая» → `otkrytaia`, «Со страницей» → `so-stranitsei` (так транслитерирует unidecode). Если фактический slug отличается — поправить ожидание по выводу `slugify_ru`, а не реализацию.

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/test_seo.py`
Expected: FAIL (404 на `/sitemap.xml`).

- [ ] **Step 3: Реализовать**

`apps/core/sitemaps.py`:

```python
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.catalog.models import Category, Service
from apps.core.models import InfoPage


class StaticSitemap(Sitemap):
    def items(self):
        return ["catalog:home", "content:events", "content:about", "content:reviews", "content:gallery", "content:contacts"]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    def items(self):
        return Category.objects.published().order_by("order", "id")


class ServiceSitemap(Sitemap):
    def items(self):
        return Service.objects.published().filter(has_page=True).order_by("id")


class InfoPageSitemap(Sitemap):
    def items(self):
        return InfoPage.objects.published().order_by("id")


SITEMAPS = {
    "static": StaticSitemap,
    "categories": CategorySitemap,
    "services": ServiceSitemap,
    "info": InfoPageSitemap,
}
```

`apps/core/views.py` — дописать:

```python
from django.http import HttpResponse


def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /admin/", f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
```

`config/urls.py` — импорты `from django.contrib.sitemaps.views import sitemap`, `from apps.core.sitemaps import SITEMAPS`, `from apps.core.views import healthz, robots_txt`; маршруты:

```python
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest`
Expected: все проходят.

- [ ] **Step 5: Commit**

```bash
git add apps/core config/urls.py tests
git commit -m "SEO: sitemap.xml, robots.txt, мета-описания и Open Graph

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Импорт — каркас, настройки сайта, телефоны, инфо-страницы

**Files:**
- Create: `apps/core/legacy/__init__.py`, `reader.py`, `report.py`, `media.py`, `html.py`, `site.py`, `runner.py`, `apps/core/management/__init__.py`, `apps/core/management/commands/__init__.py`, `apps/core/management/commands/import_legacy.py`, `tests/legacy/__init__.py`, `tests/legacy/schema.sql`, `tests/legacy/conftest.py`, `tests/legacy/test_import_site.py`

**Interfaces:**
- Consumes: модели core, `sanitize_html`, `Category`/`Service`/`Event` (проверка наличия контента).
- Produces:
  - `LegacyDB(path: Path)` с методами `rows(table: str, order_by: str = "id") -> list[dict]`, `close()`;
  - `Report` (`counts: Counter`, `warnings: list[str]`, `add(label, n=1)`, `warn(message)`, `render() -> str`);
  - `numbered_images(directory: Path) -> list[Path]`, `attach_image(instance, field_name: str, path: Path, report: Report, *, missing_ok: bool = False) -> bool`;
  - `clean_html(value) -> str`, `extract_title(html: str, fallback: str) -> str`, `parse_date(value) -> date | None`, `phone_digits(value: str) -> str | None`;
  - `import_site(db: LegacyDB, images: Path, report: Report) -> None`;
  - `LegacyImportError(Exception)`, `run_import(db_path: Path, images_dir: Path, *, flush: bool = False, price_csv: Path | None = None) -> Report`, `has_content() -> bool`, `flush_content() -> None`;
  - команда `import_legacy --db --images [--flush] [--price-csv]`;
  - фикстура `legacy` (`LegacyFixture`: `insert(table, **values)`, `image(relpath, size=(40, 30)) -> Path`, `run(**kwargs) -> Report`, `db_path`, `images`).

- [ ] **Step 1: Снять схему старой БД для тестов**

```bash
mkdir -p tests/legacy
sqlite3 old_version/T_Park.db .schema > tests/legacy/schema.sql
grep -c "CREATE TABLE" tests/legacy/schema.sql
```
Expected: `13`.

- [ ] **Step 2: Фикстура старой БД**

`tests/legacy/__init__.py` — пустой. `tests/legacy/conftest.py`:

```python
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from apps.core.legacy.runner import run_import

SCHEMA = Path(__file__).parent / "schema.sql"


class LegacyFixture:
    def __init__(self, tmp_path: Path):
        self.db_path = tmp_path / "legacy.db"
        self.images = tmp_path / "images"
        self.images.mkdir()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    def insert(self, table: str, **values) -> None:
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self.conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({marks})', list(values.values()))
        self.conn.commit()

    def image(self, relpath: str, size=(40, 30)) -> Path:
        path = self.images / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, "orange").save(path, "JPEG")
        return path

    def run(self, **kwargs):
        return run_import(self.db_path, self.images, **kwargs)


@pytest.fixture
def legacy(tmp_path):
    fixture = LegacyFixture(tmp_path)
    yield fixture
    fixture.conn.close()
```

- [ ] **Step 3: Написать падающие тесты**

`tests/legacy/test_import_site.py`:

```python
import pytest
from django.core.management import CommandError, call_command

from apps.catalog.models import Category
from apps.core.models import InfoPage, Phone, SiteSettings

pytestmark = pytest.mark.django_db(transaction=True)


def add_texts(legacy, **texts):
    for title, text in texts.items():
        legacy.insert("text", title=title, text=text)


def test_site_texts_and_contacts(legacy):
    add_texts(
        legacy,
        main_text="<p>Добро пожаловать</p><script>x</script>",
        about="<p>О нас</p>",
        filosofi="<p>Философия</p>",
        structure="<p>Рядом</p>",
        contacts_info="<p>Как добраться</p>",
        address="Калужская область, село Восход ",
        geolocation="https://yandex.ru/maps/-/CCUufTqlWC",
        vk="https://vk.com/tparkprotva",
    )
    legacy.image("staff/map.jpg")
    legacy.run()
    site = SiteSettings.load()
    assert site.home_intro == site.events_intro == "<p>Добро пожаловать</p>"
    assert site.about_text == "<p>О нас</p>"
    assert site.philosophy_text == "<p>Философия</p>"
    assert site.nearby_text == "<p>Рядом</p>"
    assert site.contacts_text == "<p>Как добраться</p>"
    assert site.address == "Калужская область, село Восход"
    assert site.map_url.endswith("CCUufTqlWC")
    assert site.vk_url == "https://vk.com/tparkprotva"
    assert site.contacts_map and not site.about_map


def test_phones_and_messenger_flags(legacy):
    add_texts(legacy, phone_numbers="9029856594 9953056461 abc 9106087735", insta="tg://resolve?domain=+79953056461")
    report = legacy.run()
    phones = list(Phone.objects.values_list("number", "is_whatsapp", "is_telegram"))
    assert phones == [
        ("9029856594", True, False),
        ("9953056461", False, True),
        ("9106087735", False, False),
    ]
    assert any("abc" in w for w in report.warnings)


def test_info_pages_keep_id_and_get_title(legacy):
    legacy.insert("text", id=11, title=None, text="<p><strong>Правила безопасности Т-парка</strong></p><p>&nbsp;</p>", status=1)
    legacy.insert("text", id=12, title=None, text="<p>просто текст</p>", status=None)
    legacy.run()
    rules = InfoPage.objects.get(id=11)
    assert rules.title == "Правила безопасности Т-парка"
    assert rules.is_published
    untitled = InfoPage.objects.get(id=12)
    assert untitled.title == "Страница 12"
    assert not untitled.is_published


def test_refuses_when_content_exists(legacy):
    Category.objects.create(name="Уже есть")
    with pytest.raises(CommandError, match="--flush"):
        call_command("import_legacy", "--db", str(legacy.db_path), "--images", str(legacy.images))


def test_missing_images_dir(legacy, tmp_path):
    with pytest.raises(CommandError, match="изображениями"):
        call_command("import_legacy", "--db", str(legacy.db_path), "--images", str(tmp_path / "nope"))


def test_command_prints_report(legacy, capsys, tmp_path):
    add_texts(legacy, phone_numbers="9029856594")
    call_command(
        "import_legacy", "--db", str(legacy.db_path), "--images", str(legacy.images), "--price-csv", str(tmp_path / "p.csv")
    )
    out = capsys.readouterr().out
    assert "Телефоны: 1" in out
    assert "Импорт завершён" in out
```

`transaction=True` нужен, потому что `run_import` сам открывает транзакцию и проверяет откат.

- [ ] **Step 4: Запустить — убедиться, что падают**

Run: `uv run pytest tests/legacy`
Expected: ERROR (`No module named 'apps.core.legacy'`).

- [ ] **Step 5: Реализовать каркас импорта**

`apps/core/legacy/__init__.py`, `apps/core/management/__init__.py`, `apps/core/management/commands/__init__.py` — пустые.

`apps/core/legacy/reader.py`:

```python
import sqlite3
from pathlib import Path


class LegacyDB:
    """Старая SQLite Flask-версии, открытая только на чтение."""

    def __init__(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(f"Старая база не найдена: {path}")
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def rows(self, table: str, order_by: str = "id") -> list[dict]:
        cursor = self.conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')
        return [dict(row) for row in cursor]

    def close(self) -> None:
        self.conn.close()
```

`apps/core/legacy/report.py`:

```python
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Report:
    counts: Counter = field(default_factory=Counter)
    warnings: list[str] = field(default_factory=list)

    def add(self, label: str, n: int = 1) -> None:
        self.counts[label] += n

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def render(self) -> str:
        lines = ["Перенесено:", *(f"  {label}: {n}" for label, n in self.counts.items())]
        if self.warnings:
            lines += ["", f"Предупреждения ({len(self.warnings)}):", *(f"  - {w}" for w in self.warnings)]
        return "\n".join(lines)
```

`apps/core/legacy/media.py`:

```python
from pathlib import Path

from django.core.files import File
from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def numbered_images(directory: Path) -> list[Path]:
    """Картинки папки по номеру в имени (2.jpg раньше 10.jpg); прочие имена — в конце по алфавиту."""
    if not directory.is_dir():
        return []
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    return sorted(files, key=lambda p: (0, int(p.stem), "") if p.stem.isdigit() else (1, 0, p.name))


def attach_image(instance, field_name: str, path: Path, report, *, missing_ok: bool = False) -> bool:
    """Кладёт файл в поле изображения (с пережатием). Битый файл — предупреждение, а не падение импорта."""
    if not path.is_file():
        if not missing_ok:
            report.warn(f"Нет файла {path}")
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        with path.open("rb") as fh:
            getattr(instance, field_name).save(path.name, File(fh), save=False)
    except Exception as exc:
        report.warn(f"Не удалось загрузить {path}: {exc}")
        return False
    return True
```

`apps/core/legacy/html.py`:

```python
import html
import re
from datetime import date

from django.utils.html import strip_tags

from apps.core.fields import sanitize_html

_TITLE_RE = re.compile(r"<(strong|h[1-3])[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)


def clean_html(value) -> str:
    return sanitize_html(value or "").strip()


def extract_title(body: str, fallback: str) -> str:
    match = _TITLE_RE.search(body or "")
    if match:
        text = re.sub(r"\s+", " ", html.unescape(strip_tags(match.group(2)))).strip()
        if text:
            return text[:255]
    return fallback


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def phone_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else None
```

`apps/core/legacy/site.py`:

```python
from pathlib import Path

from apps.core.legacy.html import clean_html, extract_title, phone_digits
from apps.core.legacy.media import attach_image
from apps.core.models import InfoPage, Phone, SiteSettings

TEXT_FIELDS = {
    "about": "about_text",
    "filosofi": "philosophy_text",
    "structure": "nearby_text",
    "contacts_info": "contacts_text",
}


def import_site(db, images: Path, report) -> None:
    texts, info_rows = {}, []
    for row in db.rows("text"):
        if row["title"]:
            texts[row["title"]] = row["text"] or ""
        else:
            info_rows.append(row)

    site = SiteSettings.load()
    main_text = clean_html(texts.get("main_text"))
    site.home_intro = site.events_intro = main_text
    for key, field in TEXT_FIELDS.items():
        setattr(site, field, clean_html(texts.get(key)))
    site.address = (texts.get("address") or "").strip()[:255]
    site.map_url = (texts.get("geolocation") or "").strip()[:500]
    site.vk_url = (texts.get("vk") or "").strip()[:500]
    attach_image(site, "contacts_map", images / "staff" / "map.jpg", report, missing_ok=True)
    attach_image(site, "about_map", images / "staff" / "map_about.jpg", report, missing_ok=True)
    site.save()
    report.add("Настройки сайта")

    telegram = phone_digits(texts.get("insta") or "")
    whatsapp_used = telegram_used = False
    for order, raw in enumerate((texts.get("phone_numbers") or "").split()):
        number = phone_digits(raw)
        if not number:
            report.warn(f"Пропущен некорректный телефон {raw!r}")
            continue
        is_whatsapp = not whatsapp_used
        is_telegram = not telegram_used and number == telegram
        Phone.objects.create(settings=site, number=number, order=order, is_whatsapp=is_whatsapp, is_telegram=is_telegram)
        whatsapp_used = whatsapp_used or is_whatsapp
        telegram_used = telegram_used or is_telegram
        report.add("Телефоны")

    for row in info_rows:
        body = clean_html(row["text"])
        InfoPage.objects.create(
            id=row["id"],
            title=extract_title(body, f"Страница {row['id']}"),
            body=body,
            is_published=bool(row["status"]),
        )
        report.add("Инфо-страницы")
```

`apps/core/legacy/runner.py`:

```python
import csv
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.legacy.reader import LegacyDB
from apps.core.legacy.report import Report
from apps.core.legacy.site import import_site
from apps.core.models import InfoPage, Phone, SiteSettings

CONTENT_MODELS = [
    CategoryService, CategoryPhoto, ServicePhoto, CategoryGroup, Service, Category,
    Event, Review, Partner, Employee, GalleryPhoto, InfoPage, Phone, SiteSettings,
]


class LegacyImportError(Exception):
    pass


def has_content() -> bool:
    return Category.objects.exists() or Service.objects.exists() or Event.objects.exists()


def flush_content() -> None:
    for model in CONTENT_MODELS:
        model.objects.all().delete()


def _media_files() -> set[Path]:
    root = Path(settings.MEDIA_ROOT)
    return {p for p in root.rglob("*") if p.is_file()} if root.exists() else set()


def export_prices(db: LegacyDB, path: Path, report: Report) -> None:
    rows = db.rows("price")
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "service_id", "price", "time"])
        writer.writerows([r["id"], r["service_id"], r["price"], r["time"]] for r in rows)
    report.add(f"Строк таблицы price выгружено в {path}", len(rows))


def run_import(db_path: Path, images_dir: Path, *, flush: bool = False, price_csv: Path | None = None) -> Report:
    if not images_dir.is_dir():
        raise LegacyImportError(f"Папка с изображениями не найдена: {images_dir}")
    if has_content() and not flush:
        raise LegacyImportError("В базе уже есть контент. Запустите с --flush, чтобы заменить его.")
    db = LegacyDB(db_path)
    report = Report()
    before = _media_files()
    try:
        try:
            with transaction.atomic():
                if flush:
                    flush_content()
                import_site(db, images_dir, report)
        except Exception:
            # БД откатилась — удаляем файлы, которые успел записать импорт.
            for path in _media_files() - before:
                path.unlink(missing_ok=True)
            raise
        if price_csv:
            export_prices(db, price_csv, report)
    finally:
        db.close()
    return report
```

`apps/core/management/commands/import_legacy.py`:

```python
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.legacy.runner import LegacyImportError, run_import


class Command(BaseCommand):
    help = "Импорт данных из старой Flask-версии (SQLite + папка images)."

    def add_arguments(self, parser):
        parser.add_argument("--db", required=True, type=Path, help="Путь к старой T_Park.db")
        parser.add_argument("--images", required=True, type=Path, help="Путь к старой папке app/static/images")
        parser.add_argument("--flush", action="store_true", help="Удалить текущий контент перед импортом")
        parser.add_argument("--price-csv", type=Path, default=Path("price_legacy.csv"), help="Куда выгрузить таблицу price")

    def handle(self, *args, db, images, flush, price_csv, **options):
        try:
            report = run_import(db, images, flush=flush, price_csv=price_csv)
        except (LegacyImportError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(report.render())
        self.stdout.write(self.style.SUCCESS("Импорт завершён."))
```

- [ ] **Step 6: Запустить тесты**

Run: `uv run pytest tests/legacy`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add apps/core tests/legacy
git commit -m "Импорт старых данных: каркас команды, настройки сайта, телефоны, инфо-страницы

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Импорт каталога

**Files:**
- Create: `apps/core/legacy/catalog.py`, `tests/legacy/test_import_catalog.py`
- Modify: `apps/core/legacy/runner.py` (вызов `import_catalog`)

**Interfaces:**
- Consumes: `LegacyDB.rows`, `Report`, `attach_image`, `numbered_images`, `clean_html`, модели каталога.
- Produces: `import_catalog(db, images: Path, report) -> None`.

- [ ] **Step 1: Написать падающие тесты**

`tests/legacy/test_import_catalog.py`:

```python
import pytest

from apps.catalog.models import Category, CategoryGroup, CategoryService, Service

pytestmark = pytest.mark.django_db(transaction=True)


def test_categories_with_photos_and_preview(legacy):
    legacy.insert("category", id=5, name="Байдарки", description="<p>Сплавы</p>", status=1, number=3)
    legacy.insert("category", id=6, name="Скрытая", status=0, number=None)
    for name in ["10.jpg", "2.jpg", "1.jpg"]:
        legacy.image(f"category/5/{name}", size=(40 + int(name.split(".")[0]), 30))
    legacy.image("category/preview/5.jpg")
    legacy.run()
    category = Category.objects.get(id=5)
    assert (category.name, category.order, category.is_published, category.slug) == ("Байдарки", 3, True, "baidarki")
    assert category.description == "<p>Сплавы</p>"
    assert category.preview
    widths = [photo.image.width for photo in category.photos.all()]
    assert widths == [41, 42, 50]
    assert Category.objects.get(id=6).is_published is False


def test_groups_and_orphan_links(legacy):
    legacy.insert("category", id=1, name="A", status=1, number=1)
    legacy.insert("type", id=1, name="Активный отдых", number=2)
    legacy.insert("category_type", id=1, type_id=1, category_id=1)
    legacy.insert("category_type", id=2, type_id=1, category_id=99)
    report = legacy.run()
    group = CategoryGroup.objects.get()
    assert (group.name, group.order) == ("Активный отдых", 2)
    assert list(group.categories.values_list("id", flat=True)) == [1]
    assert any("#2" in w for w in report.warnings)


def test_services_and_links(legacy):
    legacy.insert("category", id=1, name="A", status=1, number=1)
    legacy.insert("service", id=21, name="Сплав", price="500", time="час", status=None, next=1, short_description="<p>к</p>")
    legacy.insert("service", id=22, name="Палатка", price=None, time=None, status=0, next=0)
    legacy.insert("service_category", id=1, service_id=21, category_id=1, number=2)
    legacy.insert("service_category", id=2, service_id=22, category_id=1, number=None)
    legacy.insert("service_category", id=3, service_id=21, category_id=1, number=5)
    legacy.insert("service_category", id=4, service_id=999, category_id=1, number=1)
    legacy.image("service/21/1.jpg")
    report = legacy.run()
    splav = Service.objects.get(id=21)
    assert (splav.price, splav.price_unit, splav.is_published, splav.has_page) == ("500", "час", True, True)
    assert splav.photos.count() == 1
    tent = Service.objects.get(id=22)
    assert (tent.price, tent.is_published, tent.has_page) == ("", False, False)
    links = list(CategoryService.objects.order_by("order").values_list("service_id", "order"))
    assert links == [(21, 2), (22, 10000)]
    assert any("#4" in w for w in report.warnings)
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/legacy/test_import_catalog.py`
Expected: FAIL (категории не импортируются).

- [ ] **Step 3: Реализовать**

`apps/core/legacy/catalog.py`:

```python
from pathlib import Path

from apps.catalog.models import Category, CategoryGroup, CategoryPhoto, CategoryService, Service, ServicePhoto
from apps.core.legacy.html import clean_html
from apps.core.legacy.media import attach_image, numbered_images

LAST = 10_000  # порядок для связей без номера — в конец списка


def _order(value) -> int:
    return max(int(value), 0) if value is not None else LAST


def _import_photos(model, parent_field: str, parent, directory: Path, report, label: str) -> None:
    for order, path in enumerate(numbered_images(directory)):
        photo = model(**{parent_field: parent}, order=order)
        if attach_image(photo, "image", path, report):
            photo.save()
            report.add(label)


def import_catalog(db, images: Path, report) -> None:
    for row in db.rows("category"):
        category = Category(
            id=row["id"],
            name=(row["name"] or "").strip() or f"Категория {row['id']}",
            description=clean_html(row["description"]),
            is_published=bool(row["status"]),
            order=row["number"] if row["number"] is not None and row["number"] >= 0 else 0,
        )
        attach_image(category, "preview", images / "category" / "preview" / f"{row['id']}.jpg", report, missing_ok=True)
        category.save()
        report.add("Категории")
        _import_photos(CategoryPhoto, "category", category, images / "category" / str(row["id"]), report, "Фото категорий")

    category_ids = set(Category.objects.values_list("id", flat=True))
    groups = {}
    for row in db.rows("type"):
        groups[row["id"]] = CategoryGroup.objects.create(name=(row["name"] or "").strip(), order=row["number"] or 0)
        report.add("Группы категорий")
    for row in db.rows("category_type"):
        group = groups.get(row["type_id"])
        if group is None or row["category_id"] not in category_ids:
            report.warn(f"Пропущена связь группа–категория #{row['id']}: ссылка на удалённую запись")
            continue
        group.categories.add(row["category_id"])

    for row in db.rows("service"):
        service = Service.objects.create(
            id=row["id"],
            name=(row["name"] or "").strip() or f"Услуга {row['id']}",
            short_description=clean_html(row["short_description"]),
            description=clean_html(row["description"]),
            price=(row["price"] or "").strip()[:32],
            price_unit=(row["time"] or "").strip()[:128],
            is_published=row["status"] is None or bool(row["status"]),
            has_page=bool(row["next"]),
        )
        report.add("Услуги")
        _import_photos(ServicePhoto, "service", service, images / "service" / str(row["id"]), report, "Фото услуг")

    service_ids = set(Service.objects.values_list("id", flat=True))
    seen = set()
    for row in db.rows("service_category"):
        key = (row["category_id"], row["service_id"])
        if row["category_id"] not in category_ids or row["service_id"] not in service_ids:
            report.warn(f"Пропущена связь категория–услуга #{row['id']}: ссылка на удалённую запись")
            continue
        if key in seen:
            continue
        seen.add(key)
        CategoryService.objects.create(category_id=key[0], service_id=key[1], order=_order(row["number"]))
        report.add("Услуги в категориях")
```

`apps/core/legacy/runner.py`: добавить импорт `from apps.core.legacy.catalog import import_catalog` и вызов `import_catalog(db, images_dir, report)` сразу после `import_site(...)`.

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest tests/legacy`
Expected: все проходят.

- [ ] **Step 5: Commit**

```bash
git add apps/core/legacy tests/legacy
git commit -m "Импорт каталога: категории, группы, услуги, фото, порядок услуг

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Импорт контента, выгрузка price, flush и откат

**Files:**
- Create: `apps/core/legacy/content.py`, `tests/legacy/test_import_content.py`
- Modify: `apps/core/legacy/runner.py` (вызов `import_content`)

**Interfaces:**
- Consumes: всё из Tasks 11–12, модели контента.
- Produces: `import_content(db, images: Path, report) -> None`.

- [ ] **Step 1: Написать падающие тесты**

`tests/legacy/test_import_content.py`:

```python
import csv
from datetime import date

import pytest

from apps.catalog.models import Category
from apps.content.models import Employee, Event, GalleryPhoto, Partner, Review
from apps.core.legacy import runner

pytestmark = pytest.mark.django_db(transaction=True)


def test_events(legacy):
    legacy.insert("event", id=2, title="Сплав", date="2022-09-24", link="https://vk.com/e", text_color="#ffffff", after_date=1)
    legacy.insert("event", id=3, title="Квест", date="2022-10-16 22:00:00.000000", text_color="red", after_date=None)
    legacy.insert("event", id=4, title="Без даты", date=None)
    legacy.image("events/2.jpg")
    legacy.image("events/0.jpg")
    report = legacy.run()
    splav = Event.objects.get(title="Сплав")
    assert (splav.date, splav.text_color, splav.show_after_date, splav.link) == (date(2022, 9, 24), "#ffffff", True, "https://vk.com/e")
    assert splav.image
    kvest = Event.objects.get(title="Квест")
    assert (kvest.date, kvest.text_color, kvest.show_after_date) == (date(2022, 10, 16), "", False)
    assert not Event.objects.filter(title="Без даты").exists()
    assert any("слайдера" in w and "#2" in w for w in report.warnings)
    assert any("Без даты" in w or "#4" in w for w in report.warnings)


def test_reviews_partners_employees_gallery(legacy):
    legacy.insert("comment", id=4, name="Анна", text='<p><a href="https://reviews.yandex.ru/x">Отзыв</a></p>')
    legacy.insert("comment", id=5, name="Борис", text="<p>Ещё</p>")
    legacy.image("comments/5.jpg")
    legacy.insert("partner", id=1, name="1", link="https://partner.ru")
    legacy.insert("partner", id=2, name="temp", link=None)
    legacy.image("partner/1.jpg")
    legacy.insert("employee", id=1, name="Сотрудник", position=None, photo=None)
    for name in ["3.jpg", "12.jpg", "1.jpg"]:
        legacy.image(f"gallery/{name}", size=(30 + int(name.split(".")[0]), 30))
    report = legacy.run()
    reviews = list(Review.objects.all())
    assert [(r.author, r.order) for r in reviews] == [("Анна", 0), ("Борис", 1)]
    assert 'href="https://reviews.yandex.ru/x"' in reviews[0].text
    assert not reviews[0].photo and reviews[1].photo
    partner = Partner.objects.get()
    assert (partner.name, partner.link) == ("", "https://partner.ru") and partner.logo
    assert Employee.objects.count() == 0
    assert any("Сотрудники не перенесены" in w for w in report.warnings)
    assert [p.image.width for p in GalleryPhoto.objects.all()] == [31, 33, 42]


def test_price_csv(legacy, tmp_path):
    legacy.insert("price", id=1, service_id=21, price="500", time="час")
    target = tmp_path / "price.csv"
    legacy.run(price_csv=target)
    with target.open(encoding="utf-8-sig") as fh:
        assert list(csv.reader(fh)) == [["id", "service_id", "price", "time"], ["1", "21", "500", "час"]]


def test_corrupt_image_is_warning_not_failure(legacy):
    legacy.insert("comment", id=1, name="Анна", text="<p>x</p>")
    broken = legacy.images / "comments" / "1.jpg"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"not an image")
    report = legacy.run()
    assert Review.objects.get().photo.name in ("", None)
    assert any("1.jpg" in w for w in report.warnings)


def test_flush_replaces_content(legacy):
    Category.objects.create(name="Старая")
    legacy.insert("category", id=1, name="Новая", status=1, number=0)
    legacy.run(flush=True)
    assert list(Category.objects.values_list("name", flat=True)) == ["Новая"]


def test_failed_import_rolls_back_db_and_files(legacy, monkeypatch, media_root, make_image):
    from apps.content.models import GalleryPhoto as Photo

    kept = Photo.objects.create(image=make_image())
    kept_path = media_root / kept.image.name
    Category.objects.create(name="Старая")
    legacy.insert("category", id=1, name="Новая", status=1, number=0)
    legacy.image("category/1/1.jpg")

    def boom(*args, **kwargs):
        raise RuntimeError("сбой посередине")

    monkeypatch.setattr(runner, "import_content", boom)
    files_before = {p for p in media_root.rglob("*") if p.is_file()}
    with pytest.raises(RuntimeError):
        legacy.run(flush=True)
    assert list(Category.objects.values_list("name", flat=True)) == ["Старая"]
    assert Photo.objects.filter(pk=kept.pk).exists() and kept_path.exists()
    assert {p for p in media_root.rglob("*") if p.is_file()} == files_before
```

- [ ] **Step 2: Запустить — убедиться, что падают**

Run: `uv run pytest tests/legacy/test_import_content.py`
Expected: FAIL.

- [ ] **Step 3: Реализовать импорт контента**

`apps/core/legacy/content.py`:

```python
import re
from pathlib import Path

from apps.content.models import Event, GalleryPhoto, Partner, Review
from apps.core.legacy.html import clean_html, parse_date
from apps.core.legacy.media import attach_image, numbered_images

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
OLD_BANNER_IDS = {0, 1, 2}  # events/0..2.jpg — фон слайдера старой страницы событий


def import_content(db, images: Path, report) -> None:
    for row in db.rows("event"):
        event_date = parse_date(row["date"])
        if event_date is None:
            report.warn(f"Мероприятие #{row['id']} «{row['title']}» без даты — пропущено")
            continue
        color = (row["text_color"] or "").strip()
        event = Event(
            title=(row["title"] or "").strip()[:128] or f"Мероприятие {row['id']}",
            date=event_date,
            description=clean_html(row["description"]),
            link=(row["link"] or "").strip()[:500],
            text_color=color if COLOR_RE.match(color) else "",
            show_after_date=bool(row["after_date"]),
        )
        path = images / "events" / f"{row['id']}.jpg"
        attach_image(event, "image", path, report)
        if row["id"] in OLD_BANNER_IDS and path.is_file():
            report.warn(
                f"Фото мероприятия #{row['id']} ({path.name}) совпадает по имени с фоном старого слайдера — проверьте вручную"
            )
        event.save()
        report.add("Мероприятия")

    for order, row in enumerate(db.rows("comment")):
        review = Review(author=(row["name"] or "").strip()[:128], text=clean_html(row["text"]), is_published=True, order=order)
        attach_image(review, "photo", images / "comments" / f"{row['id']}.jpg", report, missing_ok=True)
        review.save()
        report.add("Отзывы")

    for order, row in enumerate(db.rows("partner")):
        if row["name"] == "temp":
            report.warn(f"Пропущена служебная запись партнёра #{row['id']} «temp»")
            continue
        partner = Partner(name="", link=(row["link"] or "").strip()[:500], order=order)
        attach_image(partner, "logo", images / "partner" / f"{row['id']}.jpg", report)
        partner.save()
        report.add("Партнёры")

    employees = db.rows("employee")
    if employees:
        report.warn(f"Сотрудники не перенесены: {len(employees)} записей-заглушек, заведите их в админке")

    for order, path in enumerate(numbered_images(images / "gallery")):
        photo = GalleryPhoto(order=order)
        if attach_image(photo, "image", path, report):
            photo.save()
            report.add("Фото галереи")
```

`apps/core/legacy/runner.py`: добавить `from apps.core.legacy.content import import_content` и вызов `import_content(db, images_dir, report)` после `import_catalog(...)`. Вызов должен идти через имя модуля `runner` (`import_content(...)` внутри `runner.py`), чтобы `monkeypatch.setattr(runner, "import_content", ...)` в тесте подменял его.

Отметить в `test_failed_import_rolls_back_db_and_files`: файл старого фото не удаляется, потому что очистка файлов выполняется через `transaction.on_commit` (Task 3), а при откате on_commit-колбэки отбрасываются.

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest`
Expected: все проходят.

- [ ] **Step 5: Commit**

```bash
git add apps/core/legacy tests/legacy
git commit -m "Импорт контента: мероприятия, отзывы, партнёры, галерея, выгрузка price, откат при ошибке

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Бэкап — команда backup_db и скрипт

**Files:**
- Create: `apps/core/management/commands/backup_db.py`, `scripts/backup.sh`, `tests/test_backup.py`

**Interfaces:**
- Produces: команда `backup_db <destination>`; `scripts/backup.sh` (переменная `BACKUP_KEEP`, по умолчанию 14).

- [ ] **Step 1: Написать падающий тест**

`tests/test_backup.py`:

```python
import sqlite3

import pytest
from django.core.management import call_command

from apps.catalog.models import Category

pytestmark = pytest.mark.django_db(transaction=True)


def test_backup_db_creates_consistent_copy(tmp_path):
    Category.objects.create(name="Байдарки")
    target = tmp_path / "backup.sqlite3"
    call_command("backup_db", str(target))
    with sqlite3.connect(target) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM catalog_category")]
    assert names == ["Байдарки"]
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `uv run pytest tests/test_backup.py`
Expected: FAIL (`Unknown command: 'backup_db'`).

- [ ] **Step 3: Реализовать**

`apps/core/management/commands/backup_db.py`:

```python
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Консистентный снимок SQLite без остановки сайта (sqlite3 backup API)."

    def add_arguments(self, parser):
        parser.add_argument("destination", type=Path)

    def handle(self, *args, destination: Path, **options):
        destination.parent.mkdir(parents=True, exist_ok=True)
        connection.ensure_connection()
        target = sqlite3.connect(destination)
        try:
            connection.connection.backup(target)
        finally:
            target.close()
        self.stdout.write(self.style.SUCCESS(f"Снимок базы сохранён: {destination}"))
```

`scripts/backup.sh`:

```bash
#!/usr/bin/env bash
# Бэкап продакшена: снимок SQLite + архив медиа. Запуск из cron на хосте, например:
#   15 3 * * * cd /srv/tpark && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP="${BACKUP_KEEP:-14}"
DEST="backups/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$DEST"

docker compose exec -T web python manage.py backup_db /data/db/backup.sqlite3
docker compose cp web:/data/db/backup.sqlite3 "$DEST/db.sqlite3"
docker compose exec -T web rm -f /data/db/backup.sqlite3
docker compose exec -T web tar -czf - -C /data media > "$DEST/media.tar.gz"

ls -1dt backups/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
echo "Бэкап готов: $DEST"
```

```bash
chmod +x scripts/backup.sh
```

- [ ] **Step 4: Запустить тесты**

Run: `uv run pytest tests/test_backup.py`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/core/management scripts tests/test_backup.py
git commit -m "Бэкап: команда backup_db и скрипт для cron

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Docker и docker compose

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`, `docker/entrypoint.sh`, `docker/nginx-media.conf`

**Interfaces:**
- Consumes: `healthz`, переменные окружения из Task 1.
- Produces: образ `tpark-web`; сервисы `web` (алиас в сети прокси `tpark-web`, порт 8000) и `media` (алиас `tpark-media`, порт 80).

- [ ] **Step 1: Dockerfile и вспомогательные файлы**

`.dockerignore`:

```
.git
.venv
.idea
.pytest_cache
.ruff_cache
__pycache__
.env
db.sqlite3*
media
staticfiles
backups
old_version
docs
tests
.django_tailwind_cli
static/css/tailwind.css
```

`Dockerfile`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DATABASE_PATH=/data/db/db.sqlite3 \
    MEDIA_ROOT=/data/media \
    STATIC_ROOT=/app/staticfiles

RUN SECRET_KEY=build-only python manage.py tailwind build \
 && SECRET_KEY=build-only python manage.py collectstatic --noinput \
 && useradd --system --uid 1000 --home-dir /app app \
 && mkdir -p /data/db /data/media \
 && chown -R app:app /data \
 && chmod +x /app/docker/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
```

Число воркеров gunicorn берёт из переменной `WEB_CONCURRENCY` (задаётся в `.env`).

`docker/entrypoint.sh`:

```sh
#!/bin/sh
set -e
python manage.py migrate --noinput
exec "$@"
```

`docker/nginx-media.conf`:

```nginx
server {
    listen 80;
    server_tokens off;

    location /media/ {
        alias /data/media/;
        autoindex off;
        expires 30d;
        add_header Cache-Control "public";
    }

    location / {
        return 404;
    }
}
```

`compose.yaml`:

```yaml
services:
  web:
    build: .
    image: tpark-web
    env_file: .env
    restart: unless-stopped
    volumes:
      - db:/data/db
      - media:/data/media
    networks:
      proxy:
        aliases: [tpark-web]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  media:
    image: nginx:stable-alpine
    restart: unless-stopped
    volumes:
      - media:/data/media:ro
      - ./docker/nginx-media.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      proxy:
        aliases: [tpark-media]

volumes:
  db:
  media:

networks:
  proxy:
    external: true
    name: ${PROXY_NETWORK:?Укажите PROXY_NETWORK в .env}
```

Прокси маршрутизирует: `t-camp.ru/media/` → `http://tpark-media:80`, остальное → `http://tpark-web:8000`, и передаёт заголовок `X-Forwarded-Proto`.

- [ ] **Step 2: Проверить конфиг compose**

```bash
cp .env.example .env   # если .env ещё нет; заполнить SECRET_KEY, DEBUG=0
docker network create proxy 2>/dev/null || true
docker compose config | grep -A2 "aliases"
```
Expected: алиасы `tpark-web` и `tpark-media` в выводе.

- [ ] **Step 3: Собрать и запустить локально**

```bash
docker compose build
docker compose up -d
sleep 25
docker compose ps
docker compose exec web python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz/').read())"
docker run --rm --network proxy curlimages/curl -s -o /dev/null -w "%{http_code}\n" http://tpark-media/media/nope.jpg
```
Expected: `web` в статусе `healthy`; healthz печатает `b'ok'`; nginx отвечает `404` на несуществующий файл.

- [ ] **Step 4: Проверить импорт и бэкап в контейнере**

```bash
mkdir -p /tmp/tpark-legacy/images
cp old_version/T_Park.db /tmp/tpark-legacy/
docker compose run --rm -v /tmp/tpark-legacy:/legacy web python manage.py import_legacy --db /legacy/T_Park.db --images /legacy/images --price-csv /legacy/price.csv
./scripts/backup.sh
ls backups/*/
docker compose down
```
Expected: отчёт импорта (Категории: 13, Услуги: 109, …, предупреждения о пропущенных связях и сотрудниках); в `backups/<дата>/` лежат `../../../current_content/db.sqlite3` и `media.tar.gz`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore compose.yaml docker
git commit -m "Docker: образ на uv, compose с web и nginx для медиа во внешней сети прокси

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Прогон на реальных данных и документация

**Files:**
- Create: `CLAUDE.md`, `README.md`
- Modify: `docs/decisions.md` (статус: реализация)

**Interfaces:**
- Consumes: всё выше.

- [ ] **Step 1: Прогнать импорт реальной БД локально**

```bash
rm -f db.sqlite3 && rm -rf media
DEBUG=1 uv run manage.py migrate
mkdir -p /tmp/tpark-images
DEBUG=1 uv run manage.py import_legacy --db old_version/T_Park.db --images /tmp/tpark-images
```
Expected: Категории 13, Группы 3, Услуги 109, Услуги в категориях 93 (99 строк минус 6 ссылок на удалённые записи), Мероприятия 11, Отзывы 18, Партнёры 9, Телефоны 3, Инфо-страницы 1; предупреждения: 6 пропущенных связей, сотрудники, отсутствующие фото (папки images локально нет — это ожидаемо). Если какой-то счётчик отличается — разобраться, это несоответствие данных или ошибка маппинга, и записать вывод в отчёт задачи.

- [ ] **Step 2: Пройтись по сайту**

```bash
DEBUG=1 uv run manage.py createsuperuser
DEBUG=1 uv run manage.py tailwind runserver
```
Проверить: главная с группами; категория со списком услуг и ценами; услуга с отдельной страницей; `/category?category_id=<реальный id>` редиректит; `/info?info_id=11` → «Правила безопасности Т-парка»; админка открывает все разделы, телефоны с флагами WhatsApp/Telegram.

- [ ] **Step 3: CLAUDE.md и README.md для нового проекта**

`CLAUDE.md`:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Сайт Т-Парка (t-camp.ru) на Django 6.1: публичная витрина (шаблоны + Tailwind) и админка Unfold. Старая Flask-версия — в `old_version/` (только для справки и импорта, не менять). Спецификация — `docs/superpowers/specs/2026-10-08-django-rewrite-design.md`, журнал решений — `docs/decisions.md`. Весь пользовательский текст — на русском.

## Commands

```bash
uv sync                                   # зависимости (включая dev)
cp .env.example .env                      # DEBUG=1 для разработки
uv run manage.py migrate
uv run manage.py tailwind runserver       # dev-сервер + пересборка Tailwind
uv run pytest                             # все тесты
uv run pytest tests/test_pages.py::test_info_page   # один тест
uv run ruff check . && uv run ruff format .
uv run manage.py import_legacy --db old_version/T_Park.db --images <папка images со старого сервера> [--flush]
docker compose up -d --build              # продакшен (нужна внешняя сеть PROXY_NETWORK)
```

## Architecture

- `apps/core` — настройки сайта (синглтон `SiteSettings.load()` + `Phone` с флагами WhatsApp/Telegram), инфо-страницы, общие хелперы: `fields.py` (`HtmlField` — prose-editor с очисткой nh3; `photo_field` — пережатие при загрузке; `image_spec` — WebP-миниатюры), `files.py` (удаление файлов после коммита), `bulk_upload.py`, SEO, sitemap, 301-редиректы со старых URL, импорт (`legacy/`), `backup_db`.
- `apps/catalog` — `CategoryGroup` ↔ `Category` (M2M) и `Category` ↔ `Service` через `CategoryService` с полем порядка. Меню (`menu_groups`) приходит из контекст-процессора.
- `apps/content` — мероприятия (`upcoming()`/`past_visible()`), отзывы, партнёры, сотрудники, галерея.
- Порядок везде — `order` + перетаскивание Unfold (`ordering_field`). Неопубликованное — 404.
- Миниатюры в шаблонах — только через фильтр `obj|spec_url:"spec"` (не падает на отсутствующем файле).
- Фронт без Node и CDN: Tailwind через `django-tailwind-cli` (`tailwind/source.css` → `static/css/tailwind.css`), Alpine/Swiper/GLightbox — в `static/vendor/`.
- Продакшен: `web` (gunicorn + WhiteNoise, алиас `tpark-web`) и `media` (nginx, алиас `tpark-media`) во внешней сети прокси; тома `db` и `media`; бэкап — `scripts/backup.sh`.
```

`README.md`:

```markdown
# Т-Парк — t-camp.ru

Сайт [Т-Парка](https://t-camp.ru/): услуги, мероприятия, отзывы, галерея. Django 6.1, админка Unfold, SQLite, Tailwind.

Разработка, команды и архитектура — в [CLAUDE.md](CLAUDE.md). Спецификация — в [docs/](docs/).

## Продакшен

1. `cp .env.example .env`, заполнить `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PROXY_NETWORK`, `DEBUG=0`.
2. `docker compose up -d --build`, затем `docker compose exec web python manage.py createsuperuser`.
3. В reverse-proxy: `/media/` → `http://tpark-media:80`, остальное → `http://tpark-web:8000`, заголовок `X-Forwarded-Proto`.
4. Перенос данных: `docker compose run --rm -v /путь/к/старым/данным:/legacy web python manage.py import_legacy --db /legacy/T_Park.db --images /legacy/images`.
5. Бэкап по cron: `scripts/backup.sh`.
```

`docs/decisions.md`: строку статуса заменить на «Статус: спецификация утверждена, идёт реализация по плану `docs/superpowers/plans/2026-10-08-django-rewrite.md`.»

- [ ] **Step 4: Финальная проверка**

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pre-commit run --all-files
```
Expected: все тесты зелёные, ruff и pre-commit без ошибок.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/decisions.md
git commit -m "Документация нового проекта: CLAUDE.md, README, статус решений

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
