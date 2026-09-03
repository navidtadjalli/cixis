"""Initial CiXiS roster-import contracts."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from internal.tests.cixis_fixtures import (
    INSTALLATION_ID,
    create_cixis_database,
    make_profile,
    sqlite_snapshot,
)


class InitialRosterImportTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        root = Path(self.temporary_directory.name)
        self.cixis_path = root / "cixis.sqlite3"
        create_cixis_database(self.cixis_path)
        self.profile = make_profile(self.cixis_path)

        from internal.store import InternalStore

        self.store = InternalStore(
            internal_root=root / "internal",
            installation_id=INSTALLATION_ID,
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            key_generation=1,
        )

    def _roster_payloads(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.store.database_path) as connection:
            record_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT uuid FROM internal_encrypted_records WHERE record_type = 'roster'"
                )
            ]
        return [self.store.read(record_id) for record_id in record_ids]

    def test_import_is_idempotent_by_installation_and_source_employee_id(self):
        """Breaks if repeat import duplicates an encrypted roster source identity."""
        from internal.importer import import_initial_roster

        source_before = sqlite_snapshot(self.cixis_path)

        first = import_initial_roster(self.profile, store=self.store)
        second = import_initial_roster(self.profile, store=self.store)

        self.assertEqual((first.created, first.existing), (2, 0))
        self.assertEqual((second.created, second.existing), (0, 2))
        self.assertEqual(
            sorted(
                (
                    payload["source_installation_id"],
                    payload["source_employee_id"],
                    payload["name"],
                    payload["is_active"],
                )
                for payload in self._roster_payloads()
            ),
            [
                (INSTALLATION_ID, "1", "آرش", True),
                (INSTALLATION_ID, "2", "بردیا", False),
            ],
        )
        self.assertEqual(sqlite_snapshot(self.cixis_path), source_before)

    def test_import_rejects_a_tampered_source_identity_instead_of_duplicating_it(self):
        """Breaks if a removed roster blind index lets import recreate a source row."""
        from internal.importer import import_initial_roster
        from internal.store import IntegrityError

        import_initial_roster(self.profile, store=self.store)
        with sqlite3.connect(self.store.database_path) as connection:
            connection.execute(
                """
                DELETE FROM internal_blind_indexes
                WHERE field_name = 'source_identity'
                """
            )

        with self.assertRaises(IntegrityError):
            import_initial_roster(self.profile, store=self.store)
