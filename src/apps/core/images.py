import logging
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path

from django.db import transaction
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from imagekit.cachefiles.backends import CacheFileState, Simple
from imagekit.cachefiles.strategies import JustInTime
from imagekit.utils import generate
from PIL import features

logger = logging.getLogger(__name__)

AVIF_SUFFIX = "_avif"
# Без кодировщика AVIF (другая сборка Pillow) <source type="image/avif"> не выводим: миниатюры не создадутся.
AVIF_SUPPORTED = features.check("avif")

# Сколько секунд один запрос может пережимать недостающие миниатюры. Остальные создадут фоновый generateimages
# и следующие запросы: иначе после смены спек галерея (сотни фото × 5 спек) упирается в таймаут gunicorn (30 с) → 500.
REQUEST_GENERATION_BUDGET = 2
_request = threading.local()


class GenerationDeferred(Exception):
    """Миниатюру не создали: запрос исчерпал время на генерацию."""


def start_request_budget(**kwargs) -> None:
    """request_started: отсчёт бюджета генерации для этого запроса (в фоновых потоках и командах — без ограничения)."""
    _request.deadline = time.monotonic() + REQUEST_GENERATION_BUDGET


def end_request_budget(**kwargs) -> None:
    _request.deadline = None


def safe_spec_url(obj, spec_name: str) -> str:
    """URL миниатюры imagekit или пустая строка, если объекта или исходника нет, он битый или миниатюра ещё не создана."""
    if obj is None:
        return ""
    try:
        spec = getattr(obj, spec_name)
        return spec.url if spec else ""
    except GenerationDeferred:
        return ""
    except Exception:
        logger.warning("Не удалось получить %s для %r", spec_name, obj, exc_info=True)
        return ""


def lightbox_url(photo) -> str:
    """Фото для просмотра во весь экран: WebP-спека `full`, без неё — оригинал."""
    if url := safe_spec_url(photo, "full"):
        return url
    try:
        return photo.image.url
    except AttributeError, ValueError:
        return ""


def _entries(srcset: str) -> list[tuple[str, str]]:
    entries = [item.split() for item in srcset.split(",") if item.strip()]
    if not entries or any(len(e) > 2 for e in entries) or (len(entries) > 1 and any(len(e) != 2 for e in entries)):
        raise ValueError(f"Неверный список спек {srcset!r}: нужно «спека» или «спека 640w, спека 800w».")
    return [(e[0], e[1] if len(e) == 2 else "") for e in entries]


def _candidates(obj, entries, suffix: str = "") -> list[tuple[str, str]]:
    """[(url, дескриптор)] по объявленным у модели спекам; битые и отсутствующие пропускаются."""
    found = []
    for name, descriptor in entries:
        name += suffix
        if suffix and not hasattr(type(obj), name):
            continue
        if suffix == AVIF_SUFFIX and not AVIF_SUPPORTED:
            continue
        if url := safe_spec_url(obj, name):
            found.append((url, descriptor))
    return found


def _source_url(obj, spec_name: str) -> str:
    """URL исходного фото спеки, если файл на месте."""
    field = getattr(type(obj), spec_name, None)
    source = getattr(obj, getattr(field, "source", None) or "", None)
    try:
        return source.url if source and source.storage.exists(source.name) else ""
    except ValueError, OSError:
        return ""


def _srcset(candidates) -> str:
    return ", ".join(f"{url} {descriptor}".rstrip() for url, descriptor in candidates)


def _tag(name: str, **attrs) -> str:
    """Тег с атрибутами в порядке вызова (flatatt их сортирует); None и False не выводятся, True — без значения."""
    rendered = format_html_join(
        "",
        "{}",
        (
            (format_html(" {}", k) if v is True else format_html(' {}="{}"', k, v),)
            for k, v in attrs.items()
            if v is not None and v is not False
        ),
    )
    return format_html("<{}{}>", name, rendered)


