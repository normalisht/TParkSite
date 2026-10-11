from django.utils.functional import SimpleLazyObject

from apps.core.request_cache import cached_on_request
from apps.texts.models import SiteText


def site_texts(request):
    """Все тексты сайта одним запросом на страницу — и только если она выводит хотя бы один (`{% text %}`)."""
    return {
        "site_texts": SimpleLazyObject(
            lambda: cached_on_request(request, "site_texts", lambda: dict(SiteText.objects.values_list("key", "text")))
        )
    }
