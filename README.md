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

Если общего reverse-proxy на сервере нет — `compose.nginx.yaml`: nginx сам слушает 80/443, терминирует HTTPS, отдаёт `/media/` и проксирует остальное в gunicorn (конфиг — `docker/nginx.conf.template`). `PROXY_NETWORK` не нужен. Сертификат Let's Encrypt nginx выпускает и продлевает сам (модуль `ngx_http_acme_module`, проверка HTTP-01), certbot не нужен.

1. DNS всех доменов из `SERVER_NAME` указывает на сервер, порты 80 и 443 открыты.
2. В `.env`: `COMPOSE_FILE=compose.nginx.yaml` (тогда `docker compose`, `make up`/`logs`/`prod-superuser` и `scripts/backup.sh` работают с этим файлом без `-f`), `ACME_EMAIL`, при другом домене — `SERVER_NAME` (через пробел; см. `.env.example`).
3. Данные лежат в каталогах на хосте (не в томах Docker): БД — `data/db/db.sqlite3`, медиа — `data/media/` (другие пути — `DB_DIR`/`MEDIA_DIR` в `.env`). Чтобы поднять сайт с готовыми данными, положить их туда до запуска, например из бэкапа `scripts/backup.sh`:
   ```bash
   mkdir -p data/db
   cp backups/<дата>/db.sqlite3 data/db/db.sqlite3
   tar -xzf backups/<дата>/media.tar.gz -C data     # распакуется в data/media/
   sudo chown -R 1000:1000 data                     # контейнер работает от uid 1000
   ```
   Миграции применяются при старте. Пустые каталоги тоже подойдут (новый сайт), но их владелец тоже должен быть uid 1000 — иначе Docker создаст их от root и gunicorn не сможет писать.
4. `docker compose up -d --build`, дальше — как выше (createsuperuser, импорт, бэкап). Сертификат появится через несколько секунд после старта; ход выпуска — в `docker compose logs tpark-nginx`.

Ключ аккаунта и сертификаты лежат в томе `acme` — не удалять, иначе упрёмся в лимиты Let's Encrypt. Для отладки — `ACME_SERVER` с тестовым сервером (браузер такому сертификату не доверяет); при возврате на боевой удалить том `acme`.
