"""Рисует сезонные варианты стандартного логотипа шапки: зимой — снежные шапки на буквах и ёлке, на Новый год —
ещё шарики и звезда, осенью — листья на буквах и в воздухе.
Запуск из корня: `uv run --project src python scripts/draw_season_logos.py`.

Источник — src/static/img/logo-header.png (357×132, 3× от 119×44); результат того же размера, чтобы шапка не сдвинулась:
src/static/img/logo-header-<kind>.png (имена — по Season.Kind). Рисуем с запасом 4× и уменьшаем — края сглажены.
"""

import math
import random
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw

IMG = Path(__file__).resolve().parent.parent / "src/static/img"
SS = 4  # суперсэмплинг
SNOW = (255, 255, 255, 255)
SNOW_EDGE = (
    150,
    190,
    222,
    255,
)  # голубая кайма: белый снег на белой шапке сайта иначе не виден
BALLS = [
    (229, 72, 77, 255),
    (245, 184, 46, 255),
    (74, 143, 214, 255),
    (255, 255, 255, 255),
]
STAR = (229, 72, 77, 255)
# Осенние листья: (заливка, прожилка)
LEAVES = [
    ((217, 122, 43, 255), (163, 86, 28, 255)),
    ((194, 80, 46, 255), (142, 58, 32, 255)),
    ((227, 167, 47, 255), (168, 122, 28, 255)),
]


def is_navy(p):
    r, g, b, a = p
    return a > 128 and b > 70 and r < 60 and g < 110


def is_green(p):
    r, g, b, a = p
    return a > 128 and g > 150 and r < 150 and b < 120


def is_open(p):
    """Над поверхностью «небо»: прозрачно, солнце или белая обводка ёлки — туда может лечь снег."""
    return not (is_navy(p) or is_green(p))


def top_surfaces(im):
    """Верхние грани тёмно-синих фигур, над которыми открыто небо: {x: y}, только почти горизонтальные участки."""
    px, (w, h) = im.load(), im.size
    tops = {}
    for x in range(w):
        for y in range(1, h):
            if is_navy(px[x, y]) and all(
                is_open(px[x, y - k]) for k in range(1, 9) if y - k >= 0
            ):
                # Внутренность «Р» (белый просвет, сверху снова буква) — не небо.
                if any(is_navy(px[x, yy]) for yy in range(max(0, y - 9))):
                    continue
                tops.setdefault(x, y)
    flat = {
        x: y
        for x, y in tops.items()
        if all(abs(tops.get(x + d, 999) - y) <= 1 for d in (-2, 2))
    }
    return flat


def segments(flat):
    """Склеивает соседние колонки одной высоты в отрезки [(x0, x1, y)]."""
    result, xs = [], sorted(flat)
    start = prev = xs[0]
    for x in xs[1:] + [None]:
        if x is not None and x == prev + 1 and abs(flat[x] - flat[prev]) <= 1:
            prev = x
            continue
        if prev - start >= 5:
            result.append((start, prev, min(flat[i] for i in range(start, prev + 1))))
        if x is not None:
            start = prev = x
    return result


