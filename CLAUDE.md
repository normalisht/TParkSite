# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Сайт Т-Парка (t-camp.ru) на Python 3.14 + Django 6.1: публичная витрина (шаблоны + Tailwind) и админка Unfold. Старая Flask-версия — в `old_version/` (только для справки и импорта, не менять; исключена из ruff и pre-commit). Спецификация — `docs/superpowers/specs/2026-10-08-django-rewrite-design.md`, журнал решений — `docs/decisions.md`, старый функционал — `docs/current-functionality.md`. Весь пользовательский текст — на русском.

## Layout

- `src/` — весь Django-проект: `pyproject.toml`/`uv.lock`, `manage.py`, `config/`, `apps/`, `templates/`, `static/`, `tailwind/`, `tests/`. Dev-окружение (`.venv`, `.env` из `src/.env.example`, `db.sqlite3`, `media/`) тоже живёт в `src/`.
- Корень — инфраструктура: `Dockerfile`, `compose.yaml`, `docker/`, `scripts/`, `.env.example` (продакшен, для compose), `.pre-commit-config.yaml`, `docs/`, `old_version/`.

## Commands

Python-команды запускаются из `src/`:

```bash
cd src
uv sync                                   # зависимости (включая dev)
cp .env.example .env                      # dev-окружение (DEBUG=1)
uv run manage.py migrate
uv run manage.py tailwind runserver       # dev-сервер + пересборка Tailwind (бинарник скачается в src/.django_tailwind_cli/)
uv run pytest                             # все тесты (settings: config.settings_test)
uv run pytest tests/test_pages.py::test_info_page   # один тест
uv run ruff check . && uv run ruff format .
uv run manage.py import_legacy --db ../old_version/T_Park.db --images <папка images со старого сервера> [--flush]
```

Из корня репозитория:

```bash
uv run --project src pre-commit run --all-files   # ruff в pre-commit закреплён той же версией, что в src/uv.lock; docs/ и old_version/ исключены
docker compose -f compose.dev.yaml up --build    # локально в Docker: http://localhost:8000, DEBUG=1, src/ примонтирован (hot reload + Tailwind watch)
docker compose -f compose.dev.yaml exec tpark-dev python manage.py createsuperuser
docker compose up -d --build                      # продакшен (корневой .env из .env.example, нужна внешняя сеть PROXY_NETWORK)
```

## Architecture

Пути ниже — относительно `src/`.

- `apps/core` — настройки сайта (синглтон `SiteSettings.load()` + `Phone` с флагами WhatsApp/Telegram, не более одного номера на флаг — ограничение в БД и `PhoneFormSet` в админке), инфо-страницы и общие хелперы:
  - `fields.py` — `HtmlField` (prose-editor с очисткой nh3; `sanitize_html` — та же очистка для импорта), `photo_field` (пережатие при загрузке), `image_spec` (WebP-миниатюры), `UploadTo` (случайные имена файлов);
  - `files.py` — удаление файлов при удалении/замене записи, только после коммита (`on_commit`), чтобы откат не терял файлы;
  - `maps.py` — поле встраиваемой Яндекс Карты (`MapEmbedURLField`: принимает код `<iframe>` или ссылку, только `yandex.ru/map-widget/`);
  - `bulk_upload.py` — загрузка фото пачкой в админке; `legacy_redirects.py` — 301 со старых URL; `sitemaps.py`, `seo.py`;
  - `legacy/` — `import_legacy` (одна транзакция, отказ на непустой БД без `--flush`, отчёт с предупреждениями); `backup_db` — снимок SQLite.
- `apps/catalog` — `CategoryGroup` ↔ `Category` (M2M) и `Category` ↔ `Service` через `CategoryService` с полем порядка. Меню (`menu_groups`) приходит из контекст-процессора; настройки и телефоны — из `apps.core.context_processors.site`.
- `apps/content` — мероприятия (`upcoming()` / `past_visible()`; страница `/events/<slug>/` и sitemap — только для `visible()`, slug из «заголовок + год», JSON-LD `schema.org/Event` через фильтр `ld_json`), отзывы (HTML), партнёры, сотрудники, галерея.
- Админки наследуются от `apps.core.admin_utils.SiteModelAdmin` (не напрямую от `unfold.admin.ModelAdmin`): она подключает `static/js/admin_unsaved.js` — предупреждение при уходе со страницы с несохранёнными изменениями (формы и списки с `list_editable`; встроенный `warn_unsaved_form` Unfold не ловит перетаскивание и списки).
- Перетаскивание файлов во все поля загрузки админки — `static/js/admin_dropzone.js`, подключён через `UNFOLD["SCRIPTS"]` (работает и на кастомных страницах вроде загрузки пачкой); рассчитан на разметку виджетов Unfold, поэтому свои файловые поля делаем на `UnfoldAdmin*FieldWidget` (как `MultipleImageInput`).
- У Unfold нет русской локали: недостающие строки переводятся в `locale/ru/LC_MESSAGES/django.po` (`LOCALE_PATHS`); после правки — `uv run manage.py compilemessages -l ru` (нужен gettext), `.mo` коммитится.
- Порядок везде — `order` + перетаскивание Unfold (`ordering_field`). Неопубликованное — 404.
- Миниатюры в шаблонах — только через фильтр `obj|spec_url:"spec"` (`{% load site_tags %}`): не падает на отсутствующем файле.
- Фронт без Node и CDN: Tailwind через `django-tailwind-cli` (`tailwind/source.css` → `static/css/tailwind.css`, не в git), Alpine/Swiper/GLightbox — vendored в `static/vendor/`. При обновлении vendored-JS убрать комментарий `sourceMappingURL` — иначе `collectstatic` с манифестом упадёт (ловит `tests/test_static.py`).
- Продакшен: образ собирается из `src/` (`.dockerignore` — allowlist), `tpark-web` (gunicorn + WhiteNoise) и `tpark-media` (nginx) — имена сервисов уникальны, т. к. они же DNS-имена в общей сети прокси; тома `db` и `media`; бэкап — `scripts/backup.sh` (cron на хосте).
