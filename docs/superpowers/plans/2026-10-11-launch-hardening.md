# Подготовка продакшена к запуску — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Закрыть пункты P0 и P1 «Эксплуатация» из аудита:
- образ без старых данных;
- защита входа в админку;
- nginx без лишних редиректов и чужих хостов;
- ротация логов;
- устойчивая загрузка фото;
- бэкап перед каждым деплоем.

**Architecture:** Код почти не меняется — меняется инфраструктура:
- `.dockerignore`, `compose*.yaml`, `Dockerfile`, `docker/nginx.conf.template`, `Makefile`;
- в Django — `django-axes` и проверка размера фото в мегапикселях в `validate_image_upload`.

Конфигурацию проверяем тестами-«линтерами» в `tests/test_deploy_config.py` (так уже сделано в проекте). nginx и compose дополнительно проверяем вручную на сервере.

**Tech Stack:** Django 6.1, django-axes, gunicorn, nginx (`compose.nginx.yaml`), Docker Compose, pytest-django.

**Spec:** `docs/site-audit-2026-10-11.md`. Этот план закрывает:
- раздел «P0» — п. 2;
- раздел «P1 → Эксплуатация» — пп. 5–9.

**Ветка:** `fix/launch-hardening` от `main`.

## Global Constraints

- Весь пользовательский текст (сообщения, help_text, комментарии в конфигах) — на русском.
- Python-команды — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; pre-commit (ruff) должен проходить.
- Не трогать `old_version/`.
- Два варианта продакшена должны продолжать работать:
  - `compose.yaml` (общий прокси, сеть `PROXY_NETWORK`);
  - `compose.nginx.yaml` (свой nginx).

  nginx-правки (п. 8 аудита) касаются только второго. Для первого требования к прокси описываются в README.
- Имена сервисов `tpark-web`, `tpark-media`, `tpark-nginx` не менять: на них опираются тесты и скрипты.
- 2FA не делаем: пункт убран из аудита владельцем.

## Review Focus

1. **Блокировка входа за общим прокси без `X-Real-IP`.** Все запросы приходят с IP прокси.
   - Ожидание: блокируется пара «логин + IP», то есть подбор пароля к одному логину, а не весь сайт. Другие логины входят.
   - Тест: задача 3, `test_lockout_is_per_username_and_ip`.
2. **Клиент сам присылает `X-Real-IP`, чтобы обойти блокировку.** В варианте `compose.nginx.yaml` nginx перезаписывает заголовок (`proxy_set_header X-Real-IP $remote_addr`).
   - Ожидание: заголовок задаётся на уровне `server` и не теряется ни в одном `location`.
   - Тест: задача 4, `test_nginx_sets_real_ip_for_every_location`.
3. **Фото 165 Мп весом 0,5 МБ (PNG).**
   - Ожидание: понятная ошибка формы, а не падение воркера.
   - Тест: задача 2.
4. **Первый деплой, когда контейнер ещё не запущен.** `make up` не должен падать на бэкапе.
   - Ожидание: бэкап пропускается, сайт поднимается.
   - Тест: задача 6, `test_make_up_backs_up_only_running_site` (проверка условия в рецепте).
5. **ACME-проверка Let's Encrypt после появления `default_server` на 80 порту.**
   - Ожидание: запросы `/.well-known/acme-challenge/` с `Host: t-camp.ru` попадают в именованный server, а не в `return 444`.
   - Проверка: задача 4, шаг ручной проверки на сервере (`curl -I http://t-camp.ru/.well-known/acme-challenge/x` — не пустой ответ).

---

### Task 1: Образ без старых данных

**Files:**
- Modify: `.dockerignore`
- Modify: `src/apps/core/management/commands/import_legacy.py:15-17`
- Test: `src/tests/test_deploy_config.py`
- Test: `src/tests/legacy/test_import_site.py` (новый тест в конце файла)

**Interfaces:**
- Produces: у `import_legacy` по умолчанию `--price-csv` = `None`, CSV не пишется.

- [ ] **Step 1: Написать падающие тесты**

В конец `src/tests/test_deploy_config.py`:

