FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    DATABASE_PATH=/data/db/db.sqlite3 \
    MEDIA_ROOT=/data/media \
    STATIC_ROOT=/app/staticfiles

RUN SECRET_KEY=build-only python manage.py tailwind build \
 && SECRET_KEY=build-only python manage.py collectstatic --noinput \
 && useradd --system --uid 1000 --home-dir /app app \
 && mkdir -p /data/db /data/media \
 && chown -R app:app /data \
 && chmod +x /app/docker/entrypoint.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--no-control-socket"]
