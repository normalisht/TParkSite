# Сайт Т-Парка на Django: спецификация

Дата: 2026-10-08. Статус: на ревью у владельца проекта.

Связанные документы:
- [current-functionality.md](../../current-functionality.md) — что умеет старая Flask-версия (`old_version/`);
- [decisions.md](../../decisions.md) — журнал решений с обоснованиями (номера решений ниже ссылаются на него).

## 1. Цель и объём

Переписать сайт t-camp.ru на Django с сохранением функционала, улучшить дизайн и удобство сайта и админки, перенести данные из старой SQLite и папки с изображениями.

**В объёме:** витрина групп, категорий и услуг; мероприятия; отзывы; галерея; «О нас» (тексты, карта, сотрудники, партнёры); контакты; инфо-страницы; админка; импорт старых данных; 301-редиректы со старых URL; docker compose для продакшена; бэкап.

**Вне объёма:** онлайн-бронирование, оплата, формы заявок, личный кабинет, многоязычность, React/SPA, объектное хранилище (MinIO/S3).

## 2. Стек

| Слой | Выбор |
|---|---|
| Язык и фреймворк | Python 3.14, Django 6.1.2 (`>=6.1.2,<6.2`) |
| Зависимости | uv (`pyproject.toml`, `uv.lock`; группа `dev`) |
| БД | SQLite (WAL, `busy_timeout`, `transaction_mode="IMMEDIATE"`) |
| Админка | `django-unfold` (встроенная сортировка перетаскиванием) |
| HTML-редактор | `django-prose-editor` + очистка `nh3` |
| Изображения | Pillow, `django-imagekit` |
| Slug | `unidecode` + `django.utils.text.slugify`, уникальность — суффикс `-2`, `-3`… (общий хелпер в `core`) |
| Вёрстка | Django-шаблоны, Tailwind CSS через `django-tailwind-cli` (без Node) |
| JS | Swiper, GLightbox, Alpine.js — vendored-файлы в `static/vendor/`, подключаются тегом `<script>`, без сборки и без CDN |
| Сервер | gunicorn, статика через WhiteNoise, медиа через nginx |
| Тесты и линт | pytest, pytest-django, ruff, pre-commit |

`django-admin-sortable2` подключаем, только если встроенной сортировки Unfold не хватит (решение 6).

## 3. Структура репозитория

```
pyproject.toml, uv.lock, manage.py, .env.example
config/            settings.py, urls.py, wsgi.py
apps/core/         SiteSettings, Phone, InfoPage, редиректы, контекст-процессор, import_legacy
apps/catalog/      CategoryGroup, Category, CategoryPhoto, Service, ServicePhoto, CategoryService
apps/content/      Event, Review, Partner, Employee, GalleryPhoto
templates/         base.html, страницы, partials
static/            css/source.css (Tailwind), js/, img/ (логотип, иконки)
tests/
scripts/backup.sh
Dockerfile, compose.yaml, docker/nginx-media.conf
old_version/       старая Flask-версия, только для справки и импорта
```

Настройки — один `config/settings.py`, параметры из окружения: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_PATH`, `MEDIA_ROOT`. Локально они читаются из `.env`. Хранилище медиа задаётся через `STORAGES`, чтобы при необходимости перейти на S3 только конфигом.

## 4. Модели

Общие правила:
- **Порядок** — поле `order` (PositiveIntegerField, индекс); в админке задаётся перетаскиванием; сортировка по `(order, id)`.
- **Публикация** — поле `is_published`.
- **Изображения** — `ProcessedImageField`: при загрузке пережимаются до ≤1920×1080, JPEG q85 (превью категорий — 1080×720). Для сайта есть `ImageSpecField`-миниатюры в WebP. При удалении записи её файлы удаляются (сигнал `post_delete`).
- **HTML-поля** — `ProseEditorField` с одним общим набором разрешённых тегов (абзацы, жирный, курсив, заголовки h2–h3, списки, ссылки, перенос строки).

### core

- **SiteSettings** (синглтон, `pk=1`, получение через `SiteSettings.load()`):
  - контакты: `address`, `map_url` (Яндекс.Карты), `vk_url`;
  - тексты (HTML): `home_intro`, `events_intro`, `about_text`, `philosophy_text`, `nearby_text`, `contacts_text`;
  - картинки: `contacts_map`, `about_map`.
- **Phone**:
  - `settings` — FK на SiteSettings, `number` — 10 цифр без `+7`, `order`;
  - флаги `is_whatsapp` и `is_telegram`. Каждый флаг может стоять не более чем у одного номера — частичные `UniqueConstraint(fields=["settings"], condition=Q(is_whatsapp=True))` и то же для Telegram;
  - свойства `tel_url` (`tel:+7…`), `whatsapp_url` (`https://wa.me/7…`), `telegram_url` (`https://t.me/+7…`), `display` (`+7 (XXX) XXX-XX-XX`).
