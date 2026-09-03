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
