import sqlite3
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth.hashers import check_password, make_password
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from pos.models import AppSetting
from pos.views.misc import GOD_CODE_HASH


class InternalCatalogConnectionTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "cixis.sqlite3"
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("CREATE TABLE catalog (id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO catalog (name) VALUES ('قهوه')")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_catalog_connection_reads_but_rejects_writes(self):
        from pos.internal_bridge import open_catalog_readonly

        connection = open_catalog_readonly(self.database_path)
        self.addCleanup(connection.close)

        self.assertEqual(
            connection.execute("SELECT name FROM catalog").fetchone(), ("قهوه",)
        )
        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("INSERT INTO catalog (name) VALUES ('چای')")


class InternalCompatibilityMigrationTests(TransactionTestCase):
    migrate_from = ("pos", "0016_staff_consumption_shift")
    migrate_to = ("pos", "0017_internal_compatibility")

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        old_apps = self.executor.loader.project_state([self.migrate_from]).apps
        old_settings = old_apps.get_model("pos", "AppSetting")
        old_settings.objects.filter(
            key__in=(
                "revenue_password",
                "manager_password",
                "god_password",
                "manager_password_changed",
                "password_generation_revenue",
                "password_generation_manager",
                "password_generation_god",
                "cixis_installation_id",
                "internal_compatibility_version",
            )
        ).delete()
        self.revenue_hash = make_password("Existing-supervisor-password-123")
        self.manager_hash = make_password("Existing-manager-password-123")
        old_settings.objects.create(key="revenue_password", value=self.revenue_hash)
        old_settings.objects.create(key="manager_password", value=self.manager_hash)
        self.schema_before = list(
            connection.cursor().execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            )
        )
        self.non_setting_rows_before = self._non_setting_rows()

    def _non_setting_rows(self):
        cursor = connection.cursor()
        tables = [
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' "
                "AND name NOT IN ('django_migrations', 'pos_appsetting')"
            )
        ]
        return {
            table: list(cursor.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in tables
        }

    def test_migration_preserves_role_hashes_and_seeds_internal_profile(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_to])
        apps = self.executor.loader.project_state([self.migrate_to]).apps
        settings = dict(
            apps.get_model("pos", "AppSetting").objects.values_list("key", "value")
        )

        self.assertEqual(settings["revenue_password"], self.revenue_hash)
        self.assertEqual(settings["manager_password"], self.manager_hash)
        self.assertEqual(settings["god_password"], GOD_CODE_HASH)
        self.assertEqual(settings["manager_password_changed"], "0")
        self.assertEqual(settings["password_generation_revenue"], "0")
        self.assertEqual(settings["password_generation_manager"], "0")
        self.assertEqual(settings["password_generation_god"], "0")
        self.assertEqual(
            settings["internal_compatibility_version"],
            "pos:0017_internal_compatibility",
        )
        self.assertIsInstance(uuid.UUID(settings["cixis_installation_id"]), uuid.UUID)
        self.assertEqual(
            list(
                connection.cursor().execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                )
            ),
            self.schema_before,
        )
        self.assertEqual(self._non_setting_rows(), self.non_setting_rows_before)


class SharedPasswordGenerationTests(TestCase):
    def setUp(self):
        AppSetting.objects.update_or_create(
            key="manager_password", defaults={"value": "old-manager-hash"}
        )
        AppSetting.objects.update_or_create(
            key="password_generation_manager", defaults={"value": "7"}
        )

    def test_compare_and_swap_rotates_matching_role_hash_and_generation(self):
        from pos.internal_bridge import compare_and_swap_password_setting

        next_generation = compare_and_swap_password_setting(
            "manager",
            expected_hash="old-manager-hash",
            expected_generation=7,
            replacement_hash="new-manager-hash",
        )

        self.assertEqual(next_generation, 8)
        self.assertEqual(
            AppSetting.objects.get(key="manager_password").value,
            "new-manager-hash",
        )
        self.assertEqual(
            AppSetting.objects.get(key="password_generation_manager").value,
            "8",
        )

    def test_compare_and_swap_rejects_stale_hash_or_generation_without_change(self):
        from pos.internal_bridge import compare_and_swap_password_setting

        self.assertIsNone(
            compare_and_swap_password_setting(
                "manager",
                expected_hash="old-manager-hash",
                expected_generation=6,
                replacement_hash="new-manager-hash",
            )
        )
        self.assertEqual(
            AppSetting.objects.get(key="manager_password").value,
            "old-manager-hash",
        )
        self.assertEqual(
            AppSetting.objects.get(key="password_generation_manager").value,
            "7",
        )


class InitSettingsPasswordContractTests(TestCase):
    password_keys = (
        "revenue_password",
        "manager_password",
        "god_password",
        "manager_password_changed",
        "password_generation_revenue",
        "password_generation_manager",
        "password_generation_god",
    )

    def setUp(self):
        AppSetting.objects.filter(key__in=self.password_keys).delete()

    def test_init_settings_seeds_complete_shared_password_contract(self):
        call_command("init_settings")
        settings = dict(
            AppSetting.objects.filter(key__in=self.password_keys).values_list(
                "key", "value"
            )
        )

        self.assertEqual(set(settings), set(self.password_keys))
        self.assertTrue(check_password("1234", settings["revenue_password"]))
        self.assertTrue(check_password("0000", settings["manager_password"]))
        self.assertEqual(settings["god_password"], GOD_CODE_HASH)
        self.assertEqual(settings["manager_password_changed"], "0")
        self.assertEqual(settings["password_generation_revenue"], "0")
        self.assertEqual(settings["password_generation_manager"], "0")
        self.assertEqual(settings["password_generation_god"], "0")
