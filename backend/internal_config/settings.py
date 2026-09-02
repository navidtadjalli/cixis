"""Locked-down settings for the internal product's private backend."""
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = False
SECRET_KEY = os.environ.get(
    "CIXIS_INTERNAL_DJANGO_SECRET", "cixis-internal-local-framework-key"
)
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "rest_framework",
    "internal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "internal_config.urls"
TEMPLATES = []
WSGI_APPLICATION = "internal_config.wsgi.application"
ASGI_APPLICATION = "internal_config.asgi.application"

INTERNAL_DATABASE_PATH = os.environ.get(
    "CIXIS_INTERNAL_DB_PATH", str(BASE_DIR / "internal.sqlite3")
)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": INTERNAL_DATABASE_PATH,
    }
}

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}