- **InfoPage**: `title`, `slug` (уникальный), `body` (HTML), `is_published`.

Настройки и телефоны попадают во все шаблоны через контекст-процессор, телефоны берутся одним запросом.

### catalog

- **CategoryGroup**: `name`, `order`, `categories` — M2M на Category.
- **Category**: `name`, `slug` (уникальный), `description` (HTML), `preview` (изображение), `is_published`, `order`.
- **CategoryPhoto**: `category` FK, `image`, `order`.
- **Service**: `name`, `slug` (уникальный), `short_description` (HTML), `description` (HTML), `price` (строка, до 32 символов), `price_unit` (строка, до 128 символов: «час», «сутки»…), `is_published`, `has_page`.
  - Свойство `price_display`: `"{price} руб / {price_unit}"`, `"{price} руб"` или пусто — повторяет старый `__repr__`.
- **CategoryService**: `category` FK, `service` FK, `order`; `unique_together (category, service)`.
- **ServicePhoto**: `service` FK, `image`, `order`.

### content

- **Event**: `title`, `date`, `description` (HTML), `link` (URL, необязательно), `text_color` (необязательно), `show_after_date`, `image`.
  - Мероприятие «предстоящее», если `date >= today` по `Europe/Moscow`. Эквивалент старого правила «до 22:00 дня мероприятия»: в день мероприятия оно ещё считается предстоящим.
- **Review**: `author`, `text`, `photo` (необязательно), `is_published`, `order`.
- **Partner**: `name` (необязательно, используется как alt), `link`, `logo`, `order`.
- **Employee**: `name`, `position`, `photo`, `order`.
- **GalleryPhoto**: `image`, `caption` (необязательно), `order`.

## 5. Публичная часть

### URL

| Страница | URL | 301 со старого URL |
|---|---|---|
| Главная | `/` | `/TPark` |
| Категория | `/category/<slug>/` | `/category?category_id=N` |
| Услуга | `/service/<slug>/` | `/category/service?service_id=N` |
| Мероприятия | `/events/` | — |
| О нас | `/about/` | `/about_2` |
| Отзывы | `/reviews/` | — |
| Галерея | `/gallery/` | — |
| Контакты | `/contacts/` | — |
| Инфо-страница | `/info/<slug>/` | `/info?info_id=N` |

- Редиректы ищут запись по старому `id`, импорт его сохраняет. Если запись не найдена — 404.
- `/category` без слеша и `/category/` с параметром `category_id` обрабатываются одним redirect-view. URL вида `/category/<slug>/` с ним не конфликтует.
- 404 отдаётся для: неопубликованной категории; неопубликованной услуги; услуги без `has_page`; неопубликованной инфо-страницы.
- Неопубликованные услуги не показываются в списке категории. Неопубликованные категории не показываются на главной и в меню.

### Каркас (`base.html`)

- **Шапка:**
  - логотип и меню: «Услуги» (выпадающий список категорий по группам), «Мероприятия», «О нас», «Отзывы», «Галерея», «Контакты»;
  - на ширине меньше `md` меню прячется в бургер (Alpine.js).
- **Подвал:** адрес (ссылка на `map_url`), все телефоны (`tel:`), иконки WhatsApp, Telegram, VK.
- **Кнопка «Связаться»:** плавающая, только на мобильных; раскрывается в «Позвонить» (первый номер), WhatsApp, Telegram. Пункт мессенджера скрыт, если флаг ни у кого не стоит.
- **Дизайн:** сохраняем логотип, палитру и настроение старого сайта, вёрстку делаем современнее. Палитра — токены в `@theme` Tailwind.

