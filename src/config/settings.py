"""Настройки проекта. Значения, зависящие от окружения, читаются из переменных окружения
(локально — из файла .env в корне репозитория)."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy

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
# Главный домен сайта: с www.<CANONICAL_HOST> — 301 сюда (apps.core.middleware). Пусто — без редиректа.
CANONICAL_HOST = os.environ.get("CANONICAL_HOST", "").strip().lower()

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
    "apps.catalog",
    "apps.content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.CanonicalHostMiddleware",
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
                "apps.core.context_processors.site",
                "apps.catalog.context_processors.menu",
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
LOCALE_PATHS = [BASE_DIR / "locale"]  # перевод строк Unfold, у которого нет русской локали
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

TAILWIND_CLI_SRC_CSS = "tailwind/source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "31536000"))
    # http → https силами Django; включать, только если прокси передаёт X-Forwarded-Proto (иначе — петля редиректов).
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT")
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SECURE_CONTENT_TYPE_NOSNIFF = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}


def _nav(title: str, icon: str, url_name: str) -> dict:
    return {"title": title, "icon": icon, "link": reverse_lazy(url_name)}


UNFOLD = {
    "SITE_TITLE": "Т-Парк",
    "SITE_HEADER": "Т-Парк",
    "SITE_URL": "/",
    "SCRIPTS": [lambda request: static("js/admin_dropzone.js")],  # перетаскивание файлов во все поля загрузки
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "48x48", "href": lambda request: static("img/favicon.ico")},
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static("img/favicon.svg")},
        {"rel": "apple-touch-icon", "href": lambda request: static("img/apple-touch-icon.png")},
    ],
    # Цвета логотипа: зелёная ель — акцент, тёмно-синий текст — оттенок серых
    "COLORS": {
        "base": {
            "50": "oklch(98.5% .003 230)",
            "100": "oklch(96.7% .005 230)",
            "200": "oklch(92.8% .009 230)",
            "300": "oklch(87.2% .014 230)",
            "400": "oklch(70.7% .028 230)",
            "500": "oklch(55.1% .035 230)",
            "600": "oklch(44.6% .04 230)",
            "700": "oklch(37.3% .043 230)",
            "800": "oklch(27.8% .04 230)",
            "900": "oklch(21% .035 230)",
            "950": "oklch(13% .028 230)",
        },
        "primary": {
            "50": "oklch(98.2% .018 143)",
            "100": "oklch(96.2% .044 143)",
            "200": "oklch(92.5% .084 143)",
            "300": "oklch(87.1% .15 143)",
            "400": "oklch(79.2% .209 143)",
            "500": "oklch(72.3% .219 143)",
            "600": "oklch(62.7% .194 143)",
            "700": "oklch(52.7% .154 143)",
            "800": "oklch(44.8% .119 143)",
            "900": "oklch(39.3% .095 143)",
            "950": "oklch(26.6% .065 143)",
        },
    },
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Каталог",
                "items": [
                    _nav("Группы категорий", "workspaces", "admin:catalog_categorygroup_changelist"),
                    _nav("Категории", "category", "admin:catalog_category_changelist"),
                    _nav("Услуги", "inventory_2", "admin:catalog_service_changelist"),
                ],
            },
            {
                "title": "Контент",
                "separator": True,
                "items": [
                    _nav("Мероприятия", "event", "admin:content_event_changelist"),
                    _nav("Отзывы", "reviews", "admin:content_review_changelist"),
                    _nav("Галерея", "photo_library", "admin:content_galleryphoto_changelist"),
                    _nav("Партнёры", "handshake", "admin:content_partner_changelist"),
                ],
            },
            {
                "title": "Сайт",
                "separator": True,
                "items": [
                    _nav("Настройки сайта", "settings", "admin:core_sitesettings_changelist"),
                    _nav("Инфо-страницы", "description", "admin:core_infopage_changelist"),
                ],
            },
            {
                "title": "Доступ",
                "separator": True,
                "items": [
                    _nav("Пользователи", "person", "admin:auth_user_changelist"),
                    _nav("Группы", "group", "admin:auth_group_changelist"),
                ],
            },
        ],
    },
}
