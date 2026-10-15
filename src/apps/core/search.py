"""Поиск в админке без учёта регистра и разницы «ё»/«е».

В SQLite `LIKE` не различает регистр только у латиницы: «батут» не находил «Батут». Поэтому обе стороны сравнения
приводятся к одному виду функцией `fold` — в базе через SQL-функцию `tp_fold`, которую `register` добавляет
каждому новому подключению к SQLite (`CoreConfig.ready`)."""

from collections.abc import Sequence
from functools import reduce
from operator import or_

from django.db.models import CharField, F, Func, Q, QuerySet
from django.utils.text import smart_split, unescape_string_literal

SQL_FUNCTION = "tp_fold"


def fold(value):
    """Привести строку к однородному виду для сравнения: нижний регистр, ё→е."""
    if value is None:
        return None
    return str(value).casefold().replace("ё", "е")


def register(sender, connection, **kwargs):
    """Зарегистрировать SQL-функцию tp_fold на новом подключении к SQLite."""
    if connection.vendor == "sqlite":
        connection.connection.create_function(SQL_FUNCTION, 1, fold, deterministic=True)


class Fold(Func):
    """SQL-функция для приведения значения к однородному виду."""

    function = SQL_FUNCTION
    output_field = CharField()


def search(queryset: QuerySet, search_fields: Sequence[str], term: str) -> tuple[QuerySet, bool]:
    """Записи, где каждое слово `term` есть хотя бы в одном из `search_fields` (как в Django: фраза в кавычках —
    одно слово). Возвращает queryset и признак возможных дублей (поиск по связанным записям)."""
    names = {f"_fold_{i}": field.lstrip("^=@") for i, field in enumerate(search_fields)}
    queryset = queryset.annotate(**{alias: Fold(F(name)) for alias, name in names.items()})
    for bit in smart_split(term):
        if bit.startswith(('"', "'")) and bit[0] == bit[-1]:
            bit = unescape_string_literal(bit)
        word = fold(bit)
        queryset = queryset.filter(reduce(or_, (Q(**{f"{alias}__contains": word}) for alias in names)))
    return queryset, any("__" in name for name in names.values())