```python
def test_dockerignore_excludes_legacy_data():
    # Старая база с паролями и выгрузки импорта лежат в src/ рабочей копии, а образ собирается из src/.
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "src/old_migrate" in lines
    assert "src/*.csv" in lines
```

В конец `src/tests/legacy/test_import_site.py`:

```python
def test_import_legacy_does_not_write_price_csv_by_default():
    from apps.core.management.commands.import_legacy import Command

    options = Command().create_parser("manage.py", "import_legacy").parse_args(["--db", "x.db", "--images", "img"])
    assert options.price_csv is None
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd src && uv run pytest tests/test_deploy_config.py::test_dockerignore_excludes_legacy_data tests/legacy/test_import_site.py::test_import_legacy_does_not_write_price_csv_by_default -v`
Expected: оба FAIL (нет строк в `.dockerignore`; `price_csv == PosixPath('price_legacy.csv')`).

- [ ] **Step 3: Реализация**

В `.dockerignore` после строки `src/.env` добавить:

```
# Данные старого сайта и выгрузки импорта (в рабочей копии; в git их нет)
src/old_migrate
src/*.csv
```

В `import_legacy.py` заменить аргумент `--price-csv`:

```python
        parser.add_argument(
            "--price-csv", type=Path, default=None, help="Куда выгрузить таблицу price (без параметра не выгружается)"
        )
```

(`run_import` уже пропускает выгрузку при `price_csv=None` — `apps/core/legacy/runner.py:88`.)

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest tests/test_deploy_config.py tests/legacy -q`
Expected: PASS.

- [ ] **Step 5: Убрать данные из `src/`**

```bash
cd /Users/dmitry.normanev/personal/TParkSite
git check-ignore -q backups && echo "backups/ в .gitignore"
mkdir -p backups/legacy-source
mv src/old_migrate src/price_legacy.csv backups/legacy-source/ 2>/dev/null; ls backups/legacy-source
```

Если `git check-ignore` ничего не вывел — не перемещать, а спросить владельца, куда положить. Папка `backups/` не должна попасть в git.

- [ ] **Step 6: Коммит**

```bash
git add .dockerignore src/apps/core/management/commands/import_legacy.py src/tests/test_deploy_config.py src/tests/legacy/test_import_site.py
git commit -m "Образ без данных старого сайта: old_migrate и CSV в .dockerignore, импорт не пишет CSV по умолчанию"
```

---

### Task 2: Ограничение мегапикселей при загрузке фото

**Files:**
- Modify: `src/apps/core/fields.py:37-54`
- Test: `src/tests/test_core_helpers.py`

**Interfaces:**
- Produces: `apps.core.fields.MAX_IMAGE_PIXELS = 50_000_000`; `validate_image_upload` бросает `ValidationError` с текстом «…больше 50 мегапикселей…».

- [ ] **Step 1: Падающий тест**

В `src/tests/test_core_helpers.py` (импорты добавить в начало файла, если их нет):

```python
import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.fields import validate_image_upload


def test_upload_rejects_decompression_bomb():
    # 8000×7000 = 56 Мп: PNG весит килобайты, а распакованный займёт сотни мегабайт при пережатии.
    buffer = io.BytesIO()
    Image.new("1", (8000, 7000)).save(buffer, "PNG")
    upload = SimpleUploadedFile("big.png", buffer.getvalue(), content_type="image/png")
    with pytest.raises(ValidationError, match="50 мегапикселей"):
        validate_image_upload(upload)


def test_upload_accepts_normal_photo(make_image):
    validate_image_upload(make_image(size=(4000, 3000)))
