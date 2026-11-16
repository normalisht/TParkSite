# Видео и подборки в галерее — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** вкладка «Видео» в галерее с роликами Дзена (обложка, название, описание, длительность) и подборками
роликов со своими страницами; бэкап хранит один архив медиа.

**Architecture:** новые модели `Video`, `VideoCollection`, `VideoCollectionItem` в `apps/content`; данные ролика
(название, описание, длительность, обложка) — со страницы плеера `dzen.ru/embed/<id>` при сохранении формы
(`apps/content/dzen.py`). Витрина — `/gallery/video/` и `/gallery/video/<slug>/`, ролик играет в GLightbox
слайдом с iframe Дзена, который создаётся только по клику и выгружается при перелистывании/закрытии.

**Tech Stack:** Django 6.1, Unfold, imagekit (`image_specs`), Tailwind, Alpine, GLightbox 3.3.1 (vendored),
pytest + playwright (e2e).

**Spec:** `docs/superpowers/specs/2026-11-13-gallery-video-design.md` — читать вместе с планом.

## Global Constraints

- Команды Python — из `src/`: `uv run pytest`, `uv run ruff check . && uv run ruff format .`; e2e — `make e2e`
  (нужен `uv run manage.py tailwind build`).
- pytest строгий, любое предупреждение — ошибка: файлы и соединения закрывать, сеть в тестах не трогать.
- Не коммитить: коммиты, пуш и MR — только по просьбе пользователя (его `CLAUDE.md`). Шаги «commit» в плане нет.
- Тексты витрины и админки — по-русски; комментарии — по-русски, объясняют «зачем», 1–3 строки.
- Админки — от `apps.core.admin_utils.SiteModelAdmin`; новый упорядоченный inline — с `OrderedInlineMixin`.
- Фото — `photo_field`, миниатюры — `image_specs`, вывод — `{% picture %}`; удаление файлов — `register_file_cleanup`.
- В публичных шаблонах нет значений, зависящих от запроса (ETag/304). До клика — ни iframe, ни запросов к `dzen.ru`.
- Ссылка ролика хранится нормализованной: `https://dzen.ru/embed/<id>`, `id` — `[A-Za-z0-9_-]+`, без параметров.
- Текст ошибки поля видео — дословно: «Нужен код из Дзена: под видео „⋯“ → „Поделиться“ → „Встроить“,
  скопируйте код целиком. Обычная ссылка на видео (dzen.ru/video/watch/…) не подойдёт».
- iframe плеера: `allow="autoplay; fullscreen; picture-in-picture; encrypted-media"`, `allowfullscreen`, `title`;
  `href` без `autoplay`.
- Кнопка ▶: фон `brand-500`, треугольник `ink`, hover `brand-600` + `scale(1.08)`; 56 px от `md`, 44 px ниже.
  Рамка просмотра: 16:9, `#000`, радиус 12 px, ширина `min(1100px, 100vw − 32px, (100vh − 160px) · 16/9)`.
- Показ порциями — `GALLERY_PAGE = 24`, как у фото (все карточки в HTML, `hidden` после первой порции).
- Сначала делается первый вариант дизайна каждого пункта (карточка — сетка 16:9; подборки — полка обложек).

## Review Focus

1. Администратор вставляет код «Встроить» с переводами строк, `&amp;`, параметрами (`?from=…`) или ссылку
   с `/embed/<id>/` на конце — сохраняется ровно `https://dzen.ru/embed/<id>` (Task 1, `test_extract_embed_url_*`).
2. Правка подписи/подборок существующего ролика без смены кода — ни одного запроса к Дзену, данные не меняются
   (Task 3, `test_edit_without_url_change_does_not_fetch`).
3. Дзен отдал страницу без `thumbnail` или без `duration` (вертикальный ролик, смена разметки): без обложки —
   ошибка формы, если своей обложки нет; без длительности — сохраняется с `duration=None`, плашки нет
   (Task 1 `test_parse_video_page_without_duration`, Task 3 `test_fetch_without_thumbnail_requires_poster`).
