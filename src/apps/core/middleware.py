from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    """301 с www.<CANONICAL_HOST> на CANONICAL_HOST: у сайта один адрес, без дублей в поиске.

    Другие хосты (localhost для healthcheck и т. п.) не трогает.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = settings.CANONICAL_HOST
        if host and request.get_host().lower() == f"www.{host}":
            return HttpResponsePermanentRedirect(f"https://{host}{request.get_full_path()}")
        return self.get_response(request)
