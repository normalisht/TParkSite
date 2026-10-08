import html
import re

from django.utils.html import strip_tags


def plaintext(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", html.unescape(strip_tags(value or ""))).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return f"{cut}…"


def make_seo(title: str = "", description_html: str = "", image_url: str = "") -> dict:
    return {"title": title, "description": plaintext(description_html), "image": image_url}


def absolute_url(request, url: str) -> str:
    return request.build_absolute_uri(url) if url else ""