4. Ролик снят с публикации — пропадает из всех подборок на витрине, счётчики считают только опубликованные;
   подборка, где не осталось опубликованных роликов, — 404 и не в sitemap (Task 4 `test_collection_hides_unpublished`).
5. Посетитель закрывает просмотр или листает, пока ролик играет, — iframe с `dzen.ru` удалён/обнулён
   (Task 5 e2e `test_video_iframe_unloaded_on_next_and_close`).

---

### Task 1: Ссылка и данные ролика с Дзена (`apps/content/dzen.py`)

**Files:**
- Create: `src/apps/content/dzen.py`
- Create: `src/tests/test_dzen.py`, `src/tests/fixtures/dzen_embed.html` (урезанная страница плеера:
  `<title>Т-парк. Фрироуп 3. Железный век</title>`, JSON с `"description":"Это третье видео…"`, `"duration":925`,
  `"thumbnail":"https://avatars.dzeninfra.ru/get-zen_doc/123/abc/smart_crop_516x290"`)

**Interfaces:**
- Produces:
  - `extract_embed_url(value: str) -> str` — из кода `<iframe>` или ссылки достаёт `src`, `html.unescape`, режет
    query/fragment и хвостовой `/`; не-Дзен возвращает как есть (валидатор потом отклонит).
  - `validate_embed_url(value: str) -> None` — `ValidationError(<текст из Global Constraints>)`, если не
    `https://dzen.ru/embed/<id>`.
  - `DzenEmbedFormField(forms.URLField)`, `DzenEmbedURLField(models.URLField)` — как `MapEmbedFormField`/
    `MapEmbedURLField` в `apps/core/maps.py` (Textarea `rows=3`, без `maxlength` у виджета).
  - `@dataclass(frozen=True) DzenVideo(title: str, description: str, duration: int | None, thumbnail_url: str)`
  - `class DzenFetchError(Exception)` — текст для админки.
  - `parse_video_page(page: str) -> DzenVideo`; `fetch_video(embed_url: str) -> DzenVideo`
  - `download_poster(thumbnail_url: str) -> ContentFile` — сначала адрес с `orig` вместо последнего сегмента, при
    ошибке — исходный; только `https://avatars.dzeninfra.ru/`; лимит 10 МБ; результат проходит
    `apps.core.fields.validate_image_upload`; имя файла — `poster.jpg`.
  - `format_duration(seconds: int | None) -> str` — `"15:25"`, `"1:02:03"`, `""` для `None`.

- [ ] **Step 1: Тесты**

```python
@pytest.mark.parametrize("value", [
    '<iframe width="560" src="https://dzen.ru/embed/oakZI1TIPAAA?from_block=partner&amp;mute=0" allow="autoplay"></iframe>',
    "  https://dzen.ru/embed/oakZI1TIPAAA/ \n",
    "https://dzen.ru/embed/oakZI1TIPAAA#t=10",
])
def test_extract_embed_url_normalizes(value):
    assert extract_embed_url(value) == "https://dzen.ru/embed/oakZI1TIPAAA"

@pytest.mark.parametrize("url", [
    "https://dzen.ru/video/watch/6af4c9206275f93a7e1ff96b", "http://dzen.ru/embed/abc",
    "https://evil.ru/embed/abc", "https://dzen.ru/embed/", "https://dzen.ru/embed/a/b",
])
def test_validate_embed_url_rejects(url):
    with pytest.raises(ValidationError, match="Поделиться"):
        validate_embed_url(url)

def test_parse_video_page(fixture_page):
    assert parse_video_page(fixture_page) == DzenVideo(
        "Т-парк. Фрироуп 3. Железный век", "Это третье видео…", 925,
        "https://avatars.dzeninfra.ru/get-zen_doc/123/abc/smart_crop_516x290")

def test_parse_video_page_without_duration(fixture_page): ...      # duration is None, остальное есть
def test_parse_video_page_garbage_raises(): ...                    # DzenFetchError на "<html></html>"
def test_fetch_video_rejects_redirect_off_dzen(monkeypatch): ...   # редирект на evil.ru → DzenFetchError
def test_fetch_video_network_error(monkeypatch): ...               # OSError → DzenFetchError
def test_fetch_video_too_large(monkeypatch): ...                   # > MAX_PAGE_BYTES → DzenFetchError
def test_download_poster_prefers_orig(monkeypatch, make_image): ...  # запрошен .../orig, получен ContentFile
def test_download_poster_falls_back_to_original(monkeypatch, make_image): ...
def test_download_poster_rejects_foreign_host(): ...               # https://evil.ru/x.jpg → DzenFetchError
@pytest.mark.parametrize(("s", "text"), [(None, ""), (5, "0:05"), (925, "15:25"), (3723, "1:02:03")])
def test_format_duration(s, text): ...
```

