import logging

logger = logging.getLogger(__name__)


def safe_spec_url(obj, spec_name: str) -> str:
    """URL миниатюры imagekit или пустая строка, если объекта или исходника нет либо он битый."""
    if obj is None:
        return ""
    try:
        spec = getattr(obj, spec_name)
        return spec.url if spec else ""
    except Exception:
        logger.warning("Не удалось получить %s для %r", spec_name, obj, exc_info=True)
        return ""
