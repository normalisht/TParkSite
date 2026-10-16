# Команды проекта. Python-команды выполняются в src/ через uv.
# make help — список целей.

SRC := src
MANAGE := cd $(SRC) && uv run manage.py
DEV_COMPOSE := docker compose -f compose.dev.yaml
# Продакшен без Docker: только основные зависимости, uv.lock не меняется.
PROD_MANAGE := cd $(SRC) && uv run --frozen --no-dev manage.py
SERVICE ?= tpark
SERVICE_USER ?= $(shell id -un)
SERVICE_GROUP ?= $(shell id -gn)
# nginx на хосте: deploy/nginx-site.conf собирается из шаблона, в sites-available — symlink на него.
NGINX_SITE ?= $(SERVICE)
NGINX_CONF := deploy/nginx-site.conf
NGINX_SERVER_NAME ?= t-camp.ru www.t-camp.ru

.DEFAULT_GOAL := help
.PHONY: help install env migrate run superuser shell test coverage lint format check e2e pre-commit \
	messages tailwind collectstatic import-legacy \
	dev dev-down dev-logs dev-superuser \
	build up down restart logs prod-superuser backup \
	service-install service-deploy service-restart service-status service-logs service-superuser service-backup \
	nginx-install nginx-update nginx-uninstall nginx-render

help: ## Показать список команд
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## --- Локальная разработка (без Docker) ---

install: env ## Установить зависимости и pre-commit-хуки
	cd $(SRC) && uv sync
	uv run --project $(SRC) pre-commit install

env: ## Создать src/.env из примера (если ещё нет)
	@test -f $(SRC)/.env || (cp $(SRC)/.env.example $(SRC)/.env && echo "Создан $(SRC)/.env")

migrate: ## Применить миграции
	$(MANAGE) migrate

run: migrate ## Dev-сервер + пересборка Tailwind: http://localhost:8000
	$(MANAGE) tailwind runserver

superuser: ## Создать администратора
	$(MANAGE) createsuperuser

shell: ## Django shell
	$(MANAGE) shell

test: ## Тесты (make test ARGS="tests/test_pages.py -x")
	cd $(SRC) && uv run pytest $(ARGS)

coverage: ## Тесты с покрытием: отчёт в терминале и src/htmlcov/index.html
	cd $(SRC) && uv run pytest --cov --cov-report=term --cov-report=html $(ARGS)

lint: ## Проверка ruff
	cd $(SRC) && uv run ruff check . && uv run ruff format --check .

format: ## Автоисправление и форматирование ruff
	cd $(SRC) && uv run ruff check --fix . && uv run ruff format .

check: lint test ## Линтер + тесты

e2e: ## Браузерные тесты вёрстки (один раз: cd src && uv sync --group e2e && uv run --group e2e playwright install chromium)
	cd $(SRC) && uv run manage.py tailwind build && uv run --group e2e pytest tests/e2e -m e2e $(ARGS)

pre-commit: ## Все pre-commit-хуки по всем файлам
	uv run --project $(SRC) pre-commit run --all-files

messages: ## Скомпилировать переводы (нужен gettext)
	$(MANAGE) compilemessages -l ru

tailwind: ## Собрать CSS Tailwind
	$(MANAGE) tailwind build

collectstatic: tailwind ## Собрать статику (как в продакшене)
	$(MANAGE) collectstatic --noinput

import-legacy: ## Импорт со старого сайта: make import-legacy IMAGES=<папка> [FLUSH=1]
	@test -n "$(IMAGES)" || (echo "Укажите IMAGES=<папка images со старого сервера>" && exit 1)
	$(MANAGE) import_legacy --db ../old_version/T_Park.db --images $(abspath $(IMAGES)) $(if $(FLUSH),--flush)

## --- Локально в Docker ---

dev: ## Поднять dev-контейнер (http://localhost:8000, hot reload)
	$(DEV_COMPOSE) up --build --renew-anon-volumes

dev-down: ## Остановить dev-контейнер
	$(DEV_COMPOSE) down

dev-logs: ## Логи dev-контейнера
	$(DEV_COMPOSE) logs -f

dev-superuser: ## Создать администратора в dev-контейнере
	$(DEV_COMPOSE) exec tpark-dev python manage.py createsuperuser

## --- Продакшен (корневой .env) ---

build: ## Собрать продакшен-образ
	docker compose build

up: ## Сборка, бэкап (если сайт уже запущен), запуск продакшена в фоне
	docker compose build
	@if [ -n "$$(docker compose ps -q tpark-web 2>/dev/null)" ]; then ./scripts/backup.sh; else echo "Сайт не запущен — бэкап пропущен"; fi
	docker compose up -d

down: ## Остановить продакшен
	docker compose down

restart: ## Перезапустить продакшен
	docker compose restart

logs: ## Логи продакшена
	docker compose logs -f --tail=200

prod-superuser: ## Создать администратора в продакшене
	docker compose exec tpark-web python manage.py createsuperuser

backup: ## Бэкап БД и медиа в backups/
	./scripts/backup.sh

## --- Продакшен без Docker (systemd + gunicorn; настройки — src/.env, запускать от SERVICE_USER) ---

service-install: ## Установить systemd-юнит (SERVICE=tpark, пользователь — текущий)
	@test -f $(SRC)/.env || (echo "Нет $(SRC)/.env: cp .env.example $(SRC)/.env и заполнить (DEBUG=0, SECRET_KEY, пути к БД и медиа)" && exit 1)
	sed -e 's|@SERVICE@|$(SERVICE)|g' -e 's|@USER@|$(SERVICE_USER)|g' -e 's|@GROUP@|$(SERVICE_GROUP)|g' \
		-e 's|@SRC_DIR@|$(CURDIR)/$(SRC)|g' deploy/tpark.service.in \
		| sudo tee /etc/systemd/system/$(SERVICE).service > /dev/null
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE)
	@echo "Юнит $(SERVICE) установлен, сокет — /run/$(SERVICE)/gunicorn.sock. Дальше: make service-deploy"