Сеть подменяется на уровне opener модуля (`monkeypatch.setattr(dzen, "_opener", FakeOpener(...))`), как в
`tests/test_yandex_reviews.py`.

- [ ] **Step 2:** `uv run pytest tests/test_dzen.py` — FAIL (`ModuleNotFoundError: apps.content.dzen`).
- [ ] **Step 3:** реализовать по образцу `apps/content/yandex.py` (`TIMEOUT = 10`, тот же `USER_AGENT`,
  `MAX_PAGE_BYTES = 5 МБ`, свой `HTTPRedirectHandler`, пропускающий только `dzen.ru` для страницы и
  `avatars.dzeninfra.ru` для картинки). Название — `<title>` (`html.unescape`, без суффикса « | Дзен», если есть),
  при отсутствии — `"title"` из JSON; поля JSON искать регуляркой по `"duration":(\d+)`, `"thumbnail":"(…)"`,
  `"description":"(…)"` с `json.loads('"…"')` для экранирования. Нет названия или обложки — `DzenFetchError`.
- [ ] **Step 4:** `uv run pytest tests/test_dzen.py` — PASS.

### Task 2: Модели и миграция

**Files:**
- Modify: `src/apps/content/models.py` (в конец), `src/apps/content/apps.py` (`register_file_cleanup` для `Video`,
  `VideoCollection`)
- Create: `src/apps/content/migrations/0015_video.py` (`makemigrations content -n video`)
- Test: `src/tests/test_video_models.py`