```

- [ ] **Step 2: Тест падает**

Run: `cd src && uv run pytest tests/test_core_helpers.py -k "bomb or normal_photo" -v`
Expected: `test_upload_rejects_decompression_bomb` FAIL (DID NOT RAISE).

- [ ] **Step 3: Реализация** — в `apps/core/fields.py`:

```python
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# Пережатие держит в памяти всё фото: 50 Мп ≈ 150 МБ. Больше — риск, что воркер убьёт OOM (фото с телефона — 12–48 Мп).
MAX_IMAGE_PIXELS = 50_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(file) -> None:
    if getattr(file, "_committed", False):
        return  # файл уже в хранилище — проверяли при загрузке; отсутствие файла на диске не должно блокировать сохранение
    if file.size and file.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Файл больше 20 МБ.")
    try:
        position = file.tell()
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
        file.seek(position)
    except Exception as exc:
        raise ValidationError("Файл не похож на изображение.") from exc
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Допустимые форматы: jpg, png или webp.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError("Фото больше 50 мегапикселей — уменьшите его перед загрузкой.")
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest tests/test_core_helpers.py tests/test_admin.py -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add src/apps/core/fields.py src/tests/test_core_helpers.py
git commit -m "Загрузка фото: не больше 50 Мп — защита от «бомбы распаковки»"
```

---

### Task 3: Защита входа в админку — django-axes

**Files:**
- Modify: `src/pyproject.toml`, `src/uv.lock` (через `uv add`)
- Modify: `src/config/settings.py` (INSTALLED_APPS, MIDDLEWARE, новые настройки)
- Modify: `src/config/settings_test.py`
- Modify: `README.md` (раздел про прокси и разблокировку)
- Test: `src/tests/test_admin_login.py` (новый)

**Interfaces:**
- Produces:
  - после 5 неудачных попыток пара «логин + IP» блокируется на 30 минут;
  - IP берётся из `X-Real-IP`, без заголовка — из `REMOTE_ADDR`;
  - разблокировка: `python manage.py axes_reset`.

- [ ] **Step 1: Зависимость**

Run: `cd src && uv add "django-axes[ipware]"`
Expected: пакет установлен.

Затем `uv run python -c "import axes, django; print(axes.__version__, django.__version__)"`.

Если в README django-axes нет поддержки Django 6.1 и тесты ниже падают с ошибкой импорта или в API Django — остановиться и сообщить владельцу, а не обходить. Запасной вариант (не делать без согласия): свой счётчик неудачных входов на `django.core.cache`.

- [ ] **Step 2: Падающие тесты** — `src/tests/test_admin_login.py`:

```python
"""Защита входа в админку от подбора пароля (django-axes)."""

import pytest

pytestmark = pytest.mark.django_db

LOGIN = "/admin/login/"


@pytest.fixture(autouse=True)
def axes_on(settings):
    settings.AXES_ENABLED = True  # в settings_test выключен: тестовый client.login() не передаёт request


@pytest.fixture
def boss(django_user_model):
    return django_user_model.objects.create_superuser("boss", password="right-pass-123")


def _login(client, username, password, ip):
    return client.post(LOGIN, {"username": username, "password": password}, HTTP_X_REAL_IP=ip)


def test_lockout_after_five_failures(client, boss):
    for _ in range(5):
        _login(client, "boss", "wrong", "203.0.113.5")
    response = _login(client, "boss", "right-pass-123", "203.0.113.5")
    assert response.status_code in (403, 429)


def test_lockout_is_per_username_and_ip(client, boss, django_user_model):
    django_user_model.objects.create_superuser("editor", password="editor-pass-123")
    for _ in range(5):
        _login(client, "boss", "wrong", "203.0.113.5")
    # Тот же логин с другого IP и другой логин с того же IP входят.
    assert _login(client, "boss", "right-pass-123", "198.51.100.7").status_code == 302
    client.logout()
    assert _login(client, "editor", "editor-pass-123", "203.0.113.5").status_code == 302


def test_successful_login_works(client, boss):
    assert _login(client, "boss", "right-pass-123", "203.0.113.5").status_code == 302
```

- [ ] **Step 3: Тесты падают**

Run: `cd src && uv run pytest tests/test_admin_login.py -v`
Expected: `test_lockout_after_five_failures` FAIL (200 вместо 403/429); остальные могут пройти.

- [ ] **Step 4: Реализация** — `src/config/settings.py`:

В начало файла: `from datetime import timedelta`.

`INSTALLED_APPS` — после `"django.contrib.auth"` добавить `"axes",`.

`MIDDLEWARE` — последней строкой:

```python
    # Блокировка подбора пароля к админке; должен быть последним (документация django-axes).
    "axes.middleware.AxesMiddleware",
