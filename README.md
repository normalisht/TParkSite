# Т-Парк — t-camp.ru

Сайт [Т-Парка](https://t-camp.ru/): услуги, мероприятия, отзывы, галерея. Python 3.14, Django 6.1, админка Unfold, SQLite, Tailwind.

Разработка, команды и архитектура — в [CLAUDE.md](CLAUDE.md). Спецификация и журнал решений — в [docs/](docs/). Старая Flask-версия — в [old_version/](old_version/).

## Продакшен

1. `cp .env.example .env`, заполнить `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PROXY_NETWORK`, `DEBUG=0`.
2. `docker compose up -d --build`, затем `docker compose exec web python manage.py createsuperuser`.
3. В reverse-proxy: `/media/` → `http://tpark-media:80`, остальное → `http://tpark-web:8000`, передавать заголовок `X-Forwarded-Proto`.
4. Перенос данных: `docker compose run --rm -v /путь/к/старым/данным:/legacy web python manage.py import_legacy --db /legacy/T_Park.db --images /legacy/images --price-csv /legacy/price.csv` (повторный прогон — с `--flush`).
5. Бэкап по cron: `scripts/backup.sh` (хранит последние `BACKUP_KEEP` копий, по умолчанию 14).
