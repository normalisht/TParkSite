import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DEBUG", "0")

from config.settings import *

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
CANONICAL_HOST = ""