### Страницы

- **Главная** — `home_intro`, затем блоки групп (по `order`) с карточками опубликованных категорий (превью, название). Группа без опубликованных категорий не показывается.
- **Категория:**
  - слайдер фото (Swiper) и описание;
  - список опубликованных услуг по `CategoryService.order`: название и `price_display`;
  - у услуги с `has_page` карточка ведёт на `/service/<slug>/`; у остальных краткое описание раскрывается аккордеоном (если оно есть).
- **Услуга** — слайдер фото, `price_display`, `description`, кнопки связи.
- **Мероприятия:**
  - сверху `events_intro` и фото ближайшего предстоящего мероприятия;
  - карусель Swiper (`loop` только при ≥ 3 слайдах): сначала предстоящие по дате, затем прошедшие с `show_after_date`;
  - при отсутствии мероприятий — заглушка «Скоро анонсируем».
- **О нас** — `about_text`, `philosophy_text`, `nearby_text`, `about_map`, сотрудники (блок скрыт, если их нет), партнёры (логотипы-ссылки).
- **Отзывы** — опубликованные отзывы по `order`, сетка в стиле masonry (CSS columns).
- **Галерея** — сетка миниатюр, лайтбокс с полноразмерным фото.
- **Контакты** — `contacts_text`, `contacts_map`, телефоны и мессенджеры.
- **Инфо-страница** — заголовок и текст.
- **404 / 500** — в общем стиле; шаблон 500 не зависит от БД.

### SEO

- `<title>` и `meta description` у каждой страницы; для категорий и услуг описание — первые ~160 символов текста без тегов.
- Open Graph: `og:title`, `og:description`, `og:image` (превью или первое фото).
- `sitemap.xml` — статические страницы, опубликованные категории, услуги с `has_page`, инфо-страницы; плюс `robots.txt`.

## 6. Админка

- Unfold, `LANGUAGE_CODE="ru"`, вход по `/admin/`, стандартные пользователи и группы Django.
- **Боковое меню** (`UNFOLD["SIDEBAR"]`): Каталог (группы, категории, услуги); Контент (мероприятия, отзывы, галерея, партнёры, сотрудники); Сайт (настройки, инфо-страницы); Доступ (пользователи, группы).
- **Общее:** миниатюры изображений в списках и формах; «Смотреть на сайте» (`get_absolute_url`) у категорий, услуг и инфо-страниц.

| Раздел | Список | Форма |
|---|---|---|
| Настройки сайта | — (пункт меню открывает форму записи `pk=1`; добавление и удаление запрещены) | Вкладки «Контакты» (+ inline `Phone` с перетаскиванием), «Тексты», «Карты» |
| Группы категорий | порядок перетаскиванием | `name`, `categories` (`filter_horizontal`) |
| Категории | превью, название, `is_published` (переключатель), порядок перетаскиванием | Вкладки «Основное» (название, slug, описание, превью, публикация), «Фото» (inline `CategoryPhoto` с перетаскиванием + поле загрузки пачкой), «Услуги» (inline `CategoryService`, `autocomplete_fields=["service"]`, перетаскивание) |
| Услуги | поиск по названию; фильтры: категория, `is_published`, `has_page` | Поля услуги; inline `ServicePhoto` + загрузка пачкой; inline `CategoryService` (`autocomplete_fields=["category"]`) |
| Мероприятия | фото, заголовок, дата; фильтр «Предстоящие / Прошедшие»; `date_hierarchy` | Все поля |
| Отзывы, партнёры, сотрудники | фото, основные поля, порядок перетаскиванием | Все поля |
| Галерея | миниатюры, порядок перетаскиванием; кнопка «Загрузить пачкой» (отдельная admin-view с полем множественной загрузки) | `image`, `caption` |
| Инфо-страницы | заголовок, `is_published` | Все поля |

**Загрузка пачкой** — `forms.FileField` с виджетом, у которого `allow_multiple_selected = True`. Каждый файл проверяется (тип jpg/png/webp по содержимому через Pillow, до 20 МБ) и сохраняется новой фото-записью с `order = max(order) + 1`. Ошибка валидации любого файла отменяет всю пачку и показывает понятное сообщение.

