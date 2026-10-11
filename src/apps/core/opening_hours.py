"""Часы работы из формата schema.org (`Mo-Fr 09:00-18:00; Sa,Su 10:00-16:00`) — по-русски для посетителей."""

import re

DAYS = {"Mo": "пн", "Tu": "вт", "We": "ср", "Th": "чт", "Fr": "пт", "Sa": "сб", "Su": "вс"}
_DAY = "|".join(DAYS)
_RULE = re.compile(
    rf"^(?P<days>(?:{_DAY})(?:-(?:{_DAY}))?(?:,(?:{_DAY})(?:-(?:{_DAY}))?)*)\s+"
    r"(?P<start>\d{1,2}:\d{2})-(?P<end>\d{1,2}:\d{2})$"
)


def _days(spec: str) -> str:
    if spec == "Mo-Su":
        return "Ежедневно"
    parts = []
    for part in spec.split(","):
        first, _, last = part.partition("-")
        parts.append(f"{DAYS[first]}–{DAYS[last]}" if last else DAYS[first])
    text = ", ".join(parts)
    return text[0].upper() + text[1:]


def human_opening_hours(value: str) -> list[str]:
    """Строки вида «Ежедневно, 10:00–18:00». Если хоть одно правило не разобрать — пустой список (не показываем)."""
    lines = []
    for rule in filter(None, (r.strip() for r in (value or "").split(";"))):
        match = _RULE.match(rule)
        if not match:
            return []
        lines.append(f"{_days(match['days'])}, {match['start']}–{match['end']}")
    return lines


SCHEMA_DAYS = {
    "Mo": "Monday",
    "Tu": "Tuesday",
    "We": "Wednesday",
    "Th": "Thursday",
    "Fr": "Friday",
    "Sa": "Saturday",
    "Su": "Sunday",
}
_ORDER = list(DAYS)


def _expand(spec: str) -> list[str]:
    """«Mo-Fr,Su» → [Mo, Tu, We, Th, Fr, Su]; диапазон через воскресенье («Fr-Mo») тоже разворачивается."""
    days = []
    for part in spec.split(","):
        first, _, last = part.partition("-")
        start, end = _ORDER.index(first), _ORDER.index(last or first)
        days += _ORDER[start : end + 1] if start <= end else _ORDER[start:] + _ORDER[: end + 1]
    return days


def _hhmm(value: str) -> str:
    """«9:00» → «09:00»: schema.org ждёт время ровно в формате ЧЧ:ММ."""
    return value.zfill(5)


def opening_hours_spec(value: str) -> list[dict]:
    """`OpeningHoursSpecification` для JSON-LD; если хоть одно правило не разобрать — пустой список."""
    specs = []
    for rule in filter(None, (r.strip() for r in (value or "").split(";"))):
        match = _RULE.match(rule)
        if not match:
            return []
        specs.append(
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": [f"https://schema.org/{SCHEMA_DAYS[d]}" for d in _expand(match["days"])],
                "opens": _hhmm(match["start"]),
                "closes": _hhmm(match["end"]),
            }
        )
    return specs
