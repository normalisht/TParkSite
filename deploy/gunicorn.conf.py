# Gunicorn для запуска без Docker (systemd, deploy/tpark.service.in) — замена uwsgi-ini старого сайта.
# Рабочий каталог — src/; переменные окружения — из src/.env (EnvironmentFile в юните).
import os

wsgi_app = "config.wsgi:application"

# Сокет — в /run/<сервис>/ (RuntimeDirectory юнита: создаётся при старте, удаляется при остановке).
# umask 0o111 — сокет 0666, как chmod-socket = 666 у uwsgi: nginx (www-data) должен в него писать.
_runtime = os.environ.get("RUNTIME_DIRECTORY", "/run/tpark")
bind = f"unix:{_runtime}/gunicorn.sock"
umask = 0o111
# Управление на лету (gunicornc), доступно только владельцу.
control_socket = f"{_runtime}/gunicorn.ctl"

# Синхронные воркеры, по процессу на запрос. На 1 ГБ памяти — не больше 2–3: пережатие фото держит их в памяти.
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
# Загрузка фото пачкой пережимает их прямо в запросе (у nginx proxy_read_timeout тоже 120 с).
timeout = 120
graceful_timeout = 30
# Перезапуск воркера через ~1000 запросов: утечки памяти не копятся.
max_requests = 1000
max_requests_jitter = 100

# Логи — в journald (journalctl -u <сервис>).
accesslog = "-"
errorlog = "-"
