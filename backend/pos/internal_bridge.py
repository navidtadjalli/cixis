"""Narrow, audited bridge between CiXiS and the internal product.

The internal product may only use this module for explicitly allowed CiXiS
operations.  Catalog/profile reads always use a SQLite read-only URI; no
internal model is ever installed in the CiXiS database.
"""
import sqlite3
from pathlib import Path

from django.db import transaction


PASSWORD_SETTING_KEYS = {
    "supervisor": ("revenue_password", "password_generation_revenue"),
    "manager": ("manager_password", "password_generation_manager"),
    "god": ("god_password", "password_generation_god"),
}


class _PasswordGenerationConflict(Exception):
    pass


def open_catalog_readonly(database_path: Path) -> sqlite3.Connection:
    """Open the CiXiS database for catalog reads without any write capability."""
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=3000")
    return connection


def compare_and_swap_password_setting(
    role: str,
    *,
    expected_hash: str,
    expected_generation: int,
    replacement_hash: str,
) -> int | None:
    """Atomically replace one shared role hash only at its expected generation.

    ``None`` means the caller observed stale CiXiS state.  Unknown roles are
    rejected before touching the database, keeping this module's write surface
    limited to the three specification-approved password rows and generations.
    """
    from .models import AppSetting

    try:
        password_key, generation_key = PASSWORD_SETTING_KEYS[role]
    except KeyError as error:
        raise ValueError(f"unsupported shared password role: {role}") from error

    next_generation = expected_generation + 1
    try:
        with transaction.atomic():
            password_updated = AppSetting.objects.filter(
                key=password_key, value=expected_hash
            ).update(value=replacement_hash)
            if password_updated != 1:
                raise _PasswordGenerationConflict

            generation_updated = AppSetting.objects.filter(
                key=generation_key, value=str(expected_generation)
            ).update(value=str(next_generation))
            if generation_updated != 1:
                raise _PasswordGenerationConflict
    except _PasswordGenerationConflict:
        return None

    return next_generation
