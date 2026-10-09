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
