"""Seed default AppSetting rows needed by the publish + sync flows.

Idempotent: only creates a key if it is missing (never overwrites edited values).
Run on first launch alongside ``seed_menu``.
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from pos.models import AppSetting
from pos.passwords import (
    DEFAULT_MANAGER_PASSWORD,
    DEFAULT_REVENUE_PASSWORD,
    SOURCE_GOD_PASSWORD_HASH,
)

DEFAULTS = {
    "cafe_slug": "cixis-cafe",
    "cafe_name": "خروج",
    "remote_server_url": "http://127.0.0.1:9000",
    "api_key": "dev-cixis-key",
    # revenue_password is stored hashed; default plaintext is "1234".
    "revenue_password": make_password(DEFAULT_REVENUE_PASSWORD),
    "manager_password": make_password(DEFAULT_MANAGER_PASSWORD),
    "god_password": SOURCE_GOD_PASSWORD_HASH,
    "manager_password_changed": "0",
    "password_generation_revenue": "0",
    "password_generation_manager": "0",
    "password_generation_god": "0",
    # Day-closing push to the remote Django server. Off by default: the remote is
    # optional and nothing reads what it receives.
    "sync_enabled": "false",
    # QR-menu bucket. Seeded blank on purpose -- no credential ships in the build.
    # The operator fills these in under تنظیمات انتشار, behind the god code.
    "s3_access_key": "",
    "s3_secret_key": "",
    "s3_bucket": "",
    "s3_endpoint_url": "",
    "s3_region": "",
}


class Command(BaseCommand):
    help = "Create default app settings (cafe slug, sync toggle, storage config, revenue password)."

    def handle(self, *args, **options):
        created = 0
        for key, value in DEFAULTS.items():
            _, made = AppSetting.objects.get_or_create(key=key, defaults={"value": value})
            created += int(made)
        self.stdout.write(
            self.style.SUCCESS(f"App settings ready (+{created} created).")
        )
