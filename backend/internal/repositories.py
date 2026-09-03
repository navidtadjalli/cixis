"""Typed repository boundaries over encrypted internal records."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from internal.store import EncryptedRecord, InternalStore


@dataclass(frozen=True)
class StoredPayload:
    record: EncryptedRecord
    payload: dict[str, Any]


class RosterRepository:
    record_type = "roster"

    def __init__(self, store: InternalStore) -> None:
        self.store = store

    def list(self) -> tuple[StoredPayload, ...]:
        return tuple(
            StoredPayload(record, payload)
            for record, payload in self.store.list_records(self.record_type)
        )

    def get(self, record_uuid: str) -> StoredPayload:
        for stored in self.list():
            if stored.record.uuid == record_uuid:
                return stored
        raise KeyError(record_uuid)

    def create(
        self, payload: dict[str, Any], *, blind_index_fields: tuple[str, ...] = ()
    ) -> StoredPayload:
        record = self.store.create(
            self.record_type, payload, blind_index_fields=blind_index_fields
        )
        return StoredPayload(record, dict(payload))

    def update(
        self,
        record_uuid: str,
        payload: dict[str, Any],
        *,
        expected_revision: int,
        blind_index_fields: tuple[str, ...] = (),
    ) -> StoredPayload:
        record = self.store.update(
            record_uuid,
            payload,
            expected_revision=expected_revision,
            blind_index_fields=blind_index_fields,
        )
        return StoredPayload(record, dict(payload))


class AttendanceRepository:
    record_type = "attendance"
    blind_index_fields = ("attendance_identity",)

    def __init__(self, store: InternalStore) -> None:
        self.store = store

    def list(self) -> tuple[StoredPayload, ...]:
        return tuple(
            StoredPayload(record, payload)
            for record, payload in self.store.list_records(self.record_type)
        )

    def get(self, record_uuid: str) -> StoredPayload:
        for stored in self.list():
            if stored.record.uuid == record_uuid:
                return stored
        raise KeyError(record_uuid)

    def find_identity(self, identity: str) -> StoredPayload | None:
        if not self.store.has_blind_index(
            self.record_type, "attendance_identity", identity
        ):
            return None
        for stored in self.list():
            if stored.payload.get("attendance_identity") == identity:
                return stored
        raise ValueError("authenticated attendance index has no matching payload")

    def create(self, payload: dict[str, Any]) -> StoredPayload:
        record = self.store.create(
            self.record_type,
            payload,
            blind_index_fields=self.blind_index_fields,
        )
        return StoredPayload(record, dict(payload))

    def update(
        self, record_uuid: str, payload: dict[str, Any], *, expected_revision: int
    ) -> StoredPayload:
        record = self.store.update(
            record_uuid,
            payload,
            expected_revision=expected_revision,
            blind_index_fields=self.blind_index_fields,
        )
        return StoredPayload(record, dict(payload))

    def delete(self, record_uuid: str, *, expected_revision: int) -> None:
        self.store.delete(record_uuid, expected_revision=expected_revision)