**Interfaces:**
- Consumes: `DzenEmbedURLField` (Task 1).
- Produces:
  - `Video(OrderedModel)`: `embed_url = DzenEmbedURLField("Видео с Дзена", max_length=255, unique=True)`,
    `title = CharField("Название", 255)`, `description = TextField("Описание", blank=True)`,
    `duration = PositiveIntegerField("Длительность, сек", null=True, blank=True)`,
    `poster = photo_field("Обложка", "gallery/video", blank=True)` (в БД может быть пусто только до сохранения
    формы — форма гарантирует обложку), `is_published = BooleanField("Опубликовано", default=True)`,
    `updated_at = DateTimeField(auto_now=True)`,
    `collections = ManyToManyField("VideoCollection", through="VideoCollectionItem", related_name="videos", blank=True)`;
    спеки `card, card_avif = image_specs("poster", 800, 450)`, `card_small, card_small_avif = image_specs("poster", 480, 270)`,
    `square, square_avif = image_specs("poster", 400, 400)`, `og = og_spec("poster")`;
    `objects = PublishedQuerySet.as_manager()`; `verbose_name = "Видео"`, `verbose_name_plural = "Видео"`;
    `__str__` → `title`; свойство `duration_text -> str` = `format_duration(self.duration)`.
  - `VideoCollection(SeoModel, OrderedModel)`: `title = CharField("Название", 255)`,
    `slug = SlugField("Адрес страницы", 255, unique=True, blank=True, help_text=SLUG_HELP)`,
    `description = TextField("Описание", blank=True)`, `cover = photo_field("Обложка", "gallery/collections")`
    (необязательная), `is_published = BooleanField("Опубликовано", default=True)`;
    спеки `cover_square, cover_square_avif = image_specs("cover", 400, 400)`, `cover_og = og_spec("cover")`;
    `objects = VideoCollectionQuerySet.as_manager()`; `verbose_name = "Подборка видео"`,
    `verbose_name_plural = "Подборки видео"`; `save()` — `unique_slug` + `remember_slug_change` +
    `remember_page_change` в `transaction.atomic()`, как `InfoPage.save`; `slug_source() -> str` = `title`;
    `get_absolute_url()` → `reverse("content:video_collection", args=[self.slug])`;
    `shown_videos() -> list[Video]` — опубликованные ролики подборки по `VideoCollectionItem.order, id`;
    `cover_video` (cached_property) → первый из `shown_videos()` или `None`.
  - `VideoCollectionQuerySet(PublishedQuerySet).shown()` — опубликованные, где есть опубликованный ролик,
    с аннотацией `video_count` (только опубликованные), порядок `order, id`.
  - `VideoCollectionItem(models.Model)`: `collection` FK `related_name="items"`, `video` FK
    `related_name="collection_items"`, оба `CASCADE`; `order = PositiveIntegerField("Порядок", default=0)`;
    `UniqueConstraint(fields=["collection", "video"], name="unique_video_in_collection")`;
    `ordering = ["order", "id"]`; `verbose_name = "Видео в подборке"`.

- [ ] **Step 1: Тесты**

```python
def test_collection_shown_counts_only_published(make_video, make_collection):
    c = make_collection("Услуги"); a, b = make_video(), make_video(is_published=False)
    add(c, a, b)
    [shown] = VideoCollection.objects.shown()
    assert shown.video_count == 1 and c.shown_videos() == [a]

def test_collection_without_published_videos_not_shown(...): ...   # не в shown()
def test_unpublished_collection_not_shown(...): ...
def test_video_in_two_collections_keeps_own_order(...): ...        # order в каждой подборке свой
def test_collection_slug_from_title_and_redirect_on_change(...): ... # "Услуги" → "uslugi"; смена → Redirect
def test_duplicate_video_rejected(...): ...                         # full_clean() на тот же embed_url
def test_deleting_video_removes_items(...): ...
```

`make_video`/`make_collection` — фикстуры в `tests/conftest.py` (видео с `poster=make_image()`, уникальный
`embed_url=f"https://dzen.ru/embed/v{n}"`).

- [ ] **Step 2:** `uv run pytest tests/test_video_models.py` — FAIL (ImportError).
- [ ] **Step 3:** модели + `makemigrations content -n video` + `register_file_cleanup` в `ContentConfig.ready`.
- [ ] **Step 4:** `uv run pytest tests/test_video_models.py tests/test_content_models.py` — PASS;
  `uv run manage.py makemigrations --check` — «No changes detected».

### Task 3: Админка «Видео» и «Подборки видео»

**Files:**
- Modify: `src/apps/content/admin.py`, `src/config/settings.py` (`UNFOLD["SIDEBAR"]`, после «Галереи»:
  `_nav("Видео", "smart_display", "admin:content_video_changelist")`,
  `_nav("Подборки видео", "video_library", "admin:content_videocollection_changelist")`),
  `src/templates/admin/help/sections/gallery.html`, `src/tests/test_admin_help.py` (если сверяет список полей)
- Test: `src/tests/test_admin_video.py`

