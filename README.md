# Т-Парк — t-camp.ru

Сайт [Т-Парка](https://t-camp.ru/): услуги, мероприятия, отзывы, галерея. Python 3.14, Django 6.1, админка Unfold, SQLite, Tailwind.

Django-проект — в [src/](src/), в корне — инфраструктура (Docker, скрипты). Разработка, команды и архитектура — в [CLAUDE.md](CLAUDE.md). Спецификация и журнал решений — в [docs/](docs/). Старая Flask-версия — в [old_version/](old_version/).

## Продакшен

1. В корне репозитория: `cp .env.example .env`, заполнить `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PROXY_NETWORK`, `DEBUG=0`.
2. `make up` (собирает образ, затем делает бэкап работающего сайта и запускает новый: при старте контейнера применяются миграции), затем `docker compose exec tpark-web python manage.py createsuperuser`.
3. В reverse-proxy: `/media/` → `http://tpark-media:80`, остальное → `http://tpark-web:8000`, передавать заголовок `X-Forwarded-Proto`.

   Требования к общему прокси: передавать `X-Real-IP $remote_addr` (перезаписывая заголовок клиента) и `X-Forwarded-Proto`, сжимать HTML (`gzip on`), разрешить минимум 120 секунд для ответа (`proxy_read_timeout 120s`) и тела запроса до 200 МБ (`client_max_body_size 200m` — для пакетной загрузки фото в админке).

   Дополнительно прокси должен:
   - отвечать отказом на запросы с чужим `Host` и по голому IP (Django всегда пускает `localhost`/`127.0.0.1`, поэтому такие запросы иначе попадут в canonical и `robots.txt`);
   - одним редиректом вести `http://` (в том числе `www`) на `https://${CANONICAL_HOST}`;
   - ограничивать частоту запросов к `/admin/login/` (как `limit_req` в `docker/nginx.conf.template`).

   Про `X-Real-IP`: если прокси не перезаписывает заголовок адресом клиента, клиент выставляет его сам, и защита от подбора пароля обходится целиком. Если прокси заголовок не передаёт вовсе, все запросы выглядят как с одного адреса, и любой желающий может заблокировать вход конкретному администратору на 30 минут (блокировка идёт по паре «логин + IP»).

   Если администратор заблокирован после 5 неудачных попыток входа (30 минут): `docker compose exec tpark-web python manage.py axes_reset`.
4. Перенос данных: `docker compose run --rm -v /путь/к/старым/данным:/legacy tpark-web python manage.py import_legacy --db /legacy/T_Park.db --images /legacy/images --price-csv /legacy/price.csv` (повторный прогон — с `--flush`).
5. Бэкап по cron: `scripts/backup.sh` (хранит последние `BACKUP_KEEP` копий, по умолчанию 14).
6. Миниатюры фото создаются в фоне сразу после загрузки фото, а при старте контейнера — недостающие (`generateimages`), после чего ненужные удаляются (`prune_image_cache`: миниатюры старых размеров и качества; файлы моложе часа не трогает, при пустой базе не делает ничего). Миниатюры удалённых и заменённых фото удаляются сразу. Если поменялись размеры или качество миниатюр (`src/apps/core/fields.py`, модели), первые минуты после деплоя, пока идёт генерация, часть фото показывается без AVIF или оригиналом: один запрос пережимает миниатюры не дольше 2 секунд (`REQUEST_GENERATION_BUDGET` в `src/apps/core/images.py`), остальное досоздают фон и следующие запросы. Папку `media/CACHE` вручную целиком не удалять: до перезапуска сайт будет отдавать битые картинки; посмотреть, что удалит очистка, — `docker compose exec tpark-web python manage.py prune_image_cache --dry-run`.

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
4. `make up` (собирает образ, затем делает бэкап работающего сайта и запускает новый: при старте контейнера применяются миграции), дальше — как выше (createsuperuser, импорт, бэкап). Сертификат появится через несколько секунд после старта; ход выпуска — в `docker compose logs tpark-nginx`.

Что делает конфиг: `http://` (и `www`) одним редиректом ведёт на `https://${CANONICAL_HOST}` (по умолчанию `t-camp.ru`, задаётся в `.env`); запросы с чужим Host и по IP закрываются без ответа; вход в админку (`/admin/login/`) ограничен 10 попытками в минуту с адреса, дальше — 429.

Проверка после деплоя:
- `docker compose exec tpark-nginx nginx -t` — конфиг без ошибок;
- `curl -sI http://www.t-camp.ru/contacts/` — один ответ `301` сразу на `https://t-camp.ru/contacts/`;
- `curl -sI http://<IP сервера>/` — соединение закрыто без ответа (`Empty reply from server`);
- `curl -sI http://t-camp.ru/.well-known/acme-challenge/test` — ответ `301` от nginx, а не обрыв соединения: проверка Let's Encrypt проходит.

Ключ аккаунта и сертификаты лежат в томе `acme` — не удалять, иначе упрёмся в лимиты Let's Encrypt. Для отладки — `ACME_SERVER` с тестовым сервером (браузер такому сертификату не доверяет); при возврате на боевой удалить том `acme`.
