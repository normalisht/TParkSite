#!/usr/bin/env bash
# Деплой из GitHub Actions: принудительная команда ключа CI в ~/.ssh/authorized_keys пользователя сайта
#   command="<каталог репозитория>/deploy/ci-deploy.sh",restrict ssh-ed25519 AAAA… github-actions-deploy
# Принимает только полный SHA коммита (ssh сервер <sha>) и выкатывает его, если он есть в origin/main.
# Тело — в блоке { …; exit; }: bash читает скрипт по ходу выполнения, а git ниже может его заменить.
{
set -euo pipefail
cd "$(dirname "$0")/.."

rev="${SSH_ORIGINAL_COMMAND:-${1:-}}"
if [[ ! "$rev" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Ожидался полный SHA коммита, получено: ${rev:-пусто}" >&2
  exit 2
fi

# Два деплоя из CI (повторный запуск, ручной Run workflow) не должны идти одновременно.
exec 9>.git/ci-deploy.lock
flock -w 1800 9 || { echo "Другой деплой не закончился за 30 минут" >&2; exit 1; }

git fetch --quiet origin main
if ! git merge-base --is-ancestor "$rev" origin/main 2>/dev/null; then
  echo "Коммита $rev нет в origin/main" >&2
  exit 2
fi
head="$(git rev-parse HEAD)"
if [ "$head" != "$rev" ] && git merge-base --is-ancestor "$rev" "$head"; then
  echo "Уже выкачен более новый коммит $head — пропускаю $rev"
  exit 0
fi

git merge --ff-only --quiet "$rev"
echo "Код: $(git log -1 --format='%h %s')"
# Отдельный make читает Makefile уже после merge.
make --no-print-directory service-deploy
exit
}
