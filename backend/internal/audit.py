"""Append-only, predecessor-bound audit events stored as encrypted records."""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
from collections.abc import Callable, Mapping
from typing import Any

from internal.store import IntegrityError, InternalStore


class AuditChain:
    def __init__(
        self,
        store: InternalStore,
        stream: str,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if stream not in {"operational", "manager"}:
            raise ValueError("unsupported audit stream")
        self.store = store
        self.stream = stream
        self.record_type = f"{stream}_audit"
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def append(
        self,
        *,
        actor_role: str,
        action: str,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        reason: str | None = None,
    ) -> None:
        with self.store.transaction():
            entries = self._verified_entries()
            previous_hash = entries[-1]["entry_hash"] if entries else None
            event = {
                "sequence": len(entries) + 1,
                "previous_hash": previous_hash,
                "actor_role": actor_role,
                "at": self._instant(),
                "action": action,
                "reason": reason,
                "before": dict(before) if before is not None else None,
                "after": dict(after) if after is not None else None,
            }
            event["entry_hash"] = self._hash(event)
            self.store.create(self.record_type, event)

    def _verified_entries(self) -> list[dict[str, Any]]:
        entries = [payload for _, payload in self.store.list_records(self.record_type)]
        try:
            entries.sort(key=lambda item: item["sequence"])
        except (KeyError, TypeError):
            raise IntegrityError("audit sequence is invalid") from None
        previous_hash = None
        for sequence, entry in enumerate(entries, start=1):
            unsigned = dict(entry)
            entry_hash = unsigned.pop("entry_hash", None)
            if (
                entry.get("sequence") != sequence
                or entry.get("previous_hash") != previous_hash
                or not isinstance(entry_hash, str)
                or not hmac.compare_digest(entry_hash, self._hash(unsigned))
            ):
                raise IntegrityError("audit chain is invalid")
            previous_hash = entry_hash
        return entries

    def _hash(self, value: Mapping[str, Any]) -> str:
        serialized = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return self.store.keyed_digest(
            self.record_type,
            b"cixis-internal-audit-entry-v1",
            serialized,
        ).hex()

    def _instant(self) -> str:
        value = self.clock()
        if value.tzinfo is None:
            raise ValueError("audit clock must return an aware datetime")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
