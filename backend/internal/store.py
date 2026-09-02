"""Encrypted SQLite persistence owned exclusively by the internal product."""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from uuid import uuid4

from internal.crypto import (
    EncryptedPayload,
    _encrypt_payload_with_nonce,
    blind_index,
    decrypt_payload,
)


FORMAT_VERSION = 1
NONCE_RETRY_LIMIT = 16
INTERNAL_DATABASE_NAME = "internal.sqlite3"


class IntegrityError(ValueError):
    """Raised when an encrypted-store integrity invariant is not satisfied."""


class StoreBoundaryError(ValueError):
    """Raised when a caller attempts to use a database outside its internal root."""


@dataclass(frozen=True)
class EncryptedRecord:
    uuid: str
    record_type: str
    key_generation: int
    revision: int
    nonce: bytes
    ciphertext: bytes


def verify_live_manifest(store: "InternalStore", record_type: str) -> None:
    store.verify_live_manifest(record_type)


class InternalStore:
    """Persist encrypted payloads below the authoritative internal-data root."""

    def __init__(
        self,
        *,
        internal_root: Path,
        installation_id: str,
        encryption_key: bytes,
        blind_index_key: bytes,
        integrity_key: bytes,
        key_generation: int,
        nonce_source: Callable[[], bytes] | None = None,
        database_path: Path | None = None,
    ) -> None:
        self.internal_root = Path(internal_root).resolve()
        expected_database_path = self.internal_root / INTERNAL_DATABASE_NAME
        if database_path is not None and Path(database_path).resolve() != expected_database_path:
            raise StoreBoundaryError(
                "internal database path must be the fixed file inside the internal root"
            )
        self.database_path = expected_database_path
        self.installation_id = installation_id
        self.encryption_key = encryption_key
        self.blind_index_key = blind_index_key
        self.integrity_key = integrity_key
        self.key_generation = key_generation
        self._nonce_source = nonce_source or (lambda: secrets.token_bytes(12))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA secure_delete = ON")
        self._connection.execute("PRAGMA temp_store = MEMORY")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_encrypted_records (
                uuid TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                key_generation INTEGER NOT NULL,
                revision INTEGER NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                UNIQUE (key_generation, nonce)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_nonce_registry (
                key_generation INTEGER NOT NULL,
                nonce BLOB NOT NULL,
                UNIQUE (key_generation, nonce)
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_live_manifests (
                record_type TEXT PRIMARY KEY,
                key_generation INTEGER NOT NULL,
                manifest_uuid TEXT NOT NULL,
                revision INTEGER NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_blind_indexes (
                record_uuid TEXT NOT NULL,
                field_name TEXT NOT NULL,
                value BLOB NOT NULL,
                PRIMARY KEY (record_uuid, field_name),
                FOREIGN KEY (record_uuid)
                    REFERENCES internal_encrypted_records(uuid)
            )
            """
        )
        self._connection.commit()

    def create(
        self,
        record_type: str,
        payload: Mapping[str, Any],
        *,
        blind_index_fields: Iterable[str] = (),
    ) -> EncryptedRecord:
        """Encrypt and persist a revision-one record with a unique nonce."""
        record_uuid = str(uuid4())
        revision = 1
        index_fields = tuple(sorted(set(blind_index_fields)))
        for field_name in index_fields:
            if not isinstance(payload.get(field_name), str):
                raise ValueError("blind indexes require string payload fields")
        with self._connection:
            nonce = self._fresh_nonce()
            encrypted = _encrypt_payload_with_nonce(
                key=self.encryption_key,
                aad=self._aad(record_uuid, record_type, revision),
                payload={
                    "payload": dict(payload),
                    "blind_index_fields": list(index_fields),
                },
                nonce=nonce,
            )
            self._connection.execute(
                """
                INSERT INTO internal_encrypted_records
                    (uuid, record_type, key_generation, revision, nonce, ciphertext)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_uuid,
                    record_type,
                    self.key_generation,
                    revision,
                    encrypted.nonce,
                    encrypted.ciphertext,
                ),
            )
            self._connection.executemany(
                """
                INSERT INTO internal_blind_indexes (record_uuid, field_name, value)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        record_uuid,
                        field_name,
                        blind_index(key=self.blind_index_key, value=payload[field_name]),
                    )
                    for field_name in index_fields
                ],
            )
            self._write_live_manifest(record_type)
        return EncryptedRecord(
            uuid=record_uuid,
            record_type=record_type,
            key_generation=self.key_generation,
            revision=revision,
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext,
        )

    def verify_live_manifest(self, record_type: str) -> None:
        """Authenticate the expected live rows for one record domain."""
        manifest = self._connection.execute(
            """
            SELECT key_generation, manifest_uuid, revision, nonce, ciphertext
            FROM internal_live_manifests WHERE record_type = ?
            """,
            (record_type,),
        ).fetchone()
        actual_records = self._manifest_records(record_type)
        if manifest is None:
            if actual_records:
                raise IntegrityError("live records have no authenticated manifest")
            return
        key_generation, manifest_uuid, revision, nonce, ciphertext = manifest
        if key_generation != self.key_generation:
            raise IntegrityError("manifest key generation is unavailable")
        expected = decrypt_payload(
            key=self.integrity_key,
            aad=self._aad(
                manifest_uuid,
                record_type,
                revision,
                purpose="live_manifest",
            ),
            encrypted=EncryptedPayload(nonce=nonce, ciphertext=ciphertext),
        )
        if expected.get("records") != actual_records:
            raise IntegrityError("live record manifest does not match the database")

    def verify_live_manifests(self) -> None:
        """Verify every record type observed in internal records or manifests."""
        record_types = self._connection.execute(
            """
            SELECT record_type FROM internal_encrypted_records
            UNION
            SELECT record_type FROM internal_live_manifests
            ORDER BY record_type
            """
        ).fetchall()
        for (record_type,) in record_types:
            self.verify_live_manifest(record_type)

    def sqlite_security_pragmas(self) -> dict[str, int]:
        """Return active connection hardening settings for startup verification."""
        return {
            "foreign_keys": int(
                self._connection.execute("PRAGMA foreign_keys").fetchone()[0]
            ),
            "secure_delete": int(
                self._connection.execute("PRAGMA secure_delete").fetchone()[0]
            ),
            "temp_store": int(
                self._connection.execute("PRAGMA temp_store").fetchone()[0]
            ),
        }

    def read(self, record_uuid: str) -> dict[str, Any]:
        record = self._record_by_uuid(record_uuid)
        self.verify_live_manifests()
        return self._decrypt(record)

    def read_with_revision(
        self, record_uuid: str, expected_revision: int
    ) -> dict[str, Any]:
        """Read only when the caller's expected revision still matches."""
        record = self._record_by_uuid(record_uuid)
        if record.revision != expected_revision:
            raise IntegrityError("record revision does not match the expected revision")
        self.verify_live_manifests()
        return self._decrypt(record)

    def _record_by_uuid(self, record_uuid: str) -> EncryptedRecord:
        row = self._connection.execute(
            """
            SELECT uuid, record_type, key_generation, revision, nonce, ciphertext
            FROM internal_encrypted_records WHERE uuid = ?
            """,
            (record_uuid,),
        ).fetchone()
        if row is None:
            raise KeyError(record_uuid)
        return EncryptedRecord(*row)

    def _decrypt(self, record: EncryptedRecord) -> dict[str, Any]:
        if record.key_generation != self.key_generation:
            raise IntegrityError("record key generation is unavailable")
        decrypted = decrypt_payload(
            key=self.encryption_key,
            aad=self._aad(record.uuid, record.record_type, record.revision),
            encrypted=EncryptedPayload(
                nonce=record.nonce,
                ciphertext=record.ciphertext,
            ),
        )
        payload = decrypted.get("payload")
        index_fields = decrypted.get("blind_index_fields")
        if not isinstance(payload, dict) or not isinstance(index_fields, list):
            raise IntegrityError("encrypted record payload has an invalid format")
        stored_indexes = dict(
            self._connection.execute(
                """
                SELECT field_name, value FROM internal_blind_indexes
                WHERE record_uuid = ?
                """,
                (record.uuid,),
            ).fetchall()
        )
        if set(stored_indexes) != set(index_fields):
            raise IntegrityError("blind index fields do not match the encrypted record")
        for field_name in index_fields:
            value = payload.get(field_name)
            if not isinstance(value, str) or not hmac.compare_digest(
                stored_indexes[field_name],
                blind_index(key=self.blind_index_key, value=value),
            ):
                raise IntegrityError("blind index does not match the encrypted record")
        return payload

    def _fresh_nonce(self) -> bytes:
        for _ in range(NONCE_RETRY_LIMIT):
            nonce = self._nonce_source()
            try:
                self._connection.execute(
                    """
                    INSERT INTO internal_nonce_registry (key_generation, nonce)
                    VALUES (?, ?)
                    """,
                    (self.key_generation, nonce),
                )
                return nonce
            except sqlite3.IntegrityError:
                continue
        raise IntegrityError("unable to generate a unique encryption nonce")

    def _write_live_manifest(self, record_type: str) -> None:
        current = self._connection.execute(
            """
            SELECT manifest_uuid, revision FROM internal_live_manifests
            WHERE record_type = ?
            """,
            (record_type,),
        ).fetchone()
        manifest_uuid, revision = (
            current[0],
            current[1] + 1,
        ) if current else (str(uuid4()), 1)
        nonce = self._fresh_nonce()
        encrypted = _encrypt_payload_with_nonce(
            key=self.integrity_key,
            aad=self._aad(
                manifest_uuid,
                record_type,
                revision,
                purpose="live_manifest",
            ),
            payload={"records": self._manifest_records(record_type)},
            nonce=nonce,
        )
        self._connection.execute(
            """
            INSERT INTO internal_live_manifests
                (record_type, key_generation, manifest_uuid, revision, nonce, ciphertext)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_type) DO UPDATE SET
                key_generation = excluded.key_generation,
                manifest_uuid = excluded.manifest_uuid,
                revision = excluded.revision,
                nonce = excluded.nonce,
                ciphertext = excluded.ciphertext
            """,
            (
                record_type,
                self.key_generation,
                manifest_uuid,
                revision,
                encrypted.nonce,
                encrypted.ciphertext,
            ),
        )

    def _manifest_records(self, record_type: str) -> list[dict[str, object]]:
        rows = self._connection.execute(
            """
            SELECT uuid, record_type, revision FROM internal_encrypted_records
            WHERE record_type = ? ORDER BY uuid
            """,
            (record_type,),
        ).fetchall()
        return [
            {"uuid": record_uuid, "record_type": row_type, "revision": revision}
            for record_uuid, row_type, revision in rows
        ]

    def _aad(
        self,
        record_uuid: str,
        record_type: str,
        revision: int,
        *,
        purpose: str = "record",
    ) -> bytes:
        return json.dumps(
            {
                "format_version": FORMAT_VERSION,
                "installation_id": self.installation_id,
                "key_generation": self.key_generation,
                "record_uuid": record_uuid,
                "record_type": record_type,
                "revision": revision,
                "purpose": purpose,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
