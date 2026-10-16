# Gunicorn для продакшена — общий для Docker и systemd: gunicorn сам читает ./gunicorn.conf.py из рабочего каталога
# (в образе — /app, под systemd — src/). Аргументы командной строки важнее этого файла.
import os

wsgi_app = "config.wsgi:application"

# Синхронные воркеры, по процессу на запрос. На 1 ГБ памяти — не больше 2–3: пережатие фото держит их в памяти.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
# Загрузка фото пачкой пережимает их прямо в запросе (у nginx proxy_read_timeout тоже 120 с).
timeout = 120
graceful_timeout = 30
# Перезапуск воркера через ~1000 запросов: память после пережатия фото (Pillow) возвращается системе, утечки не копятся.
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"

# Под systemd есть RUNTIME_DIRECTORY (RuntimeDirectory юнита, /run/<сервис>/: создаётся при старте, удаляется
# при остановке) — слушаем unix-сокет для nginx; в Docker — TCP-порт для прокси.
_runtime = os.environ.get("RUNTIME_DIRECTORY")
if _runtime:
    bind = f"unix:{_runtime}/gunicorn.sock"
    # Сокет 0666, как chmod-socket = 666 у uwsgi: nginx (www-data) должен в него писать.
    umask = 0o111
    # Управление на лету (gunicornc), доступно только владельцу.
    control_socket = f"{_runtime}/gunicorn.ctl"
    # Без preload_app: make service-deploy обновляет код плавным перезапуском (HUP), а с preload воркеры
    # после HUP форкаются от мастера со старым кодом.
else:
    bind = "0.0.0.0:8000"
    # Образ только для чтения: сокету управления негде лежать.
    control_socket_disable = True
    # Django импортируется один раз в мастере: воркеры делят его память (copy-on-write; на 2 воркерах — около 20 МБ)
    # и после max_requests стартуют без повторного импорта. Новый код в контейнере — только с новым контейнером.
    preload_app = True
