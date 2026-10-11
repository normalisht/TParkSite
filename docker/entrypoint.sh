#!/bin/sh
set -e
python manage.py migrate --noinput
# Миниатюры — в фоне с низким приоритетом: сайт стартует сразу, а недостающие миниатюры
# ImageKit всё равно создаёт при первом запросе страницы. Затем удаляются ненужные (старые
# размеры и качество — после смены спек). Ошибка здесь контейнер не роняет.
(nice -n 10 python manage.py generateimages && nice -n 10 python manage.py prune_image_cache) &
exec "$@"
