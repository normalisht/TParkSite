from django.db import connection
from django.http import HttpResponse


def healthz(request):
    connection.ensure_connection()
    return HttpResponse("ok", content_type="text/plain")
