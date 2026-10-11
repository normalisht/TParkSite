#!/bin/sh
set -e
# Временные файлы больших загрузок лежат на томе db (не в tmpfs и не в media, которую раздаёт nginx); Django требует, чтобы каталог существовал.
[ -z "$FILE_UPLOAD_TEMP_DIR" ] || mkdir -p "$FILE_UPLOAD_TEMP_DIR"
python manage.py migrate --noinput
# Миниатюры — в фоне с низким приоритетом: сайт стартует сразу, а недостающие миниатюры
# ImageKit всё равно создаёт при первом запросе страницы. Затем удаляются ненужные (старые
# размеры и качество — после смены спек). Ошибка здесь контейнер не роняет.
(nice -n 10 python manage.py generateimages && nice -n 10 python manage.py prune_image_cache) &
exec "$@"
