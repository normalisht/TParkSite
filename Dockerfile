# Сборка в два этапа: в build — uv, бинарник Tailwind (~105 МБ) и сборка CSS/статики, в итоговый образ
# переносятся только .venv, код и собранная статика. Оба этапа — от одного образа Python: .venv ссылается на его интерпретатор.
FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83 AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DATABASE_PATH=/data/db/db.sqlite3 \
    MEDIA_ROOT=/data/media \
    STATIC_ROOT=/app/staticfiles

WORKDIR /app


FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src/uv.lock,target=uv.lock \
    --mount=type=bind,source=src/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# Django-проект живёт в src/ репозитория и копируется в /app.
COPY src/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# Бинарник Tailwind — в кеше сборки: не скачивается заново при каждой правке кода и не попадает в слои.
# Копия в /opt/tailwind нужна только dev-образу (Tailwind в режиме watch).
# compileall: код только для чтения (read_only), без готового байткода каждый воркер компилировал бы его заново.
RUN --mount=type=cache,target=/app/.django_tailwind_cli \
    SECRET_KEY=build-only python manage.py tailwind build \
 && SECRET_KEY=build-only python manage.py collectstatic --noinput \
 && cp -a .django_tailwind_cli /opt/tailwind \
 && python -m compileall -q apps config


FROM base AS app

RUN useradd --system --uid 1000 --home-dir /app app \
 && mkdir -p /data/db /data/media \
 && chown -R app:app /data

COPY --from=build /app /app
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Задаётся после сборки: проверка Django требует, чтобы каталог существовал, а создаёт его entrypoint.
ENV FILE_UPLOAD_TEMP_DIR=/data/db/upload-tmp

USER app
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# --timeout 120: загрузка фото пачкой пережимает их прямо в запросе (у nginx proxy_read_timeout тоже 120 с).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-", "--no-control-socket"]


# compose.dev.yaml (target: dev): тот же образ + бинарник Tailwind для `tailwind runserver`.
FROM app AS dev
COPY --from=build /opt/tailwind /app/.django_tailwind_cli


# Последний этап — образ по умолчанию для `docker build .` и compose.yaml: продакшен, без Tailwind.
FROM app AS production
