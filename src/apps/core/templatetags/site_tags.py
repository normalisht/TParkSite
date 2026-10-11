import json
import re
from urllib.parse import quote

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from apps.core.images import lightbox_url as _lightbox_url
from apps.core.images import picture_html, safe_spec_url
from apps.core.seo import plaintext as _plaintext

register = template.Library()


@register.filter
def spec_url(obj, spec_name: str) -> str:
    return safe_spec_url(obj, spec_name)


@register.simple_tag
def picture(obj, srcset: str, **kwargs) -> str:
    """`{% picture photo "card_small 640w, card 800w" sizes="…" alt="" class="…" %}` — см. picture_html."""
    return picture_html(obj, srcset, **kwargs)


@register.filter
def lazy_after(counter, eager: int) -> str:
    """`loading` для N-го фото списка: первые `eager` — сразу (первый экран), остальные — лениво."""
    return "" if int(counter) <= int(eager) else "lazy"


@register.filter
def eager_first(is_first, below_fold) -> bool:
    """Первое фото слайдера грузится сразу и с высоким приоритетом — если сам слайдер на первом экране."""
    return bool(is_first) and not below_fold


@register.filter
def lightbox_url(photo) -> str:
    return _lightbox_url(photo)


@register.filter
def plaintext(value, limit: int = 160) -> str:
    return _plaintext(value, int(limit))


_JSON_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


@register.filter
def ld_json(value) -> str:
    """Структурированные данные schema.org: `<script type="application/ld+json">` с экранированием, как у json_script.

    Список узлов становится `@graph` — так узлы могут ссылаться друг на друга по `@id`.
    """
    if isinstance(value, list):
        value = {"@context": "https://schema.org", "@graph": value}
    data = json.dumps(value, ensure_ascii=False).translate(_JSON_ESCAPES)
    return mark_safe(f'<script type="application/ld+json">{data}</script>')


@register.filter
def ru_plural(number, forms: str) -> str:
    """`{{ n|ru_plural:"отзыв,отзыва,отзывов" }}` → «21 отзыв», «3 отзыва», «18 отзывов»."""
    one, few, many = forms.split(",")
    n = abs(int(number))
    if n % 10 == 1 and n % 100 != 11:
        word = one
    elif 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        word = few
    else:
        word = many
    return f"{number} {word}"


_BRAND = re.compile(r"(?:Т-Парк|Тренинг-парк)[а-яё]*", re.IGNORECASE)


@register.filter(needs_autoescape=True)
def nobr(value, autoescape=True) -> str:
    """«Т-Парк», «Тренинг-парк» в любом падеже — без переноса по дефису (иначе «Т-/Парке» на телефоне)."""
    text = conditional_escape(value) if autoescape else str(value)
    return mark_safe(_BRAND.sub(lambda m: f'<span class="whitespace-nowrap">{m.group(0)}</span>', text))


@register.filter
def whatsapp_url(phone, topic: str = "") -> str:
    """Ссылка на чат; со страницы услуги или мероприятия — с готовым первым сообщением."""
    if not topic:
        return phone.whatsapp_url
    return f"{phone.whatsapp_url}?text={quote(f'Здравствуйте! Интересует «{topic}»')}"