```

После `AUTH_PASSWORD_VALIDATORS`:

```python
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # первым: отказывает заблокированным до проверки пароля
    "django.contrib.auth.backends.ModelBackend",
]
# 5 неудачных попыток — пара «логин + IP» заблокирована на 30 минут. Не весь IP: за общим прокси без X-Real-IP
# все запросы с одного адреса, и блокировка IP закрыла бы админку всем. Разблокировать: manage.py axes_reset.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# IP клиента — из X-Real-IP: наш nginx перезаписывает его адресом соединения, клиент подделать не может.
# Без прокси (runserver) заголовка нет — берётся REMOTE_ADDR.
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_REAL_IP", "REMOTE_ADDR"]
```

`src/config/settings_test.py` — в конец:

```python
# client.login() в тестах не передаёт request, а AxesStandaloneBackend его требует; тесты axes включают сами.
AXES_ENABLED = False
```

- [ ] **Step 5: Миграции и тесты**

Run: `cd src && uv run manage.py migrate && uv run pytest -q`
Expected: всё PASS, включая `tests/test_admin_login.py`.

Если `test_lockout_after_five_failures` падает из-за того, что включение через фикстуру `settings` не подхватывается, посмотреть, как axes читает `AXES_ENABLED` (`axes/conf.py`, `axes/helpers.py`). Тогда включать через `override_settings` на уровне модуля — без правки логики.

- [ ] **Step 6: README**

В README, в раздел про общий прокси (вариант `compose.yaml`), добавить:

```markdown
Требования к общему прокси: передавать `X-Real-IP $remote_addr` (перезаписывая заголовок клиента) и `X-Forwarded-Proto`, сжимать HTML (`gzip on`). Без `X-Real-IP` защита от подбора пароля блокирует логин для всех, кто входит через этот прокси.

Если администратор заблокирован после 5 неудачных попыток входа (30 минут): `docker compose exec tpark-web python manage.py axes_reset`.
```

- [ ] **Step 7: Коммит**

```bash
git add src/pyproject.toml src/uv.lock src/config/settings.py src/config/settings_test.py src/tests/test_admin_login.py README.md
git commit -m "Админка: блокировка подбора пароля (django-axes, логин+IP, 5 попыток / 30 мин)"
```

---

### Task 4: nginx — прямой редирект, отказ чужим хостам, лимит на вход

**Files:**
- Modify: `docker/nginx.conf.template`
- Modify: `compose.nginx.yaml` (окружение `tpark-nginx`)
- Test: `src/tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `CANONICAL_HOST` из корневого `.env` (уже есть в `.env.example`).
- Produces: в шаблоне nginx — переменная `${CANONICAL_HOST}`.

- [ ] **Step 1: Падающие тесты** — в конец `src/tests/test_deploy_config.py`:

```python
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
```

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_deploy_config.py -k nginx -v`
Expected: 4 FAIL.

- [ ] **Step 3: Реализация** — в `docker/nginx.conf.template`.

Заголовок файла — дописать `${CANONICAL_HOST}` в список переменных envsubst:

```
# ${SERVER_NAME}, ${CANONICAL_HOST}, ${ACME_EMAIL}, ${ACME_SERVER} подставляет envsubst образа nginx,
```

После `upstream tpark_web { … }`:

```nginx
    # Подбор пароля к админке: не больше 10 попыток входа в минуту с адреса (+5 сразу), дальше — 429.
    limit_req_zone $binary_remote_addr zone=admin_login:10m rate=10r/m;

    # Запросы не на наш домен (по IP, сканеры) не доходят до Django: соединение закрывается без ответа.
    server {
        listen 80 default_server;
        listen [::]:80 default_server;
        return 444;
    }

    server {
        listen 443 ssl default_server;
        listen [::]:443 ssl default_server;
        ssl_reject_handshake on;
    }