def picture_html(obj, srcset: str, *, sizes: str = "", wide: str = "", media: str = "", **attrs) -> str:
    """`<picture>`: AVIF-двойники спек (`<спека>_avif`) в `<source>`, WebP — в `<img>`.

    srcset — «спека» или «спека 640w, спека 800w» (src — последняя); wide + media — другой кадр
    для широких экранов (`<source media>`). Атрибуты `<img>` с пустым значением не выводятся, кроме alt.
    Пустая строка, если ни одной миниатюры нет (исходника нет или он битый).
    """
    if obj is None:
        return ""
    entries = _entries(srcset)
    webp = _candidates(obj, entries)
    if not webp:
        # Миниатюры ещё нет (запрос исчерпал время на генерацию) — оригинал, чтобы фото не пропадало со страницы.
        source = _source_url(obj, entries[-1][0])
        return _tag("img", src=source, **{k: v for k, v in attrs.items() if k == "alt" or v != ""}) if source else ""
    multi = any(descriptor for _, descriptor in entries)
    sources = []
    if wide:
        wide_entries = _entries(wide)
        wide_sizes = sizes if any(descriptor for _, descriptor in wide_entries) else None
        for suffix, mime in ((AVIF_SUFFIX, "image/avif"), ("", "image/webp")):
            if found := _candidates(obj, wide_entries, suffix):
                sources.append(_tag("source", media=media, type=mime, srcset=_srcset(found), sizes=wide_sizes))
    if avif := _candidates(obj, entries, AVIF_SUFFIX):
        sources.append(_tag("source", type="image/avif", srcset=_srcset(avif), sizes=sizes if multi else None))
    img_attrs = {"src": webp[-1][0]}
    if multi:
        img_attrs |= {"srcset": _srcset(webp), "sizes": sizes or None}
    img_attrs |= {k: v for k, v in attrs.items() if k == "alt" or v != ""}
    img = _tag("img", **img_attrs)
    return mark_safe(f"<picture>{''.join(sources)}{img}</picture>") if sources else img


_executor: ThreadPoolExecutor | None = None


def run_in_background(fn) -> None:
    """Один фоновый поток на процесс: пережатие не отнимает все ядра у запросов."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="thumbnails")
    _executor.submit(fn)


def _generate(file) -> None:
    try:
        file.generate()
    except Exception:
        logger.warning("Не удалось создать миниатюру %s", file.name, exc_info=True)


class GenerateAfterCommit(JustInTime):
    """Как JustInTime (недостающая миниатюра создаётся при показе), но после сохранения фото все его миниатюры
    сразу создаются в фоне: первый посетитель не ждёт пережатия, а загрузка пачкой не упирается в таймаут gunicorn."""

    def on_source_saved(self, file):
        transaction.on_commit(lambda: run_in_background(partial(_generate, file)))


def _save_atomically(file) -> None:
    """Пишет миниатюру во временный файл рядом и переименовывает: читатель видит либо целый файл, либо никакого
    (недописанный файл после SIGKILL или параллельной генерации иначе отдавался бы вечно)."""
    content = generate(file.generator)
    path = Path(file.storage.path(file.name))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            shutil.copyfileobj(content, out)
        os.chmod(tmp, file.storage.file_permissions_mode or 0o644)  # mkstemp создаёт 0600, а nginx читает от себя
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class AtomicBackend(Simple):
    """Backend imagekit (`IMAGEKIT_DEFAULT_CACHEFILE_BACKEND`) с двумя исправлениями `Simple`:

    - ошибка генерации не оставляет состояние «создаётся» навсегда — иначе со второго показа сайт отдавал бы
      URL несуществующего файла (битый AVIF в `<source>` ломает и запасной WebP);
    - «создаётся» в другом потоке — не повод отдавать URL: если файла ещё нет, создаём сами (запись атомарная,
      так что двойная генерация безвредна).
    """

    def generate_now(self, file, force=False):
        state = None if force else self.get_state(file)
        if state == CacheFileState.EXISTS:
            return
        if state == CacheFileState.GENERATING and self._exists(file):
            self.set_state(file, CacheFileState.EXISTS)
            return
        deadline = getattr(_request, "deadline", None)
        if deadline is not None and time.monotonic() > deadline:
            raise GenerationDeferred(file.name)
        self.set_state(file, CacheFileState.GENERATING)
        try:
            _save_atomically(file)
        except Exception:
            self.set_state(file, CacheFileState.DOES_NOT_EXIST)  # проверим снова через existence_check_timeout
            raise
        self.set_state(file, CacheFileState.EXISTS)
