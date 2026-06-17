"""Django settings for CiXiS local POS backend.

Single-machine, offline-first. Runs on 127.0.0.1:8000 inside the Electron shell.
No auth in v1 (single trusted cafe machine).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Local-only machine: a fixed insecure key is acceptable (never exposed publicly).
SECRET_KEY = "django-insecure-cixis-local-pos-key-change-not-needed-offline"

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "pos",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Overridable so isolated runs (e.g. the smoke test) use a throwaway DB.
        "NAME": os.environ.get("CIXIS_DB_PATH", str(BASE_DIR / "cixis.sqlite3")),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

# Electron front-end origin during dev (Vite) and packaged file:// origin.
CORS_ALLOW_ALL_ORIGINS = True

# Where day-closing SQLite backups are written.
# Overridable so packaged builds write to userData (survives app updates).
BACKUP_DIR = Path(os.environ.get("CIXIS_BACKUP_DIR", str(BASE_DIR / "backups")))
MAX_BACKUPS = 7

# Hour (0-23, local time) used only to LABEL a closing's business_date and new
# orders. Visibility never depends on it: the live register is every unsettled
# order, so nothing resets at midnight regardless of this value. Default 0 =
# plain calendar date. Set e.g. 6 if you want past-midnight orders grouped under
# the previous day in reports.
BUSINESS_DAY_START_HOUR = int(
    os.environ.get("CIXIS_BUSINESS_DAY_START_HOUR", "0")
)

APP_VERSION = "1.0.0"
