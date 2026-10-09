# Т-Парк — t-camp.ru

Сайт [Т-Парка](https://t-camp.ru/): услуги, мероприятия, отзывы, галерея. Python 3.14, Django 6.1, админка Unfold, SQLite, Tailwind.

Django-проект — в [src/](src/), в корне — инфраструктура (Docker, скрипты). Разработка, команды и архитектура — в [CLAUDE.md](CLAUDE.md). Спецификация и журнал решений — в [docs/](docs/). Старая Flask-версия — в [old_version/](old_version/).

## Продакшен

1. В корне репозитория: `cp .env.example .env`, заполнить `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PROXY_NETWORK`, `DEBUG=0`.
2. `docker compose up -d --build`, затем `docker compose exec tpark-web python manage.py createsuperuser`.
3. В reverse-proxy: `/media/` → `http://tpark-media:80`, остальное → `http://tpark-web:8000`, передавать заголовок `X-Forwarded-Proto`.
4. Перенос данных: `docker compose run --rm -v /путь/к/старым/данным:/legacy tpark-web python manage.py import_legacy --db /legacy/T_Park.db --images /legacy/images --price-csv /legacy/price.csv` (повторный прогон — с `--flush`).
5. Бэкап по cron: `scripts/backup.sh` (хранит последние `BACKUP_KEEP` копий, по умолчанию 14).

### Вариант со своим nginx

Если общего reverse-proxy на сервере нет — `compose.nginx.yaml`: nginx сам слушает 80/443, терминирует HTTPS, отдаёт `/media/` и проксирует остальное в gunicorn (конфиг — `docker/nginx.conf.template`). `PROXY_NETWORK` не нужен.

1. В `.env` добавить `COMPOSE_FILE=compose.nginx.yaml` (тогда `docker compose`, `make up`/`logs`/`prod-superuser` и `scripts/backup.sh` работают с этим файлом без `-f`); при необходимости — `SERVER_NAME`, `CERT_NAME` и пути к сертификатам (см. `.env.example`).
2. Первый выпуск сертификата, пока порт 80 свободен: `certbot certonly --standalone -d t-camp.ru -d www.t-camp.ru`.
3. `docker compose up -d --build`, дальше — как выше (createsuperuser, импорт, бэкап).
4. Продление — через webroot, без остановки nginx: в `/etc/letsencrypt/renewal/t-camp.ru.conf` выставить `authenticator = webroot` и `webroot_path = /var/www/certbot`, а перезагрузку nginx — deploy-hook'ом: `certbot renew --deploy-hook "cd /srv/tpark && docker compose exec -T tpark-nginx nginx -s reload"`.
