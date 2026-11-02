"""Черновик title и description нейросетью — для кнопки «Сгенерировать» на вкладке SEO в админке.

Запрос идёт через OpenRouter. Модель по умолчанию `openrouter/free` сама выбирает из бесплатных: отдельные бесплатные
модели исчезают почти без предупреждения. Текст исключения показывается в админке: поля можно заполнить вручную.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.core.models import SeoModel
from apps.core.seo import SITE_DESCRIPTION, plaintext

logger = logging.getLogger(__name__)

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Синхронный воркер gunicorn занят на всё время запроса, а бесплатные модели отвечают не сразу.
TIMEOUT = 40
MAX_RESPONSE_BYTES = 1024 * 1024
FACT_LIMIT = 3000  # длинной инфо-странице для title и description хватит начала текста

TITLE_LIMIT = SeoModel._meta.get_field("seo_title").max_length
DESCRIPTION_LIMIT = 160  # больше на сайт не попадёт: make_seo обрежет

_REASONING = re.compile(r"<think>.*?</think>", re.DOTALL)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = f"""Ты пишешь SEO-тексты для страниц сайта. {SITE_DESCRIPTION}

Ответь только JSON-объектом с двумя строками, без пояснений: {{"title": "...", "description": "..."}}
- title — заголовок страницы для поисковика, до 60 символов: суть страницы и бренд «Т-Парк».
- description — описание под ссылкой в выдаче, 120–160 символов: одно-два живых предложения на русском, что получит гость.
- Используй только факты из данных страницы и этого сообщения. Не придумывай цены, даты, места, программу и условия.
- Цена, указанная числом, — в рублях, пиши её с «₽».
- Без HTML, эмодзи и слов вроде «лучший» и «уникальный»."""


BAD_ANSWER = "Нейросеть ответила не в том формате — попробуйте ещё раз."


class SeoGenerationError(Exception):
    """Текст исключения показывается в админке."""


@dataclass(frozen=True)
class SeoDraft:
    title: str
    description: str


def _service_error(code) -> SeoGenerationError:
    if code == 401:
        return SeoGenerationError("OpenRouter не принял ключ — проверьте OPENROUTER_API_KEY на сервере.")
    if code == 402:
        return SeoGenerationError("На счёте OpenRouter не хватает средств — заполните поля вручную.")
    if code == 429:
        return SeoGenerationError("Лимит бесплатных запросов исчерпан — попробуйте позже или заполните поля вручную.")
    return SeoGenerationError("Нейросеть сейчас недоступна — попробуйте позже или заполните поля вручную.")


def parse_draft(content) -> SeoDraft:
    if not isinstance(content, str):
        raise SeoGenerationError(BAD_ANSWER)
    # Модели оборачивают JSON в текст и ```, а ход рассуждений может содержать свои фигурные скобки.
    found = _JSON_OBJECT.search(_REASONING.sub("", content))
    try:
        data = json.loads(found.group())
        title, description = data["title"], data["description"]
    except (AttributeError, ValueError, KeyError, TypeError) as exc:
        raise SeoGenerationError(BAD_ANSWER) from exc
    if not (isinstance(title, str) and isinstance(description, str)):
        raise SeoGenerationError(BAD_ANSWER)
    draft = SeoDraft(plaintext(title, TITLE_LIMIT), plaintext(description, DESCRIPTION_LIMIT))
    if not (draft.title and draft.description):
        raise SeoGenerationError(BAD_ANSWER)
    return draft


def parse_response(body: bytes) -> SeoDraft:
    try:
        data = json.loads(body)
        # Ошибка, возникшая после начала генерации, приходит со статусом 200 — в теле ответа или в choices[0].
        error = data.get("error") or (data.get("choices") or [{}])[0].get("error")
        if error:
            raise _service_error(error.get("code"))
        return parse_draft(data["choices"][0]["message"]["content"])
    except (AttributeError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise SeoGenerationError(BAD_ANSWER) from exc


def generate_seo(page_kind: str, facts: dict[str, str]) -> SeoDraft:
    """`facts` — подпись поля → значение: только эти данные о странице видит модель."""
    if not settings.OPENROUTER_API_KEY:
        raise SeoGenerationError("Не задан OPENROUTER_API_KEY — заполните поля вручную.")
    page = "\n".join([f"Тип страницы: {page_kind}", *(f"{label}: {value}" for label, value in facts.items())])
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": page}],
    }
    request = Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(MAX_RESPONSE_BYTES)
    except HTTPError as exc:
        exc.close()
        raise _service_error(exc.code) from exc
    except OSError as exc:
        raise SeoGenerationError("OpenRouter не ответил — попробуйте позже или заполните поля вручную.") from exc
    return parse_response(body)


_executor: ThreadPoolExecutor | None = None


def run_in_background(fn) -> None:
    """Свой поток, а не общий с миниатюрами: ожидание ответа сервиса не должно задерживать пережатие фото."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="seo")
    _executor.submit(fn)


def save_empty_seo(model, pk, draft: SeoDraft) -> list[str]:
    """Записывает черновик только в пустые поля и возвращает их имена. Условие и запись — в одном UPDATE: текст,
    введённый за время ответа сервиса, не затирается. `updated_at` — lastmod в sitemap: update() его сам не меняет."""
    records = model._default_manager.filter(pk=pk)
    now = timezone.now()
    saved = []
    for name, text in (("seo_title", draft.title), ("seo_description", draft.description)):
        if records.filter(**{name: ""}).update(**{name: text, "updated_at": now}):
            saved.append(name)
    return saved


def fill_empty_seo(model, pk, facts: dict[str, str]) -> None:
    """Заполняет пустые SEO-поля записи в фоне. При сбое поля остаются пустыми: на сайте — текст из названия и описания,
    следующее сохранение попробует снова."""
    try:
        save_empty_seo(model, pk, generate_seo(str(model._meta.verbose_name), facts))
    except SeoGenerationError as exc:
        logger.warning("SEO-поля %s #%s не заполнены: %s", model.__name__, pk, exc)
    except Exception:
        logger.exception("Сбой при заполнении SEO-полей %s #%s", model.__name__, pk)
    finally:
        connection.close()  # у потока своё соединение; он живёт долго, а запросы к базе у него редкие
