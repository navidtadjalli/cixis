"""Fail-closed CiXiS profile and catalog boundary contracts."""
from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from internal.tests.cixis_fixtures import (
    APP_VERSION,
    COMPATIBILITY_VERSION,
    INSTALLATION_ID,
    create_cixis_database,
    make_profile,
)


class CixisCompatibilityTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = Path(self.temporary_directory.name) / "cixis.sqlite3"
        create_cixis_database(self.database_path)
        self.profile = make_profile(self.database_path)

    def test_validates_the_exact_paired_profile(self):
        """Breaks if a valid migrated CiXiS profile is rejected before startup."""
        from internal.compatibility import verify_cixis_profile

        self.assertIsNone(verify_cixis_profile(self.profile))

    def test_rejects_missing_wrong_old_new_or_running_profiles_before_reading(self):
        """Breaks if incompatible CiXiS installations can start the internal app."""
        from internal.compatibility import CompatibilityError, verify_cixis_profile

        profiles = {
            "missing": replace(
                self.profile,
                database_path=self.database_path.with_name("moved-cixis.sqlite3"),
            ),
            "wrong-installation": replace(
                self.profile, installation_id="179b3bb7-1ca6-4403-a3a8-7172a3177d0e"
            ),
            "wrong-fingerprint": replace(self.profile, fingerprint="0" * 64),
            "old-app": replace(
                self.profile, expected_application_version="0.9.9"
            ),
            "new-app": replace(
                self.profile, application_version="1.0.1"
            ),
            "wrong-port": replace(self.profile, port=8001),
            "running-cixis": replace(self.profile, port_is_in_use=lambda _: True),
        }

        for scenario, profile in profiles.items():
            with self.subTest(scenario=scenario):
                with self.assertRaises(CompatibilityError):
                    verify_cixis_profile(profile)

    def test_rejects_non_sqlite_or_nonempty_legacy_tracker_tables(self):
        """Breaks if an arbitrary file or stale plaintext tracker rows are accepted."""
        from internal.compatibility import CompatibilityError, verify_cixis_profile

        invalid_path = self.database_path.with_name("not-a-database")
        invalid_path.write_bytes(b"not SQLite")
        invalid_profile = replace(self.profile, database_path=invalid_path)
        with self.assertRaises(CompatibilityError):
            verify_cixis_profile(invalid_profile)

        with sqlite3.connect(self.database_path) as connection:
            connection.execute("INSERT INTO pos_shiftattendance (id) VALUES (1)")
        with self.assertRaises(CompatibilityError):
            verify_cixis_profile(self.profile)

    def test_catalog_reader_returns_only_active_menu_rows_and_rejects_writes(self):
        """Breaks if catalog access changes CiXiS or shows deleted source menu rows."""
        from internal.catalog import CatalogReader

        catalog = CatalogReader(self.profile)
        self.addCleanup(catalog.close)

        self.assertEqual(
            [
                (product.source_product_id, product.category_name, product.name)
                for product in catalog.active_products()
            ],
            [(1, "قهوه", "اسپرسو"), (2, "قهوه", "ناموجود")],
        )
        with self.assertRaises(sqlite3.OperationalError):
            catalog.connection.execute("DELETE FROM pos_product")
