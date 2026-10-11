"""Проверки конфигурации развёртывания, которые иначе всплыли бы только на сервере."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # корень репозитория (src/tests → корень)


def _compose_services() -> list[str]:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    services_block = text.split("services:", 1)[1].split("\nvolumes:", 1)[0]
    return re.findall(r"^  ([\w-]+):\s*$", services_block, flags=re.MULTILINE)


def test_compose_service_names_are_unique_in_shared_proxy_network():
    # Имя сервиса — DNS-алиас во всех сетях сервиса, включая общую сеть прокси:
    # общие имена вроде web/media пересеклись бы с другими проектами.
    assert _compose_services() == ["tpark-web", "tpark-media"]


def test_env_example_is_production_safe_by_default():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert values["DEBUG"] == "0"


def test_scripts_use_renamed_service():
    for path in [ROOT / "scripts" / "backup.sh", ROOT / "README.md", ROOT / "CLAUDE.md"]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"compose (exec|run|cp)( -T| --rm)* web\b", text), path
        assert not re.search(r"(?<![\w-])web:/data", text), path


def test_dev_compose_renews_venv_volume():
    # В compose.dev.yaml .venv образа держится в анонимном томе, а compose при пересоздании контейнера
    # оставляет старый том: без --renew-anon-volumes новые зависимости из пересобранного образа не видны.
    for path in [ROOT / "Makefile", ROOT / "compose.dev.yaml", ROOT / "README.md", ROOT / "CLAUDE.md"]:
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"(compose -f compose\.dev\.yaml|DEV_COMPOSE\)) up\b", line):
                assert "--renew-anon-volumes" in line, f"{path.name}: {line.strip()}"


def test_entrypoint_prunes_thumbnails_after_generating_in_background():
    # Сначала досоздать миниатюры, потом удалить ненужные — в фоне, чтобы сайт стартовал сразу.
    script = (ROOT / "docker/entrypoint.sh").read_text(encoding="utf-8")
    assert re.search(r"\(.*generateimages && .*prune_image_cache\) &", script)


def test_dockerignore_excludes_legacy_data():
    # Старая база с паролями и выгрузки импорта лежат в src/ рабочей копии, а образ собирается из src/.
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "src/old_migrate" in lines
    assert "src/*.csv" in lines
    # Отчёты покрытия (pytest --cov) лежат в src/ рабочей копии и в образ не нужны.
    assert "src/.coverage*" in lines
    assert "src/htmlcov" in lines


def test_gitignore_excludes_coverage_reports():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/src/.coverage*" in lines
    assert "/src/htmlcov/" in lines


NGINX = (ROOT / "docker/nginx.conf.template").read_text(encoding="utf-8")


def _server_blocks(conf: str) -> list[str]:
    """Тексты блоков server { … } верхнего уровня внутри http (вложенные location — внутри)."""
    blocks, depth, start = [], 0, None
    for match in re.finditer(r"server\s*\{|\{|\}", conf):
        token = match.group()
        if token.startswith("server") and depth == 1:
            start = match.start()
        if token.endswith("{"):
            depth += 1
        else:
            depth -= 1
            if depth == 1 and start is not None:
                blocks.append(conf[start : match.end()])
                start = None
    return blocks


def test_nginx_rejects_unknown_hosts():
    blocks = _server_blocks(NGINX)
    assert any("listen 80 default_server;" in b and "return 444;" in b for b in blocks)
    assert any("listen 443 ssl default_server;" in b and "ssl_reject_handshake on;" in b for b in blocks)


def test_nginx_http_redirects_straight_to_canonical_host():
    # http://www… → https://t-camp.ru одним редиректом, а не через www и middleware.
    assert "return 301 https://${CANONICAL_HOST}$request_uri;" in NGINX
    assert "https://$host$request_uri" not in NGINX
    compose = (ROOT / "compose.nginx.yaml").read_text(encoding="utf-8")
    assert "CANONICAL_HOST: ${CANONICAL_HOST:-t-camp.ru}" in compose


def test_nginx_limits_admin_login():
    assert re.search(r"limit_req_zone \$binary_remote_addr zone=admin_login:\d+m rate=\d+r/m;", NGINX)
    block = NGINX.split("location = /admin/login/", 1)[1].split("}", 1)[0]
    assert "limit_req zone=admin_login" in block
    assert "proxy_pass http://tpark_web;" in block


def test_nginx_sets_real_ip_for_every_location():
    # Заголовки прокси — на уровне server: location без своих proxy_set_header их наследует.
    https = next(b for b in _server_blocks(NGINX) if "acme_certificate" in b)
    server_level = re.sub(r"location[^{]*\{[^}]*\}", "", https)
    assert "proxy_set_header X-Real-IP $remote_addr;" in server_level
    for location in re.findall(r"location[^{]*\{([^}]*)\}", https):
        assert "proxy_set_header" not in location


def _services(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split("\nservices:", 1)[1].split("\nvolumes:", 1)[0]
    return re.findall(r"^  ([\w-]+):\s*$", block, flags=re.MULTILINE)


def test_compose_rotates_logs_for_every_service():
    for name in ("compose.yaml", "compose.nginx.yaml"):
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        assert re.search(r'max-size: "10m"', text), name
        assert text.count("logging: *logging") == len(_services(path)), name


def test_web_has_memory_limit():
    for name in ("compose.yaml", "compose.nginx.yaml"):
        assert "mem_limit: ${WEB_MEM_LIMIT:-1g}" in (ROOT / name).read_text(encoding="utf-8"), name


def test_gunicorn_timeout_covers_bulk_upload():
    # Пачка фото пережимается прямо в запросе; 30 с по умолчанию мало, у nginx — 120 с.
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert '"--timeout", "120"' in dockerfile


def test_env_example_starts_with_short_hsts():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert values["HSTS_SECONDS"] == "86400"


def test_make_up_backs_up_only_running_site():
    # Миграции идут при старте контейнера (entrypoint), поэтому перед пересборкой — бэкап; при первом запуске — пропуск.
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\nup:", 1)[1].split("\n\n", 1)[0]
    assert "docker compose ps -q tpark-web" in recipe
    # Сначала сборка (долгая), потом бэкап — иначе правки, сделанные за время сборки, в бэкап не попадут; потом запуск.
    assert (
        recipe.index("docker compose build") < recipe.index("scripts/backup.sh") < recipe.index("docker compose up -d")
    )
    assert "up -d --build" not in recipe


def test_backup_rotation_touches_only_dated_folders():
    # Папки вроде backups/legacy-source/ ротация удалять не должна: только backups/YYYY-MM-DD_HHMM.
    script = (ROOT / "scripts" / "backup.sh").read_text(encoding="utf-8")
    assert "ls -1dt backups/20*/" in script
    assert "backups/*/" not in script


def test_ci_runs_linters_tests_and_image_build():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for command in ("ruff check", "ruff format --check", "makemigrations --check", "pytest", "docker build"):
        assert command in workflow, command
    # Минимальные права токена, отмена устаревших прогонов и потолок по времени.
    assert re.search(r"^permissions:\n  contents: read$", workflow, re.MULTILINE)
    assert "cancel-in-progress: true" in workflow
    assert workflow.count("timeout-minutes:") == 2  # test и image


def _service_block(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split(f"\n  {name}:\n", 1)[1].split("\n  tpark-", 1)[0].split("\nvolumes:", 1)[0]


def test_web_container_is_hardened():
    for name in ("compose.yaml", "compose.nginx.yaml"):
        block = _service_block(ROOT / name, "tpark-web")
        for line in ("read_only: true", "- /tmp", "cap_drop: [ALL]", "no-new-privileges:true"):
            assert line in block, (name, line)


def test_nginx_containers_have_healthchecks():
    assert "healthcheck:" in _service_block(ROOT / "compose.yaml", "tpark-media")
    assert "healthcheck:" in _service_block(ROOT / "compose.nginx.yaml", "tpark-nginx")
    assert "location = /healthz" in (ROOT / "docker/nginx-media.conf").read_text(encoding="utf-8")
    assert "location = /healthz" in (ROOT / "docker/nginx.conf.template").read_text(encoding="utf-8")


def test_upload_temp_dir_is_on_db_volume_and_created_at_start():
    # Файлы больших загрузок — на диск (том db), а не в tmpfs /tmp, который считается в mem_limit.
    # Том media раздаёт nginx, поэтому временные файлы туда класть нельзя.
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r"FILE_UPLOAD_TEMP_DIR=(\S+)", dockerfile)
    assert match, "Dockerfile не задаёт FILE_UPLOAD_TEMP_DIR"
    assert match.group(1).startswith("/data/db/")
    assert "/data/media" not in match.group(1)
    entrypoint = (ROOT / "docker/entrypoint.sh").read_text(encoding="utf-8")
    assert 'mkdir -p "$FILE_UPLOAD_TEMP_DIR"' in entrypoint
    # Оборванные загрузки оставляют файлы: старше часа удаляем при старте (и не падаем под set -e, если удалять нечего).
    assert re.search(r'find "\$FILE_UPLOAD_TEMP_DIR" -type f -mmin \+60 -delete', entrypoint)


def test_python_does_not_write_bytecode_into_read_only_image():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile
