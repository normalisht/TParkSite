#!/usr/bin/env bash
# Бэкап продакшена: снимок SQLite + архив медиа. Запуск из cron на хосте, например:
#   15 3 * * * cd /srv/tpark && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP="${BACKUP_KEEP:-14}"
DEST="backups/$(date +%Y-%m-%d_%H%M)"
mkdir -p "$DEST"

docker compose exec -T tpark-web python manage.py backup_db /data/db/backup.sqlite3
docker compose cp tpark-web:/data/db/backup.sqlite3 "$DEST/db.sqlite3"
docker compose exec -T tpark-web rm -f /data/db/backup.sqlite3
docker compose exec -T tpark-web tar -czf - -C /data media > "$DEST/media.tar.gz"

ls -1dt backups/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
echo "Бэкап готов: $DEST"