**Interfaces:**
- Consumes: Task 1 (`fetch_video`, `download_poster`, `DzenFetchError`, `format_duration`), Task 2 (модели).
- Produces:
  - `VideoAdminForm(forms.ModelForm)`; в `clean()` при `"embed_url" in self.changed_data` (и при добавлении)
    вызывает `fetch_video` и, если нужна обложка, `download_poster`; результат — в `self.dzen: DzenVideo | None`
    и `self.dzen_poster: ContentFile | None`. Правила заполнения — спецификация, «Данные с Дзена»
    (новая запись: только пустые поля; смена ролика: всё, кроме полей из `changed_data`; длительность — всегда).
    Ошибка Дзена → `add_error("embed_url", f"Не удалось получить данные ролика с Дзена: {exc} Попробуйте позже или заполните название и загрузите обложку вручную.")`,
    кроме случая, когда в форме есть и название, и обложка (тогда `duration=None`).
  - `VideoAdmin(OrderedPhotoAdmin)`: `form = VideoAdminForm`; `fields = ["embed_url", "title", "description", "poster", "is_published"]`;
    `title` не обязателен в форме (заполнится); inline `VideoCollectionItemInline` (fk `video`, поле `collection`,
    `extra=0`), новым связям в `save_formset` — `order = next_order(VideoCollectionItem, collection=item.collection)`;
    `list_display = ["preview", "title", "collections_list", "is_published"]`, `list_editable = ["is_published"]`,
    `list_filter = ["is_published", "collections"]`, `search_fields = ["title"]`, `list_per_page = 400`,
    действие `move_to_top`; `preview` — обложка `card_small` 96 px + «▶ 15:25» под ней.
  - `VideoCollectionAdmin(SeoGenerateMixin, OrderedPhotoAdmin)`: `fieldsets` — «Основное»
    (`title`, `slug`, `description`, `cover`, `is_published`) + `SEO_FIELDSET`; `seo_source_fields = ("title", "description")`;
    `slug_source_fields = ("title",)`; inline `CollectionVideoInline(OrderedInlineMixin, TabularInline)` на
    `VideoCollectionItem` (fk `collection`, `fields = ["video", "order"]`, `ordering_field = "order"`,
    `hide_ordering_field = True`, `autocomplete_fields = ["video"]`, `extra = 0`);
    `list_display = ["preview", "title", "video_count", "is_published"]`.
  - Обе: `help_anchor = "gallery"`, `help_intro` — 1–2 предложения (как добавить ролик / собрать подборку).

- [ ] **Step 1: Тесты** (`fetch_video`/`download_poster` подменяются в `apps.content.admin` через monkeypatch)

```python
def test_add_video_fills_from_dzen(admin_client, fake_dzen):
    post_add(admin_client, embed_url=IFRAME_CODE, title="", description="")
    v = Video.objects.get()
    assert (v.embed_url, v.title, v.duration) == ("https://dzen.ru/embed/oakZI1TIPAAA", "Т-парк. Фрироуп 3. Железный век", 925)
    assert v.description.startswith("Это третье") and v.poster

def test_add_video_keeps_admin_title_and_poster(...): ...            # своё название и обложка не перезаписаны
def test_change_video_url_replaces_unchanged_fields(...): ...       # новое название/обложка, кроме изменённых в той же отправке
def test_edit_without_url_change_does_not_fetch(...): ...           # fake_dzen.calls == 0
def test_dzen_error_is_form_error(...): ...                         # 200 с ошибкой у поля, Video.objects.count() == 0
def test_dzen_error_allowed_with_manual_title_and_poster(...): ...  # сохранено, duration is None
def test_fetch_without_thumbnail_requires_poster(...): ...
def test_watch_link_rejected_with_hint(...): ...                    # «Поделиться» в тексте ошибки
def test_video_added_to_collection_goes_last(...): ...
def test_collection_inline_reorders_videos(...): ...
def test_new_admin_pages_open(admin_client): ...                    # changelist/add обеих — 200
```

- [ ] **Step 2:** `uv run pytest tests/test_admin_video.py` — FAIL.
- [ ] **Step 3:** реализовать админки, меню, справку (что делать: «Поделиться → Встроить»; пустые поля заполнятся
  с Дзена; реклама и рекомендации — от Дзена; удалённый на Дзене ролик удалить и с сайта; как собрать подборку и
  менять порядок).
