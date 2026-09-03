"""Fail-closed validation for the paired, read-only CiXiS installation."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import socket
import sqlite3
from uuid import UUID

from pos.internal_bridge import open_catalog_readonly


SQLITE_HEADER = b"SQLite format 3\x00"
LEGACY_TRACKER_TABLES = ("pos_shiftattendance", "pos_staffconsumption")


class CompatibilityError(RuntimeError):
    """Raised without source details when CiXiS cannot be safely consumed."""


def _port_is_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


@dataclass(frozen=True)
class CixisProfile:
    """Trusted Electron profile for one exact CiXiS installation and release."""

    database_path: Path
    installation_id: str
    fingerprint: str
    compatibility_version: str
    application_version: str
    expected_application_version: str
    port: int = 8000
    port_is_in_use: Callable[[int], bool] = field(
        default=_port_is_in_use, repr=False, compare=False
    )


def _require_sqlite_header(database_path: Path) -> None:
    try:
        with database_path.open("rb") as database_file:
            header = database_file.read(len(SQLITE_HEADER))
    except OSError as error:
        raise CompatibilityError("CiXiS profile is unavailable") from error
    if header != SQLITE_HEADER:
        raise CompatibilityError("CiXiS profile is incompatible")


def _readonly_connection(database_path: Path) -> sqlite3.Connection:
    try:
        return open_catalog_readonly(database_path)
    except (OSError, sqlite3.Error, ValueError) as error:
        raise CompatibilityError("CiXiS profile is incompatible") from error


def cixis_schema_fingerprint(database_path: Path) -> str:
    """Hash schema plus CiXiS migration history, never mutable application rows."""
    database_path = Path(database_path)
    _require_sqlite_header(database_path)
    connection = _readonly_connection(database_path)
    try:
        schema = connection.execute(
            """
            SELECT type, name, tbl_name, COALESCE(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name, tbl_name
            """
        ).fetchall()
        migrations = connection.execute(
            """
            SELECT app, name FROM django_migrations
            WHERE app = 'pos'
            ORDER BY app, name
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise CompatibilityError("CiXiS profile is incompatible") from error
    finally:
        connection.close()
    material = repr((schema, migrations)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _setting(connection: sqlite3.Connection, key: str) -> str:
    try:
        row = connection.execute(
            "SELECT value FROM pos_appsetting WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.Error as error:
        raise CompatibilityError("CiXiS profile is incompatible") from error
    if row is None or not isinstance(row[0], str):
        raise CompatibilityError("CiXiS profile is incompatible")
    return row[0]


def _require_empty_legacy_tracker_tables(connection: sqlite3.Connection) -> None:
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in LEGACY_TRACKER_TABLES:
            if table not in tables or connection.execute(
                f'SELECT 1 FROM "{table}" LIMIT 1'
            ).fetchone() is not None:
                raise CompatibilityError("CiXiS profile is incompatible")
    except sqlite3.Error as error:
        raise CompatibilityError("CiXiS profile is incompatible") from error


def verify_cixis_profile(profile: CixisProfile) -> None:
    """Reject every profile except the exact paired, migrated, stopped CiXiS."""
    database_path = Path(profile.database_path)
    _require_sqlite_header(database_path)
    if (
        not profile.application_version
        or not profile.compatibility_version
        or profile.application_version != profile.expected_application_version
        or profile.port != 8000
        or profile.port_is_in_use(profile.port)
    ):
        raise CompatibilityError("CiXiS profile is incompatible")
    try:
        expected_installation_id = str(UUID(profile.installation_id))
    except (AttributeError, ValueError) as error:
        raise CompatibilityError("CiXiS profile is incompatible") from error
    if cixis_schema_fingerprint(database_path) != profile.fingerprint:
        raise CompatibilityError("CiXiS profile is incompatible")
    connection = _readonly_connection(database_path)
    try:
        if _setting(connection, "cixis_installation_id") != expected_installation_id:
            raise CompatibilityError("CiXiS profile is incompatible")
        if (
            _setting(connection, "internal_compatibility_version")
            != profile.compatibility_version
        ):
            raise CompatibilityError("CiXiS profile is incompatible")
        _require_empty_legacy_tracker_tables(connection)
    finally:
        connection.close()
