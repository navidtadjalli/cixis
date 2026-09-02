"""Seed the narrow CiXiS settings contract used by چیخیش اندرونی.

This migration preserves any already-configured supervisor/manager hashes.  The
God hash is copied verbatim from the historical CiXiS source constant so an
existing installation keeps its current God credential until it is changed via
the internal product.
"""
import uuid

from django.contrib.auth.hashers import make_password
from django.db import migrations


SOURCE_GOD_PASSWORD_HASH = (
    "pbkdf2_sha256$870000$gOdPBjJb3OXLTp2xpAoAeB$"
    "jQ5VH8bk15uw1QeYbYFBb44HDu+ZOGRVKk8OMDUR8lQ="
)


def seed_internal_compatibility_settings(apps, schema_editor):
    AppSetting = apps.get_model("pos", "AppSetting")
    defaults = {
        "revenue_password": make_password("1234"),
        "manager_password": make_password("0000"),
        "god_password": SOURCE_GOD_PASSWORD_HASH,
        "manager_password_changed": "0",
        "password_generation_revenue": "0",
        "password_generation_manager": "0",
        "password_generation_god": "0",
        "cixis_installation_id": str(uuid.uuid4()),
        "internal_compatibility_version": "pos:0017_internal_compatibility",
    }
    for key, value in defaults.items():
        AppSetting.objects.get_or_create(key=key, defaults={"value": value})


class Migration(migrations.Migration):
    dependencies = [("pos", "0016_staff_consumption_shift")]

    operations = [
        migrations.RunPython(
            seed_internal_compatibility_settings,
            migrations.RunPython.noop,
        )
    ]
