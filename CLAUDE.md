# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Сайт Т-Парка (t-camp.ru) на Python 3.14 + Django 6.1: публичная витрина (шаблоны + Tailwind) и админка Unfold. Старая Flask-версия — в `old_version/` (только для справки и импорта, не менять; исключена из ruff и pre-commit). Спецификация — `docs/superpowers/specs/2026-10-08-django-rewrite-design.md`, журнал решений — `docs/decisions.md`, старый функционал — `docs/current-functionality.md`. Весь пользовательский текст — на русском.

## Commands

```bash
uv sync                                   # зависимости (включая dev)
cp .env.example .env                      # затем поставить DEBUG=1 для разработки (в примере DEBUG=0 — продакшен-безопасно)
uv run manage.py migrate
uv run manage.py tailwind runserver       # dev-сервер + пересборка Tailwind (бинарник скачается в .django_tailwind_cli/)
uv run pytest                             # все тесты (settings: config.settings_test)
uv run pytest tests/test_pages.py::test_info_page   # один тест
uv run ruff check . && uv run ruff format .
uv run pre-commit run --all-files         # ruff в pre-commit закреплён той же версией, что в uv.lock
uv run manage.py import_legacy --db old_version/T_Park.db --images <папка images со старого сервера> [--flush]
docker compose up -d --build              # продакшен (нужна внешняя сеть PROXY_NETWORK из .env)
```

## Architecture

- `apps/core` — настройки сайта (синглтон `SiteSettings.load()` + `Phone` с флагами WhatsApp/Telegram, не более одного номера на флаг — ограничение в БД и `PhoneFormSet` в админке), инфо-страницы и общие хелперы:
  - `fields.py` — `HtmlField` (prose-editor с очисткой nh3; `sanitize_html` — та же очистка для импорта), `photo_field` (пережатие при загрузке), `image_spec` (WebP-миниатюры), `UploadTo` (случайные имена файлов);
  - `files.py` — удаление файлов при удалении/замене записи, только после коммита (`on_commit`), чтобы откат не терял файлы;
  - `bulk_upload.py` — загрузка фото пачкой в админке; `legacy_redirects.py` — 301 со старых URL; `sitemaps.py`, `seo.py`;
  - `legacy/` — `import_legacy` (одна транзакция, отказ на непустой БД без `--flush`, отчёт с предупреждениями); `backup_db` — снимок SQLite.
- `apps/catalog` — `CategoryGroup` ↔ `Category` (M2M) и `Category` ↔ `Service` через `CategoryService` с полем порядка. Меню (`menu_groups`) приходит из контекст-процессора; настройки и телефоны — из `apps.core.context_processors.site`.
- `apps/content` — мероприятия (`upcoming()` / `past_visible()`), отзывы (HTML), партнёры, сотрудники, галерея.
- Порядок везде — `order` + перетаскивание Unfold (`ordering_field`). Неопубликованное — 404.
- Миниатюры в шаблонах — только через фильтр `obj|spec_url:"spec"` (`{% load site_tags %}`): не падает на отсутствующем файле.
- Фронт без Node и CDN: Tailwind через `django-tailwind-cli` (`tailwind/source.css` → `static/css/tailwind.css`, не в git), Alpine/Swiper/GLightbox — vendored в `static/vendor/`. При обновлении vendored-JS убрать комментарий `sourceMappingURL` — иначе `collectstatic` с манифестом упадёт (ловит `tests/test_static.py`).
- Продакшен: `tpark-web` (gunicorn + WhiteNoise) и `tpark-media` (nginx) — имена сервисов уникальны, т. к. они же DNS-имена в общей сети прокси; тома `db` и `media`; бэкап — `scripts/backup.sh` (cron на хосте).