## 7. Импорт старых данных (`import_legacy`)

```
manage.py import_legacy --db <путь к T_Park.db> --images <путь к папке images> [--flush] [--price-csv <путь>]
```

- Старая БД открывается только на чтение (`sqlite3`, `mode=ro`).
- Если в новой БД уже есть контент (хотя бы одна категория, услуга или мероприятие), команда завершается с ошибкой. `--flush` сначала удаляет весь контент и его медиафайлы; пользователей не трогает.
- Весь импорт идёт в одной транзакции. Файлы, скопированные до ошибки, удаляются.
- HTML пропускается через тот же фильтр `nh3`, что и редактор.
- Фото копируются через `ImageField`, поэтому проходят тот же пережим. Порядок фото берётся из числового имени файла (`2.jpg` < `10.jpg`).
- В конце выводится отчёт: сколько записей перенесено по каждой модели, каких файлов не нашлось, какие строки пропущены и почему.

| Старое | Новое | Детали |
|---|---|---|
| `type` | `CategoryGroup` | `number` → `order` |
| `category_type` | `CategoryGroup.categories` | пары с несуществующими id пропускаются |
| `category` | `Category` (**id сохраняется**) | `status` → `is_published`; `number` → `order`; slug из `name`; `images/category/preview/<id>.jpg` → `preview` |
| `images/category/<id>/*` | `CategoryPhoto` | по возрастанию номера |
| `service` | `Service` (**id сохраняется**) | `time` → `price_unit`; `status` → `is_published` (`NULL` → `True`); `next` → `has_page`; slug из `name` |
| `images/service/<id>/*` | `ServicePhoto` | по возрастанию номера |
| `service_category` | `CategoryService` | `number` → `order` (`NULL` → в конец); дубли схлопываются; **6 строк ссылаются на удалённые записи — пропускаются** |
| `event` | `Event` | `after_date` → `show_after_date`; `images/events/<id>.jpg` → `image` (см. риск ниже) |
| `comment` | `Review` | `name` → `author`; `is_published=True`; `order` по `id`; `images/comments/<id>.jpg` → `photo` |
| `partner` | `Partner` | строки с `name="temp"` пропускаются; `name` в данных — это id (артефакт старой админки), поэтому импортируется пустым; `images/partner/<id>.jpg` → `logo`; `order` по `id` |
| `employee` | — | **не импортируется**: все 7 записей — заглушки «Сотрудник» без фото. Блок сотрудников на «О нас» скрыт, пока их не заведут в админке |
| `text` с `title` | `SiteSettings` | `main_text` → `home_intro` и `events_intro`; `about` → `about_text`; `filosofi` → `philosophy_text`; `structure` → `nearby_text`; `contacts_info` → `contacts_text`; `address`; `geolocation` → `map_url`; `vk` → `vk_url` |
| `text.phone_numbers` | `Phone` | номера через пробел → записи по порядку; первому номеру ставится `is_whatsapp`; `is_telegram` ставится номеру, найденному в значении `insta` (`tg://resolve?domain=+7…`) |
| `text` без `title` | `InfoPage` (**id сохраняется**) | `status` → `is_published`; `title` — текст первого `<strong>` или `<h1-3>`, иначе «Страница N»; slug из `title` |
| `images/gallery/*` | `GalleryPhoto` | по возрастанию номера |
| `images/staff/map.jpg`, `map_about.jpg` | `SiteSettings.contacts_map`, `about_map` | — |
| `price` | CSV-файл (`--price-csv`, по умолчанию `price_legacy.csv`) | в БД не переносится |
| `admin`, `alembic_version` | — | не переносятся |

**Известный риск:** фон слайдера старой страницы событий лежит в `images/events/0..2.jpg`, а у мероприятия с `id=2` фото тоже `events/2.jpg`. Импорт ставит этот файл мероприятию 2 и выводит в отчёте предупреждение — после импорта фото нужно проверить вручную. Файлы `0.jpg` и `1.jpg` игнорируются: мероприятий с такими id нет.