- [ ] **Step 4:** `uv run pytest tests/test_admin_video.py tests/test_admin_help.py tests/test_admin.py` — PASS.

### Task 4: Витрина — вкладки, «Видео», подборки, SEO, sitemap, CSP

**Files:**
- Modify: `src/apps/content/urls.py`, `src/apps/content/views.py`, `src/templates/content/gallery.html`,
  `src/apps/core/sitemaps.py`, `src/apps/core/seo.py`, `src/apps/core/models.py` (`seo_video_title`,
  `seo_video_description = _seo_pair("Видео")`), `src/apps/core/admin.py` (страница `"video"` в списке SEO),
  `src/apps/texts/registry.py`, `src/apps/core/templatetags/site_tags.py` (фильтр `duration`), `src/config/settings.py`
  (`frame-src` + `https://dzen.ru`)
- Create: `src/templates/content/gallery_video.html`, `src/templates/content/video_collection.html`,
  `src/templates/content/partials/gallery_tabs.html`, `src/templates/content/partials/video_card.html`,
  `src/templates/content/partials/video_collections.html`; миграции `core` (SEO-поля) и `texts` (`sync_texts`,
  по образцу `apps/texts/migrations/0004_hours_note.py`)
- Test: `src/tests/test_gallery_video.py`

**Interfaces:**
- Consumes: Task 2 (`Video`, `VideoCollection.objects.shown()`, `shown_videos()`, `cover_video`), Task 1 (`format_duration`).
- Produces:
  - URL `content:gallery_video` → `gallery/video/`, `content:video_collection` → `gallery/video/<slug:slug>/`.
  - `gallery_video(request)` — 404 без опубликованных роликов; контекст `videos`, `collections`, `page_size`,
    `has_videos=True`, `seo=page_seo("video")`, крошки «Главная / Галерея / Видео».
  - `video_collection(request, slug)` — `get_for_view`; 404, если у подборки нет опубликованных роликов;
    контекст `collection`, `videos`, `other_collections`, `seo=make_seo(...)` (og — `cover_og` или `og` у
    `cover_video`), крошки «… / Видео / <title>».
  - `gallery()` получает `has_videos` (`Video.objects.published().exists()`).
  - Шаблонная часть: `{% include "content/partials/gallery_tabs.html" with active="photo|video" %}` (нет `has_videos` — ничего);
    `{% include "content/partials/video_card.html" with video=… gallery="video" %}` — `<a class="glightbox …"
    href="{{ video.embed_url }}" data-type="external" data-gallery="{{ gallery }}" data-title="{{ video.title }}"
    aria-label="Видео: {{ video.title }}">`; фильтр `{{ video.duration|duration }}`.
  - Тексты (`TextDef` в разделе «Галерея»): `gallery.tab_photo` «Фото», `gallery.tab_video` «Видео»,
    `gallery.video_lead` «Видео из жизни парка», `gallery.collections_title` «Подборки»,
    `gallery.all_videos_title` «Все видео», `gallery.other_collections_title` «Другие подборки».
  - `PAGE_DEFAULTS["video"] = ("Видео Т-Парка — ролики о парке, Калужская область", f"Видео Т-Парка: верёвочный парк, сплавы, тренинги и праздники на природе. {PARK_ADDRESS}.")`,
    `STATIC_PAGES["video"] = ("Видео", "/gallery/video/", None)`.
  - Sitemap: `"content:gallery_video"` в `StaticSitemap.PAGES` (lastmod — новейший `updated_at` опубликованных
    роликов; без роликов — пункта нет), `VideoCollectionSitemap(ModelSitemap)` по `shown()`, ключ `"video_collections"`.