service-deploy: ## Обновить сайт: зависимости, статика, бэкап, миграции, плавный перезапуск, миниатюры
	cd $(SRC) && uv sync --frozen --no-dev
	$(PROD_MANAGE) tailwind build
	$(PROD_MANAGE) collectstatic --noinput
	@if systemctl is-active --quiet $(SERVICE); then ./scripts/backup.sh --host; else echo "Сайт не запущен — бэкап пропущен"; fi
	$(PROD_MANAGE) migrate --noinput
	sudo systemctl reload-or-restart $(SERVICE)
	@if [ -L /etc/nginx/sites-available/$(NGINX_SITE) ]; then $(MAKE) --no-print-directory nginx-update; else echo "nginx-сайт не подключён (make nginx-install) — пропущено"; fi
	@# Сайт уже работает: недостающие миниатюры ImageKit создаёт и сам при показе, здесь — заранее и с низким приоритетом.
	cd $(SRC) && nice -n 10 uv run --frozen --no-dev manage.py generate_missing_images
	cd $(SRC) && nice -n 10 uv run --frozen --no-dev manage.py prune_image_cache

service-restart: ## Полный перезапуск (после обновления Python или gunicorn)
	sudo systemctl restart $(SERVICE)

service-status: ## Состояние сервиса
	systemctl status $(SERVICE) --no-pager

service-logs: ## Логи сервиса (journald)
	journalctl -u $(SERVICE) -f -n 200

service-superuser: ## Создать администратора
	$(PROD_MANAGE) createsuperuser

service-backup: ## Бэкап БД и медиа в backups/
	./scripts/backup.sh --host

nginx-install: ## Подключить сайт к nginx: symlink в sites-available и sites-enabled на собранный deploy/nginx-site.conf
	@for f in /etc/nginx/sites-available/$(NGINX_SITE) /etc/nginx/sites-enabled/$(NGINX_SITE); do \
		if [ -e "$$f" ] && [ ! -L "$$f" ]; then echo "$$f — обычный файл, а не symlink: перенесите его и повторите"; exit 1; fi; \
	done
	$(MAKE) --no-print-directory nginx-render
	sudo ln -sfn $(CURDIR)/$(NGINX_CONF) /etc/nginx/sites-available/$(NGINX_SITE)
	sudo ln -sfn /etc/nginx/sites-available/$(NGINX_SITE) /etc/nginx/sites-enabled/$(NGINX_SITE)
	@if sudo nginx -t; then sudo systemctl reload nginx; \
	else sudo rm -f /etc/nginx/sites-enabled/$(NGINX_SITE); echo "Конфиг не прошёл nginx -t — сайт отключён из sites-enabled"; exit 1; fi

nginx-update: ## Пересобрать nginx-конфиг из шаблона, проверить и перечитать (при ошибке — вернуть прежний)
	@test -L /etc/nginx/sites-available/$(NGINX_SITE) || (echo "Сайт не подключён: make nginx-install" && exit 1)
	@if [ -f $(NGINX_CONF) ]; then cp -p $(NGINX_CONF) $(NGINX_CONF).bak; fi
	$(MAKE) --no-print-directory nginx-render
	@if sudo nginx -t; then sudo systemctl reload nginx && rm -f $(NGINX_CONF).bak; \
	else [ -f $(NGINX_CONF).bak ] && mv $(NGINX_CONF).bak $(NGINX_CONF); echo "Новый конфиг не прошёл nginx -t — оставлен прежний"; exit 1; fi

nginx-uninstall: ## Отключить сайт от nginx (удалить symlink'и)
	sudo rm -f /etc/nginx/sites-enabled/$(NGINX_SITE)
	@if [ -L /etc/nginx/sites-available/$(NGINX_SITE) ]; then sudo rm -f /etc/nginx/sites-available/$(NGINX_SITE); fi
	sudo nginx -t && sudo systemctl reload nginx

# Собирает deploy/nginx-site.conf: MEDIA_ROOT и CANONICAL_HOST — из настроек Django (src/.env).
nginx-render:
	@set -e; \
	vals="$$($(PROD_MANAGE) shell -c 'from django.conf import settings; print(f"MEDIA_ROOT={settings.MEDIA_ROOT}"); print(f"HOST={settings.CANONICAL_HOST}")')"; \
	media="$$(echo "$$vals" | sed -n 's/^MEDIA_ROOT=//p')"; host="$$(echo "$$vals" | sed -n 's/^HOST=//p')"; \
	test -n "$$host" || (echo "Пустой CANONICAL_HOST в $(SRC)/.env" && exit 1); \
	cert="$${NGINX_CERT_DIR:-/etc/letsencrypt/live/$$host}"; \
	sed -e 's|@SERVICE@|$(SERVICE)|g' -e "s|@MEDIA_ROOT@|$$media|g" -e "s|@CANONICAL_HOST@|$$host|g" \
		-e 's|@SERVER_NAME@|$(NGINX_SERVER_NAME)|g' -e "s|@CERT_DIR@|$$cert|g" deploy/nginx-site.conf.in > $(NGINX_CONF); \
	echo "Собран $(NGINX_CONF): медиа — $$media, домен — $$host, сертификат — $$cert"
