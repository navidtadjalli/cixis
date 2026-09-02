from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase


class InternalStoreTests(SimpleTestCase):
    def test_persists_and_loads_an_encrypted_record(self):
        """Breaks if records are not durably encrypted in the internal store."""
        from internal.store import InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )

            record = store.create(
                "roster", {"name": "آرش", "jalali_date": "1405-06-11"}
            )

            self.assertEqual(
                store.read(record.uuid),
                {"name": "آرش", "jalali_date": "1405-06-11"},
            )
            self.assertNotIn("آرش".encode(), database_path.read_bytes())

    def test_rejects_a_read_with_a_stale_revision(self):
        """Breaks if callers can read a record against the wrong revision."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            store = InternalStore(
                database_path=Path(temporary_directory) / "internal.sqlite3",
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create("roster", {"name": "آرش"})

            with self.assertRaises(IntegrityError):
                store.read_with_revision(record.uuid, record.revision + 1)

    def test_retries_a_nonce_collision_before_encrypting_another_record(self):
        """Breaks if a reused nonce is accepted under one key generation."""
        from internal.store import InternalStore

        nonce_source = iter(
            [b"n" * 12, b"x" * 12, b"n" * 12, b"m" * 12, b"y" * 12]
        ).__next__
        with TemporaryDirectory() as temporary_directory:
            store = InternalStore(
                database_path=Path(temporary_directory) / "internal.sqlite3",
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
                nonce_source=nonce_source,
            )

            first = store.create("roster", {"name": "آرش"})
            second = store.create("roster", {"name": "بردیا"})

            self.assertEqual(first.nonce, b"n" * 12)
            self.assertEqual(second.nonce, b"m" * 12)

    def test_manifest_detects_a_deleted_live_record(self):
        """Breaks if deleting a SQLite row leaves integrity verification green."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create("roster", {"name": "آرش"})
            store.verify_live_manifest("roster")

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "DELETE FROM internal_encrypted_records WHERE uuid = ?",
                    (record.uuid,),
                )

            with self.assertRaises(IntegrityError):
                store.verify_live_manifest("roster")

    def test_manifest_detects_an_inserted_live_record(self):
        """Breaks if inserting a SQLite row leaves integrity verification green."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create("roster", {"name": "آرش"})

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO internal_encrypted_records
                        (uuid, record_type, key_generation, revision, nonce, ciphertext)
                    VALUES (?, 'roster', 2, 1, ?, ?)
                    """,
                    ("13ed53d0-b70f-4d5f-96d2-c05beb2299f9", b"z" * 12, record.ciphertext),
                )

            with self.assertRaises(IntegrityError):
                store.verify_live_manifest("roster")

    def test_read_verifies_its_live_manifest_before_decrypting(self):
        """Breaks if ordinary reads miss deletion of another live domain row."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            deleted = store.create("roster", {"name": "آرش"})
            retained = store.create("roster", {"name": "بردیا"})

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "DELETE FROM internal_encrypted_records WHERE uuid = ?",
                    (deleted.uuid,),
                )

            with self.assertRaises(IntegrityError):
                store.read(retained.uuid)

    def test_exposes_enforced_sqlite_secure_delete_and_memory_temp_storage(self):
        """Breaks if encrypted SQLite connections lose either storage hardening pragma."""
        from internal.store import InternalStore

        with TemporaryDirectory() as temporary_directory:
            store = InternalStore(
                database_path=Path(temporary_directory) / "internal.sqlite3",
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )

            self.assertEqual(
                store.sqlite_security_pragmas(),
                {"secure_delete": 1, "temp_store": 2},
            )

    def test_module_manifest_verifier_checks_a_store_domain(self):
        """Breaks if domain services cannot invoke authenticated manifest checks."""
        from internal.store import InternalStore, verify_live_manifest

        with TemporaryDirectory() as temporary_directory:
            store = InternalStore(
                database_path=Path(temporary_directory) / "internal.sqlite3",
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            store.create("roster", {"name": "آرش"})

            self.assertIsNone(verify_live_manifest(store, "roster"))

    def test_rejects_ciphertext_changed_in_sqlite(self):
        """Breaks if store reads a row whose authenticated ciphertext was modified."""
        from cryptography.exceptions import InvalidTag

        from internal.store import InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create("roster", {"name": "آرش"})

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "UPDATE internal_encrypted_records SET ciphertext = ? WHERE uuid = ?",
                    (record.ciphertext[:-1] + b"x", record.uuid),
                )

            with self.assertRaises(InvalidTag):
                store.read(record.uuid)

    def test_rejects_a_stored_revision_changed_outside_the_authenticated_record(self):
        """Breaks if revision tampering is not rejected before a record is read."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create("roster", {"name": "آرش"})

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    "UPDATE internal_encrypted_records SET revision = 2 WHERE uuid = ?",
                    (record.uuid,),
                )

            with self.assertRaises(IntegrityError):
                store.read(record.uuid)

    def test_rejects_a_blind_index_changed_in_sqlite(self):
        """Breaks if a tampered equality index is trusted after decryption."""
        from internal.store import IntegrityError, InternalStore

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "internal.sqlite3"
            store = InternalStore(
                database_path=database_path,
                installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                encryption_key=bytes(range(32)),
                blind_index_key=b"b" * 32,
                integrity_key=b"i" * 32,
                key_generation=1,
            )
            record = store.create(
                "roster", {"name": "آرش"}, blind_index_fields=("name",)
            )

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    UPDATE internal_blind_indexes SET value = ?
                    WHERE record_uuid = ? AND field_name = 'name'
                    """,
                    (b"x" * 32, record.uuid),
                )

            with self.assertRaises(IntegrityError):
                store.read(record.uuid)
