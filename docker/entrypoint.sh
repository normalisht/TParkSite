#!/bin/sh
set -e
python manage.py migrate --noinput
# Миниатюры — в фоне с низким приоритетом: сайт стартует сразу, а недостающие миниатюры
# ImageKit всё равно создаёт при первом запросе страницы. Ошибка здесь контейнер не роняет.
nice -n 10 python manage.py generateimages &
exec "$@"
