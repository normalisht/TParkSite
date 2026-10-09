# Команды проекта. Python-команды выполняются в src/ через uv.
# make help — список целей.

SRC := src
MANAGE := cd $(SRC) && uv run manage.py
DEV_COMPOSE := docker compose -f compose.dev.yaml

.DEFAULT_GOAL := help
.PHONY: help install env migrate run superuser shell test lint format check pre-commit \
	messages tailwind collectstatic import-legacy \
	dev dev-down dev-logs dev-superuser \
	build up down restart logs prod-superuser backup

help: ## Показать список команд
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

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

lint: ## Проверка ruff
	cd $(SRC) && uv run ruff check . && uv run ruff format --check .

format: ## Автоисправление и форматирование ruff
	cd $(SRC) && uv run ruff check --fix . && uv run ruff format .

check: lint test ## Линтер + тесты

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
	$(DEV_COMPOSE) up --build

dev-down: ## Остановить dev-контейнер
	$(DEV_COMPOSE) down

dev-logs: ## Логи dev-контейнера
	$(DEV_COMPOSE) logs -f

dev-superuser: ## Создать администратора в dev-контейнере
	$(DEV_COMPOSE) exec tpark-dev python manage.py createsuperuser

## --- Продакшен (корневой .env) ---

build: ## Собрать продакшен-образ
	docker compose build

up: ## Собрать и запустить продакшен в фоне
	docker compose up -d --build

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