def draw_snow(draw, segs, rnd):
    for x0, x1, y in segs:
        width = x1 - x0
        height = min(
            8, 3 + width / 8
        )  # на широкой планке «Т» сугроб выше, на узкой ножке «К» — тоньше
        drips = [rnd.uniform(x0 + 3, x1 - 3) for _ in range(max(1, width // 22))]
        top, bottom = [], []
        steps = width * 2
        for i in range(steps + 1):
            x = x0 - 1 + (width + 2) * i / steps
            t = (x - x0) / max(width, 1)
            bump = math.sin(math.pi * min(max(t, 0), 1)) ** 0.5
            ripple = 0.6 * math.sin(x / 4.3 + rnd.random())
            top.append((x, y - height * bump - ripple * bump))
            drip = sum(3.2 * math.exp(-(((x - d) / 2.2) ** 2)) for d in drips)
            bottom.append((x, y + (2.8 + drip) * min(bump * 2.5, 1)))
        poly = [(px * SS, py * SS) for px, py in top + bottom[::-1]]
        draw.polygon(poly, fill=SNOW, outline=SNOW_EDGE, width=int(1.1 * SS))


def green_tiers(im):
    """Ярусы ёлки: связные зелёные области, сверху вниз, [(xmin, ymin, xmax, ymax, точки)]."""
    px, (w, h) = im.load(), im.size
    seen, tiers = set(), []
    for y in range(h):
        for x in range(w):
            if (x, y) in seen or not is_green(px[x, y]):
                continue
            stack, pts = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                pts.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if (
                        0 <= nx < w
                        and 0 <= ny < h
                        and (nx, ny) not in seen
                        and is_green(px[nx, ny])
                    ):
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if len(pts) > 30:
                tiers.extend(_split_tiers(pts))
    return sorted(tiers, key=lambda t: t[1])


def _split_tiers(pts):
    """Зелень ярусов соединена узким перешейком над тёмной полосой веток — режем там, где ширина ряда резко
    падает по сравнению с рядом выше (верх следующего яруса)."""
    rows = {}
    for x, y in pts:
        rows.setdefault(y, []).append(x)
    ys = sorted(rows)
    cuts = [y for prev, y in pairwise(ys) if len(rows[y]) < 0.6 * len(rows[prev])]
    bounds = [ys[0], *cuts, ys[-1] + 1]
    result = []
    for top, bottom in pairwise(bounds):
        part = {(x, y) for x, y in pts if top <= y < bottom}
        if len(part) > 30:
            xs, part_ys = [p[0] for p in part], [p[1] for p in part]
            result.append((min(xs), min(part_ys), max(xs), max(part_ys), part))
    return result


def snow_on_tiers(im, tiers):
    """Снег на верхушках ярусов ёлки: белая шапка на зелёном с волнистым нижним краем (рисуем по пикселям
    исходника — края совпадают с ярусом)."""
    px = im.load()
    for xmin, ymin, xmax, ymax, pts in tiers:
        line = ymin + (ymax - ymin) * 0.36
        for x, y in pts:
            if y < line + 1.6 * math.sin(x / 2.3):
                px[x, y] = SNOW


def draw_balls(draw, tiers):
    colors = iter(BALLS * 4)
    for xmin, ymin, xmax, ymax, pts in tiers:
        cx = (xmin + xmax) / 2
        row_y = ymax - 5
        xs = (
            [cx]
            if xmax - xmin < 30
            else [cx - (xmax - xmin) * 0.27, cx, cx + (xmax - xmin) * 0.27]
        )
        for x in xs:
            r = 4.0
            if not all(
                (round(x + dx), round(row_y + dy)) in pts
                for dx in (-r, r)
                for dy in (-r, r)
            ):
                continue
            color = next(colors)
            box = [(x - r) * SS, (row_y - r) * SS, (x + r) * SS, (row_y + r) * SS]
            draw.ellipse(
                box, fill=color, outline=(16, 71, 92, 255), width=int(0.7 * SS)
            )
            hl = [
                (x - r * 0.55) * SS,
                (row_y - r * 0.55) * SS,
                (x - r * 0.05) * SS,
                (row_y - r * 0.05) * SS,
            ]
            draw.ellipse(hl, fill=(255, 255, 255, 170))


def draw_star(draw, im):
    """Пятиконечная звезда на макушке ёлки — над верхней точкой тёмно-синего контура в зоне ёлки."""
    px, (w, h) = im.load(), im.size
    tree_x = [x for x in range(w) for y in range(h) if is_green(px[x, y])]
    x_lo, x_hi = min(tree_x), max(tree_x)
    apex = min(
        ((x, y) for x in range(x_lo, x_hi + 1) for y in range(h) if is_navy(px[x, y])),
        key=lambda p: p[1],
    )
    cx, cy, outer, inner = apex[0], apex[1] + 2, 11.5, 4.8
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append(
            ((cx + radius * math.cos(angle)) * SS, (cy + radius * math.sin(angle)) * SS)
        )
    draw.polygon(points, fill=STAR, outline=(255, 255, 255, 255), width=int(1.3 * SS))


def draw_leaf(draw, x, y, angle, length, colors):
    """Лист-«лодочка» с прожилкой; (x, y) — черенок, angle — в градусах."""
    fill, vein = colors
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def point(u, v):
        return ((x + u * cos - v * sin) * SS, (y + u * sin + v * cos) * SS)

    width = length * 0.36
    outline = [
        point(length * t, -width * math.sin(math.pi * t))
        for t in (i / 16 for i in range(17))
    ]
    outline += [
        point(length * t, width * math.sin(math.pi * t))
        for t in (i / 16 for i in range(16, -1, -1))
    ]
    draw.polygon(outline, fill=fill)
    draw.line(
        [point(-length * 0.15, 0), point(length * 0.85, 0)],
        fill=vein,
        width=int(0.9 * SS),
    )


def draw_autumn(draw, segs):
    """Листья лежат на верхних гранях букв (на широких планках «Т» и «П» — по два) и летят над тире и в пустом верху."""
    colors = iter(LEAVES * 4)
    for x0, x1, y in segs:
        width = x1 - x0
        if width < 10:
            continue
        spots = [0.18, 0.62] if width >= 40 else [0.45]
        for i, t in enumerate(spots):
            length = 17 if width >= 24 else 12
            draw_leaf(
                draw, x0 + width * t, y - 3.2, -10 if i % 2 else 7, length, next(colors)
            )
    for x, y, angle, length in (
        (62, 50, 35, 15),
        (40, 10, -25, 14),
        (272, 12, 150, 15),
    ):
        draw_leaf(draw, x, y, angle, length, next(colors))


def render(base, kind):
    w, h = base.size
    tiers = green_tiers(base)
    segs = segments(top_surfaces(base))
    layer = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if kind == "autumn":
        draw_autumn(draw, segs)
    else:
        draw_snow(draw, segs, random.Random(7))
    if kind == "new_year":
        draw_balls(draw, tiers)
        draw_star(draw, base)
    layer = layer.resize((w, h), Image.LANCZOS)
    out = base.copy()
    if kind != "autumn":
        snow_on_tiers(out, tiers)
    out.alpha_composite(layer)
    return out.quantize(
        colors=64, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
    )


def main():
    base = Image.open(IMG / "logo-header.png").convert("RGBA")
    for kind in ("autumn", "winter", "new_year"):
        path = IMG / f"logo-header-{kind}.png"
        render(base, kind).save(path, optimize=True)
        print(path.relative_to(IMG.parent.parent.parent), path.stat().st_size, "байт")


if __name__ == "__main__":
    main()
