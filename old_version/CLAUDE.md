# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

> Это **старая** Flask-версия, перенесённая в `old_version/` перед переписыванием на Django. Используется как источник данных для миграции и справка по функционалу (`../docs/current-functionality.md`). Команды ниже запускаются из `old_version/`.

Сайт Т-Парка (t-camp.ru): публичная витрина услуг/категорий/мероприятий/отзывов + самописная админка для их редактирования. Стек: Flask 2.1, Flask-SQLAlchemy 2.5 (SQLAlchemy 1.4), SQLite, Jinja2, jQuery. Весь UI и комментарии в коде — на русском.

## Commands

```bash
pip install -r requirements.txt     # зависимости (версии старые: Flask 2.1, Pillow 8.3)
flask run                            # dev-сервер; FLASK_APP=main.py задан в .flaskenv
gunicorn main:app                    # прод (Procfile)
flask shell                          # shell context содержит `db`
pre-commit run --all-files           # ruff check --fix + ruff format + базовые хуки
ruff check . && ruff format .        # линт/формат напрямую
```

Тестов в репозитории нет. Директории `migrations/` нет (в `.gitignore`), хотя Flask-Migrate подключён — схема живёт прямо в закоммиченном `T_Park.db`.

## Architecture

- `main.py` → `app.create_app()` (application factory в `app/__init__.py`). Три blueprint'а:
  - `app/main` — публичные страницы (`/`, `/category`, `/category/service`, `/events`, `/reviews`, `/gallery`, `/contacts`, `/info`). Главная рендерит `main/new_main.html` (не `main/main.html`).
  - `app/admin_panel` — админка под `/admin_panel`, Flask-Login (`Admin.check_password` сравнивает пароль в открытом виде). Почти вся логика — в одном большом `routes.py` (~1000 строк): обработка форм, загрузка/удаление/переименование фото.
  - `app/errors` — обработчики 404/500.
- `app/models.py` — все модели. Ключевые связи many-to-many через явные таблицы-связки с полем порядка `number`:
  - `Type` ←`CategoryType`→ `Category` (группировка категорий на главной);
  - `Category` ←`ServiceCategory`→ `Service`.
  - `status` у `Category`/`Service`/`Text` — видимость для клиентов.
- `Text` — key-value хранилище контента сайта: записи ищутся по `title` (`main_text`, `address`, `geolocation`, `phone_numbers`, `vk`, `insta` и т.д., см. `app/main/functions.py`). Отсутствие записи ломает страницу (`.first().text` на `None`).

### Изображения

Картинки не хранятся в БД — только на диске в `app/static/images/` (в `.gitignore`, локально отсутствует), пути захардкожены относительно корня репо (`"app/static/images/..."`), поэтому приложение нужно запускать из корня. Раскладка: `category/<id>/`, `category/preview/<id>.jpg`, `service/<id>/`, `events/<id>.jpg`, `comments/<id>.jpg`, `gallery/`. Файлы в папках пронумерованы (`1.jpg`, `2.jpg`, …); после удаления админка перенумеровывает их в два прохода (сначала префикс `file_`, чтобы не перетереть) — та же логика в разовом скрипте `fix_name_for_service_images.py`. При загрузке фото сжимаются через Pillow (`compress_img` в `admin_panel/routes.py`, дубль в `resize_photo.py`); используется `Image.ANTIALIAS`, удалённый в Pillow ≥10.

### Frontend

Шаблоны в `app/templates/{main,admin_panel,errors}`, статика в `app/static/<страница>/` (отдаётся по `/app/static`). Мобильная/десктопная версии выбираются на клиенте: `static/base.js` через `mobile-detect.min.js` динамически подключает `*_phone.css`/`*_desktop.css` и `base_desktop.js`. Поэтому CSS-правки обычно нужны в обоих вариантах файла.

## Gotchas

- `app/main/routes.py` создаёт отдельный `create_engine("sqlite:///T_Park.db")` по относительному пути в обход `Config.SQLALCHEMY_DATABASE_URI`.
- `config.py` и `.flaskenv` содержат реальные почтовые креды; логирование ошибок по SMTP и в `logs/main.log` включается только вне debug/testing.
- `app/templates/admin_panel/Шаблон.html` — заготовка-шаблон для новых страниц админки.