```

Блок `:80` с `server_name ${SERVER_NAME}` — заменить `location /`:

```nginx
        location / {
            # Сразу на главный домен по https: http://www… — одним редиректом, без промежуточного www.
            return 301 https://${CANONICAL_HOST}$request_uri;
        }
```

Блок `:443`: директивы прокси перенести из `location /` на уровень `server` (перед `location /media/`), сам `location /` упростить и добавить `location = /admin/login/`:

```nginx
        # Для всех location ниже: location без своих proxy_set_header наследует эти.
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;

        location /media/ {
            … (без изменений)
        }

        location = /admin/login/ {
            limit_req zone=admin_login burst=5 nodelay;
            limit_req_status 429;
            proxy_pass http://tpark_web;
        }

        location / {
            proxy_pass http://tpark_web;
        }
```

`compose.nginx.yaml` — в `environment` сервиса `tpark-nginx` после `SERVER_NAME`:

```yaml
      # Куда ведёт редирект с http и www (как CANONICAL_HOST в Django).
      CANONICAL_HOST: ${CANONICAL_HOST:-t-camp.ru}
```

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest tests/test_deploy_config.py -v`
Expected: PASS.

- [ ] **Step 5: Синтаксис конфига** (Docker локально)

```bash
cd /Users/dmitry.normanev/personal/TParkSite
docker compose -f compose.nginx.yaml config >/dev/null && echo "compose ok"
```

Полная проверка `nginx -t` возможна только на сервере: модулю ACME нужен резолвер Docker. Записать её в шаг 6.

- [ ] **Step 6: Чек-лист для ручной проверки после деплоя** — добавить в README, в раздел про `compose.nginx.yaml`:

```markdown
Проверка после деплоя:
- `docker compose exec tpark-nginx nginx -t` — конфиг без ошибок;
- `curl -sI http://www.t-camp.ru/contacts/` — один ответ `301` сразу на `https://t-camp.ru/contacts/`;
- `curl -sI http://<IP сервера>/` — соединение закрыто без ответа (`Empty reply from server`);
- `curl -sI http://t-camp.ru/.well-known/acme-challenge/test` — ответ от nginx (404), а не обрыв: проверка Let's Encrypt проходит.
```

- [ ] **Step 7: Коммит**

```bash
git add docker/nginx.conf.template compose.nginx.yaml src/tests/test_deploy_config.py README.md
git commit -m "nginx: http и www — сразу на главный домен, отказ чужим хостам, лимит попыток входа в админку"
```

---

### Task 5: Ротация логов, память, таймаут gunicorn, HSTS на старте

**Files:**
- Modify: `compose.yaml`, `compose.nginx.yaml`
- Modify: `Dockerfile:36` (CMD)
- Modify: `.env.example`
- Test: `src/tests/test_deploy_config.py`

**Interfaces:**
- Produces: переменные `.env` — `WEB_MEM_LIMIT` (по умолчанию `1g`) и `HSTS_SECONDS=86400` в примере.

- [ ] **Step 1: Падающие тесты** — в конец `src/tests/test_deploy_config.py`:

```python
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
```

Важно: `_services` ищет блок `services:` с переводом строки перед ним. Если в файле до `services:` есть только комментарии, первая строка `services:` без `\n` перед ней не найдётся — тогда искать `text.split("services:", 1)`, как в существующем `_compose_services`.

- [ ] **Step 2: Тесты падают**

Run: `cd src && uv run pytest tests/test_deploy_config.py -k "logs or memory or gunicorn or hsts" -v`
Expected: 4 FAIL.

- [ ] **Step 3: Реализация**

`compose.yaml` — первой строкой файла, до `services:`:

```yaml
# Логи контейнеров: не больше 5 файлов по 10 МБ, иначе access-логи забьют диск, и SQLite перестанет писать.
x-logging: &logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "5"

```

У каждого сервиса (`tpark-web`, `tpark-media`) после `restart: unless-stopped`:

```yaml
    logging: *logging
```

У `tpark-web` дополнительно:

```yaml
    # Пережатие фото держит их в памяти; без лимита OOM-killer может положить весь сервер.
    mem_limit: ${WEB_MEM_LIMIT:-1g}