Вариант дизайна 1 (см. спецификацию, «Варианты дизайна»): карточка — сетка `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`,
обложка `aspect-video rounded-xl`, `{% picture video "card_small 480w, card 800w" sizes=… %}`, ▶ и длительность поверх,
ниже название (`line-clamp-2`, `font-semibold`), описание (`line-clamp-2 text-ink/65`), подборки чипами-ссылками.
Подборки — полка над «Все видео»: `.scroll-strip`, квадратные карточки 160–200 px с `{% picture %}` по
`cover_square` (или `square` у `cover_video`), значок числа роликов, название; карточка — ссылка на подборку.
Шапка подборки — обложка, название, описание, «N видео», ссылка «← Все видео»; внизу — «Другие подборки» той же полкой.

- [ ] **Step 1: Тесты**

```python
def test_tabs_hidden_without_videos(client, make_image): ...      # /gallery/ без "gallery/video/", /gallery/video/ → 404
def test_tabs_on_both_pages(client, make_video): ...              # aria-current="page" у активной вкладки
def test_video_card_markup(client, make_video):
    v = make_video(title="Фрироуп", duration=925)
    html = client.get("/gallery/video/").content.decode()
    assert 'href="https://dzen.ru/embed/' in html and 'data-type="external"' in html
    assert "15:25" in html and 'aria-label="Видео: Фрироуп"' in html
    assert "<iframe" not in html and html.count("dzen.ru") == html.count('href="https://dzen.ru/embed/')
def test_unpublished_video_hidden(...): ...
def test_collection_page_order_and_count(...): ...                # порядок items, «2 видео»
def test_collection_hides_unpublished(...): ...                   # все ролики сняты → 404, нет в sitemap
def test_collection_draft_preview_for_staff(...): ...             # плашка «Черновик», noindex
def test_collection_slug_change_redirects(...): ...               # 301 со старого адреса
def test_video_counter(...): ...                                  # «3 видео · 2 подборки»
def test_videos_after_page_size_hidden(...): ...                  # 25-я карточка с hidden
def test_sitemap_has_video_pages(...): ...
def test_video_pages_etag_304(client, make_video): ...            # повторный GET с If-None-Match → 304
def test_csp_allows_dzen_frames(settings): ...                    # "https://dzen.ru" in frame-src
```

- [ ] **Step 2:** `uv run pytest tests/test_gallery_video.py` — FAIL.
- [ ] **Step 3:** реализовать (шаблоны — по стилям `tailwind/source.css`: `.page-hero`, `.page-title`, `.page-lead`,
  `.scroll-strip`; `{% text %}` для всех подписей; `vendor.html` с `glightbox=1`).
- [ ] **Step 4:** `uv run pytest tests/test_gallery_video.py tests/test_texts.py tests/test_seo.py tests/test_pages.py tests/test_indexing.py` — PASS.

### Task 5: Просмотр ролика — GLightbox, рамка 16:9, выгрузка iframe

**Files:**
- Modify: `src/static/js/site.js` (инициализация GLightbox), `src/tailwind/source.css` (классы кнопки, плашки,
  рамки; блок GLightbox ~стр. 98)
- Test: `src/tests/e2e/test_video_lightbox.py`

**Interfaces:**
- Consumes: разметка карточки из Task 4 (`a.glightbox[data-type="external"]`).
- Produces: CSS-классы `.video-play`, `.video-duration` (Task 4 их использует) и правила рамки — по CSS макета
  (спецификация, «Витрина»; на узком экране `.gslide-description` у слайда с `.gslide-external` — `position: static`,
  под рамкой).

- [ ] **Step 1: e2e-тесты** — `page.route("https://dzen.ru/**", lambda r: r.fulfill(body="<html><body>stub</body></html>", content_type="text/html"))`

```python
def test_video_opens_in_16_9_frame_with_allow(live_server, browser, make_video):
    ...  # клик по карточке → .gslide.current iframe[src^="https://dzen.ru/embed/"]
    assert "autoplay" in iframe.get_attribute("allow") and iframe.get_attribute("allowfullscreen") is not None
    box = iframe.bounding_box(); assert abs(box["width"] / box["height"] - 16 / 9) < 0.02

def test_no_dzen_requests_before_click(live_server, browser, make_video): ...   # счётчик route == 0 до клика
def test_video_iframe_unloaded_on_next_and_close(...): ...    # после .gnext — нет iframe с dzen src вне текущего слайда; после Escape — нет вовсе
def test_caption_below_frame_on_phone(...): ...               # 390×844: description.top >= frame.bottom
```

