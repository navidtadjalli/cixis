"""Encrypted roster behavior shared by internal APIs and later domains."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from internal.repositories import RosterRepository, StoredPayload
from internal.store import IntegrityError, InternalStore


WRITE_ROLES = frozenset({"supervisor", "manager"})


class RosterValidationError(ValueError):
    pass


class RosterPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class RosterMember:
    uuid: str
    name: str
    sort_order: int
    is_active: bool
    revision: int


class RosterService:
    def __init__(self, store: InternalStore) -> None:
        self.repository = RosterRepository(store)

    def list_members(self, *, status: str = "active") -> tuple[RosterMember, ...]:
        if status not in {"active", "inactive", "all"}:
            raise RosterValidationError("unsupported roster status")
        members = [self._member(stored) for stored in self.repository.list()]
        if status != "all":
            wanted = status == "active"
            members = [member for member in members if member.is_active is wanted]
        return tuple(sorted(members, key=lambda item: (item.sort_order, item.uuid)))

    def get(self, member_uuid: str) -> RosterMember:
        return self._member(self.repository.get(member_uuid))

    def create(
        self,
        *,
        name: object,
        actor_role: str,
        sort_order: object | None = None,
    ) -> RosterMember:
        self._require_write_role(actor_role)
        normalized_name = self._name(name)
        if sort_order is None:
            all_members = self.list_members(status="all")
            normalized_sort_order = max(
                (member.sort_order for member in all_members), default=0
            ) + 1
        elif isinstance(sort_order, int) and not isinstance(sort_order, bool):
            normalized_sort_order = sort_order
        else:
            raise RosterValidationError("sort order must be an integer")
        return self._member(
            self.repository.create(
                {
                    "name": normalized_name,
                    "sort_order": normalized_sort_order,
                    "is_active": True,
                }
            )
        )

    def rename(
        self, member_uuid: str, *, name: object, actor_role: str
    ) -> RosterMember:
        self._require_write_role(actor_role)
        stored = self.repository.get(member_uuid)
        payload = dict(stored.payload)
        payload["name"] = self._name(name)
        return self._member(self._update(stored, payload))

    def deactivate(self, member_uuid: str, *, actor_role: str) -> RosterMember:
        self._require_manager(actor_role)
        return self._set_active(member_uuid, False)

    def reactivate(self, member_uuid: str, *, actor_role: str) -> RosterMember:
        self._require_manager(actor_role)
        return self._set_active(member_uuid, True)

    def _set_active(self, member_uuid: str, is_active: bool) -> RosterMember:
        stored = self.repository.get(member_uuid)
        payload = dict(stored.payload)
        payload["is_active"] = is_active
        return self._member(self._update(stored, payload))

    def _update(self, stored: StoredPayload, payload: dict[str, Any]) -> StoredPayload:
        blind_fields = ("source_identity",) if "source_identity" in payload else ()
        return self.repository.update(
            stored.record.uuid,
            payload,
            expected_revision=stored.record.revision,
            blind_index_fields=blind_fields,
        )

    @staticmethod
    def _member(stored: StoredPayload) -> RosterMember:
        payload = stored.payload
        if (
            not isinstance(payload.get("name"), str)
            or not isinstance(payload.get("sort_order"), int)
            or not isinstance(payload.get("is_active"), bool)
        ):
            raise IntegrityError("encrypted roster payload is invalid")
        return RosterMember(
            uuid=stored.record.uuid,
            name=payload["name"],
            sort_order=payload["sort_order"],
            is_active=payload["is_active"],
            revision=stored.record.revision,
        )

    @staticmethod
    def _name(value: object) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160:
            raise RosterValidationError("roster name must contain 1 to 160 characters")
        return value.strip()

    @staticmethod
    def _require_write_role(role: str) -> None:
        if role not in WRITE_ROLES:
            raise RosterPermissionError("role cannot change roster names")

    @staticmethod
    def _require_manager(role: str) -> None:
        if role != "manager":
            raise RosterPermissionError("only manager can change roster status")