```

`compose.nginx.yaml` — то же самое:
- блок `x-logging` после вводного комментария, перед `services:`;
- `logging: *logging` у `tpark-web` и `tpark-nginx`;
- `mem_limit` у `tpark-web`.

`Dockerfile`, последняя строка:

```dockerfile
# --timeout 120: загрузка фото пачкой пережимает их прямо в запросе (у nginx proxy_read_timeout тоже 120 с).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-", "--no-control-socket"]
```

`.env.example` — заменить строку `HSTS_SECONDS=31536000`:

```
# HSTS: на старте — сутки (если что-то случится с сертификатом, браузеры не «запомнят» https надолго).
# После недели стабильной работы — 31536000 (год).
HSTS_SECONDS=86400
```

И после `WEB_CONCURRENCY=3`:

```
# Лимит памяти контейнера сайта (пережатие фото). Для VPS с 1 ГБ — 600m.
# WEB_MEM_LIMIT=1g
```

- [ ] **Step 4: Тесты и синтаксис compose**

```bash
cd src && uv run pytest tests/test_deploy_config.py -q
cd .. && PROXY_NETWORK=proxy docker compose config >/dev/null && ACME_EMAIL=x@example.com docker compose -f compose.nginx.yaml config >/dev/null && echo ok
```

Expected: PASS и `ok`.

- [ ] **Step 5: Коммит**

```bash
git add compose.yaml compose.nginx.yaml Dockerfile .env.example src/tests/test_deploy_config.py
git commit -m "Продакшен: ротация логов Docker, лимит памяти, таймаут gunicorn 120 с, HSTS на старте — сутки"
```

---

### Task 6: Бэкап перед каждым деплоем

**Files:**
- Modify: `Makefile` (цель `up`)
- Modify: `README.md` (шаги деплоя)
- Modify: `CLAUDE.md` (строка про `make up`)
- Test: `src/tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `scripts/backup.sh` (без изменений).

- [ ] **Step 1: Падающий тест**

```python
def test_make_up_backs_up_only_running_site():
    # Миграции идут при старте контейнера (entrypoint), поэтому перед пересборкой — бэкап; при первом запуске — пропуск.
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    recipe = makefile.split("\nup:", 1)[1].split("\n\n", 1)[0]
    assert "docker compose ps -q tpark-web" in recipe
    assert recipe.index("scripts/backup.sh") < recipe.index("docker compose up -d --build")
```

- [ ] **Step 2: Тест падает**

Run: `cd src && uv run pytest tests/test_deploy_config.py::test_make_up_backs_up_only_running_site -v`
Expected: FAIL.

- [ ] **Step 3: Реализация** — цель `up` в `Makefile`:

```makefile
up: ## Бэкап (если сайт уже запущен), затем сборка и запуск продакшена в фоне
	@if [ -n "$$(docker compose ps -q tpark-web 2>/dev/null)" ]; then ./scripts/backup.sh; else echo "Сайт не запущен — бэкап пропущен"; fi
	docker compose up -d --build
```

README, раздел продакшена, шаг 2 — заменить `docker compose up -d --build` на:

```markdown
`make up` (перед пересборкой делает бэкап работающего сайта: при старте контейнера применяются миграции)
```

То же — в описании деплоя для `compose.nginx.yaml`.

В CLAUDE.md, в списке команд из корня, строку про `docker compose up -d --build` дополнить: «(обновление — `make up`: сначала бэкап)».

- [ ] **Step 4: Тесты проходят**

Run: `cd src && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Коммит**

```bash
git add Makefile README.md CLAUDE.md src/tests/test_deploy_config.py
git commit -m "make up: бэкап работающего сайта перед пересборкой (миграции идут при старте)"
```

---

## После плана

- Полный прогон: `cd src && uv run pytest -q && uv run ruff check . && uv run ruff format --check .`.
- Ручная проверка на сервере — чек-лист из задачи 4 (шаг 6).
- Через неделю стабильной работы — `HSTS_SECONDS=31536000` в `.env` на сервере.
