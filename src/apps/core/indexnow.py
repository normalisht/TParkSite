"""IndexNow: после сохранения записи сообщаем Яндексу адрес её страницы — переобход за часы, а не за дни.

Ключ — `INDEXNOW_KEY` (8–128 символов: латиница, цифры, дефис), файл с ним отдаёт `/<ключ>.txt` (`views.indexnow_key`).
Без ключа или `CANONICAL_HOST` ничего не отправляется. Протокол общий: Яндекс передаёт адреса другим поисковикам IndexNow.
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

API_URL = "https://yandex.com/indexnow"
TIMEOUT = 10
# Один адрес Яндекс просит присылать не чаще раза в 10 минут: повтор раньше откладываем, а не теряем.
RESEND_AFTER = 600

_pending: set[str] = set()
_sent_at: dict[str, float] = {}
_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def enabled() -> bool:
    return bool(settings.INDEXNOW_KEY and settings.CANONICAL_HOST)


def _is_public(obj) -> bool:
    return obj.is_published and not obj.in_trash and getattr(obj, "has_page", True)


def remember_page_change(instance) -> None:
    """Вызывать в `save()` до записи, как `remember_slug_change`. После коммита уходит адрес страницы, если она открыта,
    и прежний адрес, если была открыта: снятую с публикации или переименованную страницу поисковик тоже переобойдёт."""
    if not enabled():
        return
    paths = set()
    if instance.pk is not None:
        old = type(instance)._default_manager.filter(pk=instance.pk).first()
        if old is not None and _is_public(old):
            paths.add(old.get_absolute_url())
    if _is_public(instance):
        paths.add(instance.get_absolute_url())
    if paths:
        urls = [f"https://{settings.CANONICAL_HOST}{path}" for path in sorted(paths)]
        transaction.on_commit(lambda: notify(urls))


def notify(urls) -> None:
    with _lock:
        _pending.update(urls)
    run_in_background(_flush)


def run_in_background(fn) -> None:
    """Свой поток: ожидание ответа Яндекса не должно задерживать сохранение и другие фоновые задачи."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexnow")
    _executor.submit(fn)


def _flush() -> None:
    """Отправляет одним запросом всё накопленное (пачка из списка админки — один запрос), кроме недавно отправленного."""
    try:
        now = time.monotonic()
        with _lock:
            due = sorted(url for url in _pending if now - _sent_at.get(url, -RESEND_AFTER) >= RESEND_AFTER)
            _pending.difference_update(due)
            _sent_at.update(dict.fromkeys(due, now))
            wait = min((RESEND_AFTER - (now - _sent_at[url]) for url in _pending), default=None)
        if wait is not None:
            timer = threading.Timer(wait, run_in_background, [_flush])
            timer.daemon = True
            timer.start()
        if due:
            send(due)
    except Exception:
        logger.exception("Сбой отправки адресов в IndexNow")


def send(urls: list[str]) -> None:
    payload = {"host": settings.CANONICAL_HOST, "key": settings.INDEXNOW_KEY, "urlList": urls}
    request = Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
    except HTTPError as exc:
        exc.close()
        # 403/422 — Яндекс не нашёл файл ключа или ключ не подходит к адресам: проверьте INDEXNOW_KEY и /<ключ>.txt.
        logger.warning("IndexNow отклонил адреса (HTTP %s): %s", exc.code, ", ".join(urls))
        return
    except OSError as exc:
        logger.warning("IndexNow не ответил (%s): %s", exc, ", ".join(urls))
        return
    logger.info("IndexNow принял адреса (HTTP %s): %s", status, ", ".join(urls))