- [ ] **Step 2:** `make e2e` (или `uv run pytest tests/e2e/test_video_lightbox.py -m e2e`) — FAIL.
- [ ] **Step 3:** реализовать в `site.js`: атрибуты iframe ставятся до его загрузки (GLightbox `external` создаёт
  iframe только с `src` — проверено по `glightbox.min.js`: функция создания iframe получает лишь `url`); выгрузка —
  по `slide_changed` (у `prev`) и `close`. Способ — на выбор исполнителя (свой iframe в `slide_before_load`/
  `slide_after_load`, слайд `inline` и т. п.), vendored-файл не править, iframe ради атрибута не перезагружать.
- [ ] **Step 4:** `make e2e` — PASS; `uv run pytest tests/test_static.py` — PASS.

### Task 6: Бэкап — один архив медиа

**Files:**
- Modify: `scripts/backup.sh`, `README.md` (раздел про бэкап)

**Interfaces:** `BACKUP_MEDIA_KEEP` (по умолчанию `1`) рядом с `KEEP`.

- [ ] **Step 1:** после создания `media.tar.gz` (обе ветки, до общей очистки) — удалить `media.tar.gz` из всех
  `backups/20*/`, кроме `BACKUP_MEDIA_KEEP` новейших:
  `ls -1dt backups/20*/ | tail -n +$((MEDIA_KEEP + 1)) | while read -r d; do rm -f "${d}media.tar.gz"; done`.
  Комментарий в шапке скрипта — что хранится.
- [ ] **Step 2: Проверка вручную** (в `scratchpad`): копия скрипта с замоканными `docker`/`uv` не нужна — проверить
  строку очистки на подготовленных папках: 16 папок с `db.sqlite3` и `media.tar.gz` → после запуска 14 папок,
  `media.tar.gz` только в новейшей. `bash -n scripts/backup.sh` — без ошибок. Итог описать в ответе.

### Task 7: Документация и полная проверка

**Files:**
- Modify: `CLAUDE.md` (Architecture → `apps/content`: видео, подборки, `dzen.py`, вкладки; бэкап — один архив
  медиа), `docs/decisions.md` (Дзен вместо своего хостинга; отдельная модель `Video`; без `VideoObject`)

- [ ] **Step 1:** обновить документы.
- [ ] **Step 2:** `cd src && uv run pytest` — PASS; `uv run ruff check . && uv run ruff format --check .` — чисто;
  `cd .. && uv run --project src pre-commit run --all-files` — чисто; `make e2e` — PASS.

### Task 8: Варианты дизайна для выбора

**Files:**
- Create: `src/templates/content/partials/video_card_list.html` (вариант 2), `video_card_featured.html` (3),
  `video_collections_chips.html` (2), `video_collections_shelves.html` (3)
- Modify: `src/apps/content/views.py` (выбор варианта)

**Interfaces:** параметры `?card=1|2|3&collections=1|2|3` читаются только при `settings.DEBUG`; иначе — вариант 1.

- [ ] **Step 1:** сверстать варианты по описанию в спецификации («Варианты дизайна»), на тех же классах.
- [ ] **Step 2:** снять скриншоты (ПК 1280×800 и телефон 390×844) всех вариантов на локальном сервере с реальными
  роликами канала (несколько роликов и подборок, добавленных через админку на копии базы); показать пользователю.
- [ ] **Step 3 (после выбора):** выбранный вариант — в основной шаблон, остальные шаблоны и переключатель удалить,
  тесты Task 4/5 поправить под выбранную разметку, снова Task 7 Step 2.
