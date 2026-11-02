"""Раскладка карточек категорий на главной: размер зависит от их числа, в рядах нет пустых мест."""

from typing import Any, NamedTuple

# Сетка ПК — 6 колонок. Форма: колонки, соотношение сторон поверх обычного 4:3, sizes (контейнер 1120 px, зазор 24 px).
THIRD = ("lg:col-span-2", "", "(min-width: 1152px) 357px, (min-width: 1024px) calc((100vw - 80px) / 3)")
HALF = ("lg:col-span-3", "lg:aspect-[16/9]", "(min-width: 1152px) 548px, (min-width: 1024px) calc(50vw - 28px)")
# Две карточки стоят половинками и на планшете — там тоже пониже.
PAIR = ("lg:col-span-3", "sm:aspect-[16/9]", HALF[2])
# Фото 3:2 в полосе шириной в контейнер: при 4:3 или 16:9 одна карточка заняла бы целый экран.
FULL = ("lg:col-span-6", "sm:aspect-[5/2] lg:aspect-[3/1]", "(min-width: 1152px) 1120px")

# Сколько первых карточек идут по две в ряд, чтобы остальные легли ровно по три: 4 → 2+2, 5 → 2+3, 7 → 2+2+3.
HALVES_BY_REMAINDER = {0: 0, 1: 4, 2: 2}

PHONE_FULL_SIZES = "calc(100vw - 32px)"
PHONE_HALF_SIZES = "(min-width: 640px) calc(50vw - 28px), calc(50vw - 22px)"


class CategoryTile(NamedTuple):
    category: Any
    span: str
    aspect: str
    sizes: str


def _desktop_shape(index: int, count: int) -> tuple[str, str, str]:
    if count == 1:
        return FULL
    if count == 2:
        return PAIR
    return HALF if index < HALVES_BY_REMAINDER[count % 3] else THIRD


def category_tiles(categories: list) -> list[CategoryTile]:
    """Ниже lg сетка в 2 колонки: при нечётном числе первая карточка — во всю ширину."""
    count = len(categories)
    tiles = []
    for index, category in enumerate(categories):
        span, aspect, desktop_sizes = _desktop_shape(index, count)
        phone_full = index == 0 and count % 2 == 1
        phone_sizes = PHONE_FULL_SIZES if phone_full else PHONE_HALF_SIZES
        tiles.append(
            CategoryTile(
                category=category,
                span=f"col-span-2 {span}" if phone_full else span,
                aspect=aspect,
                sizes=f"{desktop_sizes}, {phone_sizes}",
            )
        )
    return tiles
