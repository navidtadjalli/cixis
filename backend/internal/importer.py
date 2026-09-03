"""Idempotent, read-only import of the existing CiXiS roster."""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from pos.internal_bridge import open_catalog_readonly

from internal.compatibility import CixisProfile, CompatibilityError, verify_cixis_profile
from internal.store import InternalStore


@dataclass(frozen=True)
class RosterImportResult:
    created: int
    existing: int


def _source_identity(installation_id: str, employee_id: int) -> str:
    return f"{installation_id}:{employee_id}"


def import_initial_roster(
    profile: CixisProfile, *, store: InternalStore
) -> RosterImportResult:
    """Snapshot every existing source employee once without modifying CiXiS."""
    verify_cixis_profile(profile)
    connection = open_catalog_readonly(profile.database_path)
    try:
        rows = connection.execute(
            """
            SELECT id, name, sort_order, is_active
            FROM pos_employee
            ORDER BY sort_order, id
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise CompatibilityError("CiXiS roster is unavailable") from error
    finally:
        connection.close()

    created = 0
    existing = 0
    for employee_id, name, sort_order, is_active in rows:
        if (
            not isinstance(employee_id, int)
            or not isinstance(name, str)
            or not isinstance(sort_order, int)
            or is_active not in (0, 1)
        ):
            raise CompatibilityError("CiXiS roster is incompatible")
        source_employee_id = str(employee_id)
        source_identity = _source_identity(profile.installation_id, employee_id)
        if store.has_blind_index("roster", "source_identity", source_identity):
            existing += 1
            continue
        store.create(
            "roster",
            {
                "source_installation_id": profile.installation_id,
                "source_employee_id": source_employee_id,
                "source_identity": source_identity,
                "name": name,
                "sort_order": sort_order,
                "is_active": bool(is_active),
            },
            blind_index_fields=("source_identity",),
        )
        created += 1
    return RosterImportResult(created=created, existing=existing)