**Где взять картинки:** папки `images/` в репозитории нет, её нужно скопировать с текущего продакшен-сервера (`app/static/images`).

## 8. Инфраструктура

### Разработка

```bash
uv sync                                  # зависимости, включая dev
uv run manage.py migrate
uv run manage.py tailwind runserver      # Django + сборка Tailwind в режиме watch
uv run pytest
uv run manage.py import_legacy --db old_version/T_Park.db --images <путь>
```

При `DEBUG=True` Django сам отдаёт `/media/`.

### Docker

- **Dockerfile:**
  - база `ghcr.io/astral-sh/uv:python3.14-bookworm-slim`;
  - сборка: `uv sync --frozen --no-dev` → `manage.py tailwind build` → `collectstatic`;
  - запуск от непривилегированного пользователя;
  - entrypoint: `migrate --noinput`, затем gunicorn (3 sync-воркера; число задаётся переменной окружения).
- **compose.yaml:**
  - `web` — образ приложения, `env_file: .env`, тома `db:/data/db` и `media:/data/media`, healthcheck (HTTP на `/healthz/`), `restart: unless-stopped`;
  - `media` — `nginx:alpine`, том `media` только на чтение, конфиг `docker/nginx-media.conf` (отдаёт `/media/`, долгий кэш, `autoindex off`);
  - оба сервиса во внешней сети `${PROXY_NETWORK}`, наружу порты не открываются;
  - прокси маршрутизирует `/media/` → `media:80`, остальное → `web:8000`; HTTPS делает он.
- **Django за прокси:** `SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS — при `DEBUG=False`.
- **Логи** пишутся в stdout.

### Бэкап

`scripts/backup.sh` запускается cron'ом на хосте:
1. `docker compose exec web python manage.py backup_db /data/db/backup.sqlite3` — management-команда на `sqlite3.Connection.backup()` (консистентный снимок без остановки сайта); файл копируется на хост через `docker compose cp`;
2. `tar` тома `media`;
3. результат складывается в `backups/<дата>/`; хранятся последние N копий (переменная окружения).

### Переезд

1. Развернуть новый сайт на тестовом поддомене, выполнить `import_legacy`, проверить страницы, фото и редиректы.
2. Остановить редактирование в старой админке, выполнить финальный импорт (`--flush`).
3. Переключить домен в прокси на новый сайт.
4. Старый сайт держать выключенным, но не удалять, пока не убедимся, что всё в порядке.

## 9. Тесты

pytest + pytest-django, фабрики — простые хелперы или `model_bakery`.

- **import_legacy:** фикстура — небольшая SQLite со схемой старой БД (DDL из `old_version/T_Park.db`) и несколько картинок в `tmp_path`. Проверяются: маппинг полей, сохранение id, порядок фото, телефоны и флаги, InfoPage, пропуск сирот и `temp`, отказ без `--flush` на непустой БД, атомарность (ошибка посередине — БД пустая).
- **Редиректы:** каждый старый URL → 301 на правильный новый; несуществующий id → 404.
- **Видимость:** 404 для неопубликованной категории, услуги и инфо-страницы и для услуги без `has_page`; скрытые записи не попадают в списки и меню.
- **Phone:** второй `is_whatsapp` или `is_telegram` вызывает `IntegrityError`.
- **Загрузка пачкой:** N файлов → N записей в конце списка; невалидный файл отменяет всю пачку.
- **backup_db:** создаёт валидную копию БД с теми же данными.
- **Smoke:** все публичные страницы отдают 200 на заполненной БД и на пустой (без настроек и мероприятий); в админке у суперпользователя открываются список и форма добавления (или изменения) каждой модели.

Вёрстка и JS автотестами не покрываются.

## 10. Решения, принятые при написании спецификации

Требуют подтверждения при ревью:
- сотрудники не импортируются (все записи — заглушки);
- у партнёров название при импорте пустое;
- `main_text` копируется и во вступление главной, и во вступление мероприятий (в старой версии это был один текст на обеих страницах);
- «предстоящее мероприятие» — `date >= сегодня` по Москве;
- `CLAUDE.md` для нового проекта пишется после каркаса, `old_version/CLAUDE.md` остаётся для старого кода.
