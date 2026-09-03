"""SQLite fixtures for testing the internal product's read-only CiXiS bridge."""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path


INSTALLATION_ID = "c3e29c3e-e3e6-4a47-bb42-a07269bec0d4"
COMPATIBILITY_VERSION = "pos:0017_internal_compatibility"
APP_VERSION = "1.0.0"


def create_cixis_database(database_path: Path) -> None:
    """Create a minimal, migrated CiXiS SQLite database with source rows."""
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE django_migrations (
                id INTEGER PRIMARY KEY,
                app TEXT NOT NULL,
                name TEXT NOT NULL,
                applied TEXT NOT NULL
            );
            CREATE TABLE pos_appsetting (
                id INTEGER PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL
            );
            CREATE TABLE pos_category (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                is_active INTEGER NOT NULL,
                staff_free_monthly_quota INTEGER NOT NULL
            );
            CREATE TABLE pos_product (
                id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                is_active INTEGER NOT NULL,
                is_available INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                staff_free_monthly_quota INTEGER NOT NULL
            );
            CREATE TABLE pos_employee (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                is_active INTEGER NOT NULL
            );
            CREATE TABLE pos_shiftattendance (id INTEGER PRIMARY KEY);
            CREATE TABLE pos_staffconsumption (id INTEGER PRIMARY KEY);
            """
        )
        connection.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)",
            ("pos", "0017_internal_compatibility", "2026-09-02T00:00:00Z"),
        )
        connection.executemany(
            "INSERT INTO pos_appsetting (key, value) VALUES (?, ?)",
            (
                ("cixis_installation_id", INSTALLATION_ID),
                ("internal_compatibility_version", COMPATIBILITY_VERSION),
            ),
        )
        connection.executemany(
            """
            INSERT INTO pos_category
                (id, name, sort_order, is_active, staff_free_monthly_quota)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (1, "قهوه", 1, 1, 10),
                (2, "بایگانی", 2, 0, 0),
            ),
        )
        connection.executemany(
            """
            INSERT INTO pos_product
                (id, category_id, name, price, is_active, is_available, sort_order,
                 staff_free_monthly_quota)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (1, 1, "اسپرسو", 50, 1, 1, 1, 0),
                (2, 1, "ناموجود", 60, 1, 0, 2, 0),
                (3, 2, "پنهان", 70, 1, 1, 1, 0),
            ),
        )
        connection.executemany(
            "INSERT INTO pos_employee (id, name, sort_order, is_active) VALUES (?, ?, ?, ?)",
            (
                (1, "آرش", 1, 1),
                (2, "بردیا", 2, 0),
            ),
        )


def make_profile(database_path: Path, **changes):
    """Build a valid profile, allowing one expected value to be overridden."""
    from internal.compatibility import CixisProfile, cixis_schema_fingerprint

    profile = CixisProfile(
        database_path=database_path,
        installation_id=INSTALLATION_ID,
        fingerprint=cixis_schema_fingerprint(database_path),
        compatibility_version=COMPATIBILITY_VERSION,
        application_version=APP_VERSION,
        expected_application_version=APP_VERSION,
        port_is_in_use=lambda _: False,
    )
    return replace(profile, **changes)


def sqlite_snapshot(database_path: Path) -> dict[str, object]:
    """Capture every CiXiS schema object and row for write-isolation assertions."""
    with sqlite3.connect(database_path) as connection:
        schema = list(
            connection.execute(
                """
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%'
                ORDER BY type, name
                """
            )
        )
        tables = [
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        rows = {
            table: list(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in tables
        }
    return {"schema": schema, "rows": rows}
