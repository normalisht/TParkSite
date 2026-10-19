#!/usr/bin/env bash
# Бэкап продакшена: снимок SQLite + архив медиа. Запуск из cron на хосте, например:
#   15 3 * * * cd /srv/tpark && ./scripts/backup.sh >> backups/backup.log 2>&1
# Сайт без Docker (systemd, make service-*) — с ключом --host: ./scripts/backup.sh --host
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP="${BACKUP_KEEP:-14}"
DEST="backups/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$DEST"

if [ "${1:-}" = "--host" ]; then
  ROOT="$(pwd)"
  (cd src && uv run --frozen --no-dev manage.py backup_db "$ROOT/$DEST/db.sqlite3")
  MEDIA="$(cd src && uv run --frozen --no-dev manage.py shell -c 'from django.conf import settings; print(settings.MEDIA_ROOT)')"
  tar -czf "$DEST/media.tar.gz" -C "$(dirname "$MEDIA")" "$(basename "$MEDIA")"
else
  docker compose exec -T tpark-web python manage.py backup_db /data/db/backup.sqlite3
  docker compose cp tpark-web:/data/db/backup.sqlite3 "$DEST/db.sqlite3"
  docker compose exec -T tpark-web rm -f /data/db/backup.sqlite3
  docker compose exec -T tpark-web tar -czf - -C /data media > "$DEST/media.tar.gz"
fi

ls -1dt backups/20*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
echo "Бэкап готов: $DEST"
