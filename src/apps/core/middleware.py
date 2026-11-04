from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.utils.cache import set_response_etag
from django.utils.http import http_date


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


class RedirectFallbackMiddleware:
    """404 по адресу из «Редиректов» (страницу переименовали) — 301 на новый адрес с теми же параметрами (utm и т. п.)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        from apps.core.models import Redirect, is_site_path

        target = Redirect.objects.filter(old_path=request.path).values_list("new_path", flat=True).first()
        if not target or not is_site_path(target):  # строка могла попасть в обход валидации — на чужой сайт не уводим
            return response
        query = request.META.get("QUERY_STRING", "")
        separator = "&" if "?" in target else "?"
        return HttpResponsePermanentRedirect(f"{target}{separator}{query}" if query else target)


class LastModifiedMiddleware:
    """Last-Modified у публичных страниц: робот Яндекса переобходит с If-Modified-Since, а ETag/If-None-Match
    (`ConditionalGetMiddleware`) использует Google. Сам 304 отдаёт `ConditionalGetMiddleware` — этот стоит под ним.

    Без заголовка: страницы с параметрами в адресе (из utm и т. п. в базе копились бы строки), админка и черновики
    (`private`/`no-cache`, `Vary: Cookie` — HTML зависит от посетителя), ответы, где Last-Modified уже есть (sitemap).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.core.models import PageVersion

        response = self.get_response(request)
        if self._applies(request, response) and len(request.path) <= PageVersion.MAX_PATH_LENGTH:
            if not response.has_header("ETag"):
                set_response_etag(response)
            if response.has_header("ETag"):  # у пустого ответа ETag нет
                modified_at = PageVersion.modified_at_for(request.path, response["ETag"])
                response["Last-Modified"] = http_date(modified_at.timestamp())
        return response

    @staticmethod
    def _applies(request, response) -> bool:
        if request.method != "GET" or response.status_code != 200 or response.streaming:
            return False
        if request.META.get("QUERY_STRING") or response.has_header("Last-Modified"):
            return False
        cache_control = response.get("Cache-Control", "").lower()
        if any(word in cache_control for word in ("private", "no-cache", "no-store")):
            return False
        return "cookie" not in response.get("Vary", "").lower()


class PermissionsPolicyMiddleware:
    """Запрещает странице и встроенным фреймам камеру, микрофон, платежи и USB — сайту они не нужны.

    Геолокацию не трогаем: «Моё местоположение» в карте Яндекса.
    """

    POLICY = "camera=(), microphone=(), payment=(), usb=()"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", self.POLICY)
        return response
