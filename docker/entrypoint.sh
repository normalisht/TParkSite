#!/bin/sh
set -e
# Временные файлы больших загрузок лежат на томе db (не в tmpfs и не в media, которую раздаёт nginx); Django требует, чтобы каталог существовал.
# Оборванные загрузки оставляют там файлы: при старте убираем старше часа (`-delete` без находок не падает под set -e).
if [ -n "$FILE_UPLOAD_TEMP_DIR" ]; then
  mkdir -p "$FILE_UPLOAD_TEMP_DIR"
  find "$FILE_UPLOAD_TEMP_DIR" -type f -mmin +60 -delete
fi
python manage.py migrate --noinput
# Миниатюры — в фоне с низким приоритетом: сайт стартует сразу, а недостающие миниатюры
# ImageKit всё равно создаёт при первом запросе страницы. Затем удаляются ненужные (старые
# размеры и качество — после смены спек). Ошибка здесь контейнер не роняет.
(nice -n 10 python manage.py generateimages && nice -n 10 python manage.py prune_image_cache) &
exec "$@"
