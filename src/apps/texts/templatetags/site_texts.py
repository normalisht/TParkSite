from django import template

from apps.core.templatetags.site_tags import nobr
from apps.texts.registry import BY_KEY

register = template.Library()

USAGE = 'Использование: {% text "ключ" %} или {% text "ключ" as переменная %}'


class TextNode(template.Node):
    def __init__(self, key: str, var_name: str | None):
        self.key, self.var_name = key, var_name

    def render(self, context) -> str:
        item = BY_KEY[self.key]
        texts = context.get("site_texts")  # нет при рендере без контекст-процессоров — тогда текст по умолчанию
        value = texts.get(self.key, item.default) if texts is not None else item.default
        if not value and item.required:
            value = item.default
        if self.var_name:
            context[self.var_name] = value
            return ""
        return nobr(value)


@register.tag("text")
def do_text(parser, token):
    """Текст сайта из «Текстов сайта» (apps/texts/registry.py): ключ проверяется при компиляции шаблона."""
    bits = token.split_contents()
    if len(bits) == 2:
        var_name = None
    elif len(bits) == 4 and bits[2] == "as":
        var_name = bits[3]
    else:
        raise template.TemplateSyntaxError(USAGE)
    raw = bits[1]
    if len(raw) < 2 or raw[0] != raw[-1] or raw[0] not in "\"'":
        raise template.TemplateSyntaxError(f"Ключ текста — строка в кавычках. {USAGE}")
    key = raw[1:-1]
    if key not in BY_KEY:
        raise template.TemplateSyntaxError(f"Неизвестный текст сайта «{key}»: добавьте его в apps/texts/registry.py")
    return TextNode(key, var_name)
