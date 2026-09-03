"""Encrypted attendance entry, exact metrics, and manager corrections."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
from collections.abc import Callable, Container, Mapping
from typing import Any

from internal.audit import AuditChain
from internal.jalali import assert_mutable_business_date, parse_jalali_date
from internal.repositories import AttendanceRepository, StoredPayload
from internal.services.roster import RosterService
from internal.store import IntegrityError, InternalStore


SHIFT_START = {"morning": 9 * 60, "evening": 16 * 60}
SHIFT_END = {"morning": 17 * 60, "evening": 24 * 60}
WRITE_ROLES = frozenset({"supervisor", "manager"})
CORRECTION_VERSION = 1
CORRECTION_FIELDS = frozenset(
    {
        "staff_uuid",
        "jalali_date",
        "shift",
        "check_in_hour",
        "check_in_minute",
        "check_out_hour",
        "check_out_minute",
    }
)


class AttendanceValidationError(ValueError):
    pass


class AttendanceDuplicateError(AttendanceValidationError):
    pass


class AttendanceConflictError(ValueError):
    pass


class AttendancePermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class AttendanceMetrics:
    worked: int
    late: int
    early: int
    overtime: int
    shifts: int = 1


@dataclass(frozen=True)
class AttendanceEntry:
    uuid: str
    staff_uuid: str
    staff_name: str
    jalali_date: str
    shift: str
    check_in_hour: int
    check_in_minute: int
    check_out_hour: int
    check_out_minute: int
    metrics: AttendanceMetrics
    revision: int


@dataclass(frozen=True)
class CorrectionPreview:
    token: str
    action: str
    impact: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class CorrectionResult:
    action: str
    entry: AttendanceEntry | None


def calculate_attendance(
    shift: object,
    check_in_hour: object,
    check_in_minute: object,
    check_out_hour: object,
    check_out_minute: object,
) -> AttendanceMetrics:
    """Calculate exact attendance metrics on a normalized minute timeline."""
    normalized_shift = _shift(shift)
    in_hour = _clock_part(check_in_hour, maximum=23, label="hour")
    in_minute = _clock_part(check_in_minute, maximum=59, label="minute")
    out_hour = _clock_part(check_out_hour, maximum=23, label="hour")
    out_minute = _clock_part(check_out_minute, maximum=59, label="minute")
    check_in = in_hour * 60 + in_minute
    check_out = out_hour * 60 + out_minute
    normalized_out = check_out if check_out > check_in else check_out + 24 * 60
    scheduled_start = SHIFT_START[normalized_shift]
    scheduled_end = SHIFT_END[normalized_shift]
    return AttendanceMetrics(
        worked=normalized_out - check_in,
        late=max(0, check_in - scheduled_start),
        early=max(0, scheduled_start - check_in),
        overtime=max(0, normalized_out - scheduled_end),
    )


class AttendanceService:
    def __init__(
        self,
        store: InternalStore,
        roster_service: RosterService,
        *,
        finalized_months: Container[str] | object,
        today: str | Callable[[], str] | None = None,
        operational_audit: object | None = None,
        manager_audit: object | None = None,
    ) -> None:
        self.store = store
        self.repository = AttendanceRepository(store)
        self.roster = roster_service
        self.finalized_months = finalized_months
        self.today = today
        self.operational_audit = operational_audit or AuditChain(store, "operational")
        self.manager_audit = manager_audit or AuditChain(store, "manager")

    def create(
        self,
        *,
        staff_uuid: object,
        jalali_date: object,
        shift: object,
        check_in_hour: object,
        check_in_minute: object,
        check_out_hour: object,
        check_out_minute: object,
        actor_role: str,
    ) -> AttendanceEntry:
        self._require_write_role(actor_role)
        with self.store.transaction():
            payload = self._new_payload(
                staff_uuid=staff_uuid,
                jalali_date=jalali_date,
                shift=shift,
                check_in_hour=check_in_hour,
                check_in_minute=check_in_minute,
                check_out_hour=check_out_hour,
                check_out_minute=check_out_minute,
            )
            if self.repository.find_identity(payload["attendance_identity"]):
                raise AttendanceDuplicateError("attendance already exists")
            stored = self.repository.create(payload)
            self.operational_audit.append(
                actor_role=actor_role,
                action="attendance.create",
                before=None,
                after=payload,
                reason=None,
            )
        return self._entry(stored)

    def get(self, record_uuid: str) -> AttendanceEntry:
        return self._entry(self.repository.get(record_uuid))

    def list_entries(
        self,
        *,
        jalali_date: object | None = None,
        shift: object | None = None,
    ) -> tuple[AttendanceEntry, ...]:
        normalized_date = (
            parse_jalali_date(jalali_date) if jalali_date is not None else None
        )
        normalized_shift = _shift(shift) if shift is not None else None
        entries = [self._entry(stored) for stored in self.repository.list()]
        if normalized_date is not None:
            entries = [entry for entry in entries if entry.jalali_date == normalized_date]
        if normalized_shift is not None:
            entries = [entry for entry in entries if entry.shift == normalized_shift]
        shift_order = {"morning": 0, "evening": 1}
        return tuple(
            sorted(
                entries,
                key=lambda entry: (
                    entry.jalali_date,
                    shift_order[entry.shift],
                    self.roster.get(entry.staff_uuid).sort_order,
                    entry.uuid,
                ),
            )
        )

    def preview_correction(
        self,
        record_uuid: str,
        *,
        changes: Mapping[str, Any] | None = None,
        delete: bool = False,
        reason: object | None = None,
        actor_role: str,
    ) -> CorrectionPreview:
        self._require_manager(actor_role)
        normalized_reason = self._reason(reason)
        if not isinstance(delete, bool):
            raise AttendanceValidationError("delete must be boolean")
        if changes is None:
            changes = {}
        if not isinstance(changes, Mapping):
            raise AttendanceValidationError("changes must be an object")
        if set(changes) - CORRECTION_FIELDS:
            raise AttendanceValidationError("unsupported attendance correction field")
        if delete and changes:
            raise AttendanceValidationError("delete cannot include replacement values")
        if not delete and not changes:
            raise AttendanceValidationError("correction must change or delete attendance")

        with self.store.transaction():
            source = self.repository.get(record_uuid)
            source_payload = self._validated_payload(source.payload)
            self._assert_mutable(source_payload["jalali_date"])
            candidate = None
            if not delete:
                candidate = self._replacement_payload(source_payload, changes)
                duplicate = self.repository.find_identity(
                    candidate["attendance_identity"]
                )
                if duplicate is not None and duplicate.record.uuid != record_uuid:
                    raise AttendanceDuplicateError("attendance already exists")
            affected = self._affected_keys(source_payload, candidate)
            impact = self._impact(source.record.uuid, candidate, affected)
            token_payload = {
                "version": CORRECTION_VERSION,
                "action": "delete" if delete else "update",
                "record_uuid": source.record.uuid,
                "expected_revision": source.record.revision,
                "candidate": candidate,
                "reason": normalized_reason,
                "affected_staff_months": [list(key) for key in affected],
                "target_months": sorted({month for _, month in affected}),
                "source_revisions": self._source_revisions(affected),
                "allowance_generation": 0,
                "impact": list(impact),
            }
            token = self._encode_token(token_payload)
        return CorrectionPreview(
            token=token,
            action=token_payload["action"],
            impact=impact,
        )

    def confirm_correction(
        self, token: object, *, actor_role: str
    ) -> CorrectionResult:
        self._require_manager(actor_role)
        preview = self._decode_token(token)
        with self.store.transaction():
            try:
                source = self.repository.get(preview["record_uuid"])
            except KeyError:
                raise AttendanceConflictError("attendance correction is stale") from None
            if source.record.revision != preview["expected_revision"]:
                raise AttendanceConflictError("attendance correction is stale")
            source_payload = self._validated_payload(source.payload)
            affected = self._token_affected_keys(preview)
            for month in preview["target_months"]:
                self._assert_month_mutable(month, source_payload["jalali_date"])
            if self._source_revisions(affected) != preview["source_revisions"]:
                raise AttendanceConflictError("attendance correction is stale")
            candidate = preview["candidate"]
            if candidate is not None:
                candidate = self._validated_payload(candidate, source_staff_uuid=source_payload["staff_uuid"])
                duplicate = self.repository.find_identity(candidate["attendance_identity"])
                if duplicate is not None and duplicate.record.uuid != source.record.uuid:
                    raise AttendanceConflictError("attendance correction target now exists")
            impact = self._impact(source.record.uuid, candidate, affected)
            if list(impact) != preview["impact"]:
                raise AttendanceConflictError("attendance correction impact is stale")

            if preview["action"] == "delete":
                self.repository.delete(
                    source.record.uuid, expected_revision=source.record.revision
                )
                entry = None
            else:
                stored = self.repository.update(
                    source.record.uuid,
                    candidate,
                    expected_revision=source.record.revision,
                )
                entry = self._entry(stored)
            self.manager_audit.append(
                actor_role=actor_role,
                action=f"attendance.{preview['action']}",
                before=source_payload,
                after=candidate,
                reason=preview["reason"],
            )
        return CorrectionResult(action=preview["action"], entry=entry)

    def _new_payload(self, **values: object) -> dict[str, Any]:
        staff_uuid = values["staff_uuid"]
        if not isinstance(staff_uuid, str) or not staff_uuid:
            raise AttendanceValidationError("staff UUID is required")
        try:
            member = self.roster.get(staff_uuid)
        except KeyError:
            raise AttendanceValidationError("staff member does not exist") from None
        if not member.is_active:
            raise AttendanceValidationError("inactive staff cannot receive attendance")
        jalali_date = self._assert_mutable(values["jalali_date"])
        shift = _shift(values["shift"])
        metrics = calculate_attendance(
            shift,
            values["check_in_hour"],
            values["check_in_minute"],
            values["check_out_hour"],
            values["check_out_minute"],
        )
        payload = {
            "staff_uuid": staff_uuid,
            "jalali_date": jalali_date,
            "shift": shift,
            "check_in_hour": values["check_in_hour"],
            "check_in_minute": values["check_in_minute"],
            "check_out_hour": values["check_out_hour"],
            "check_out_minute": values["check_out_minute"],
            "metrics": _metrics_dict(metrics),
        }
        payload["attendance_identity"] = _identity(staff_uuid, jalali_date, shift)
        return payload

    def _replacement_payload(
        self, source: dict[str, Any], changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        values = {field: source[field] for field in CORRECTION_FIELDS}
        values.update(changes)
        staff_uuid = values["staff_uuid"]
        if not isinstance(staff_uuid, str) or not staff_uuid:
            raise AttendanceValidationError("staff UUID is required")
        try:
            member = self.roster.get(staff_uuid)
        except KeyError:
            raise AttendanceValidationError("staff member does not exist") from None
        if staff_uuid != source["staff_uuid"] and not member.is_active:
            raise AttendanceValidationError("inactive staff cannot receive attendance")
        jalali_date = self._assert_mutable(values["jalali_date"])
        shift = _shift(values["shift"])
        metrics = calculate_attendance(
            shift,
            values["check_in_hour"],
            values["check_in_minute"],
            values["check_out_hour"],
            values["check_out_minute"],
        )
        payload = {
            **values,
            "jalali_date": jalali_date,
            "shift": shift,
            "metrics": _metrics_dict(metrics),
            "attendance_identity": _identity(staff_uuid, jalali_date, shift),
        }
        return payload

    def _validated_payload(
        self,
        payload: Mapping[str, Any],
        *,
        source_staff_uuid: str | None = None,
    ) -> dict[str, Any]:
        try:
            staff_uuid = payload["staff_uuid"]
            jalali_date = parse_jalali_date(payload["jalali_date"])
            shift = _shift(payload["shift"])
            metrics = calculate_attendance(
                shift,
                payload["check_in_hour"],
                payload["check_in_minute"],
                payload["check_out_hour"],
                payload["check_out_minute"],
            )
        except (KeyError, AttendanceValidationError, ValueError):
            raise IntegrityError("encrypted attendance payload is invalid") from None
        if not isinstance(staff_uuid, str) or not staff_uuid:
            raise IntegrityError("encrypted attendance payload is invalid")
        expected_identity = _identity(staff_uuid, jalali_date, shift)
        if (
            payload.get("attendance_identity") != expected_identity
            or payload.get("metrics") != _metrics_dict(metrics)
        ):
            raise IntegrityError("encrypted attendance payload is inconsistent")
        if source_staff_uuid is not None:
            try:
                member = self.roster.get(staff_uuid)
            except KeyError:
                raise AttendanceConflictError("attendance correction staff is unavailable") from None
            if staff_uuid != source_staff_uuid and not member.is_active:
                raise AttendanceConflictError("attendance correction staff is inactive")
            self._assert_mutable(jalali_date)
        return dict(payload)

    def _entry(self, stored: StoredPayload) -> AttendanceEntry:
        payload = self._validated_payload(stored.payload)
        try:
            staff_name = self.roster.get(payload["staff_uuid"]).name
        except KeyError:
            raise IntegrityError("attendance references missing roster member") from None
        metrics = AttendanceMetrics(**payload["metrics"])
        return AttendanceEntry(
            uuid=stored.record.uuid,
            staff_uuid=payload["staff_uuid"],
            staff_name=staff_name,
            jalali_date=payload["jalali_date"],
            shift=payload["shift"],
            check_in_hour=payload["check_in_hour"],
            check_in_minute=payload["check_in_minute"],
            check_out_hour=payload["check_out_hour"],
            check_out_minute=payload["check_out_minute"],
            metrics=metrics,
            revision=stored.record.revision,
        )

    def _impact(
        self,
        source_uuid: str,
        candidate: dict[str, Any] | None,
        affected: tuple[tuple[str, str], ...],
    ) -> tuple[dict[str, Any], ...]:
        current = [
            (stored.record.uuid, self._validated_payload(stored.payload))
            for stored in self.repository.list()
        ]
        after = [item for item in current if item[0] != source_uuid]
        if candidate is not None:
            after.append((source_uuid, candidate))
        return tuple(
            {
                "staff_uuid": staff_uuid,
                "jalali_month": month,
                "before": self._aggregate(current, staff_uuid, month),
                "after": self._aggregate(after, staff_uuid, month),
            }
            for staff_uuid, month in affected
        )

    @staticmethod
    def _aggregate(
        entries: list[tuple[str, dict[str, Any]]], staff_uuid: str, month: str
    ) -> dict[str, int]:
        total = {name: 0 for name in ("worked", "late", "early", "overtime", "shifts")}
        for _, payload in entries:
            if payload["staff_uuid"] == staff_uuid and payload["jalali_date"][:7] == month:
                for name in total:
                    total[name] += payload["metrics"][name]
        return total

    def _source_revisions(
        self, affected: tuple[tuple[str, str], ...]
    ) -> list[dict[str, Any]]:
        wanted = set(affected)
        revisions = []
        for stored in self.repository.list():
            payload = self._validated_payload(stored.payload)
            if (payload["staff_uuid"], payload["jalali_date"][:7]) in wanted:
                revisions.append(
                    {"uuid": stored.record.uuid, "revision": stored.record.revision}
                )
        return sorted(revisions, key=lambda item: item["uuid"])

    @staticmethod
    def _affected_keys(
        source: Mapping[str, Any], candidate: Mapping[str, Any] | None
    ) -> tuple[tuple[str, str], ...]:
        keys = {(source["staff_uuid"], source["jalali_date"][:7])}
        if candidate is not None:
            keys.add((candidate["staff_uuid"], candidate["jalali_date"][:7]))
        return tuple(sorted(keys))

    @staticmethod
    def _token_affected_keys(preview: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
        try:
            keys = tuple(
                (item[0], item[1]) for item in preview["affected_staff_months"]
            )
        except (KeyError, IndexError, TypeError):
            raise AttendanceConflictError("attendance correction token is invalid") from None
        if (
            not keys
            or list(keys) != sorted(set(keys))
            or any(
                not isinstance(staff_uuid, str)
                or not isinstance(month, str)
                or len(month) != 7
                for staff_uuid, month in keys
            )
        ):
            raise AttendanceConflictError("attendance correction token is invalid")
        return keys

    def _encode_token(self, payload: Mapping[str, Any]) -> str:
        body = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        signature = hmac.new(self._manager_token_key(), body, hashlib.sha256).digest()
        return f"{_b64encode(body)}.{_b64encode(signature)}"

    def _decode_token(self, token: object) -> dict[str, Any]:
        try:
            if not isinstance(token, str) or token.count(".") != 1:
                raise ValueError
            encoded_body, encoded_signature = token.split(".")
            body = _b64decode(encoded_body)
            signature = _b64decode(encoded_signature)
            if not hmac.compare_digest(
                signature,
                hmac.new(self._manager_token_key(), body, hashlib.sha256).digest(),
            ):
                raise ValueError
            payload = json.loads(body)
            if (
                not isinstance(payload, dict)
                or payload.get("version") != CORRECTION_VERSION
                or payload.get("action") not in {"update", "delete"}
                or not isinstance(payload.get("record_uuid"), str)
                or not isinstance(payload.get("expected_revision"), int)
                or not isinstance(payload.get("target_months"), list)
                or not isinstance(payload.get("source_revisions"), list)
                or not isinstance(payload.get("impact"), list)
                or payload.get("allowance_generation") != 0
            ):
                raise ValueError
            return payload
        except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
            raise AttendanceConflictError("attendance correction token is invalid") from None

    def _manager_token_key(self) -> bytes:
        return self.store.keyed_digest(
            "manager_audit",
            b"cixis-internal-attendance-correction-token-v1",
            b"",
        )

    def _assert_mutable(self, value: object) -> str:
        today = self.today() if callable(self.today) else self.today
        return assert_mutable_business_date(
            value,
            finalized_months=self.finalized_months,
            today=today,
        )

    def _assert_month_mutable(self, month: object, source_date: str) -> None:
        if not isinstance(month, str):
            raise AttendanceConflictError("attendance correction token is invalid")
        representative = source_date if source_date.startswith(f"{month}-") else f"{month}-01"
        try:
            self._assert_mutable(representative)
        except ValueError:
            raise AttendanceConflictError("attendance correction month is locked") from None

    @staticmethod
    def _reason(value: object | None) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str) or len(value.strip()) > 1000:
            raise AttendanceValidationError("reason must contain at most 1000 characters")
        return value.strip() or None

    @staticmethod
    def _require_write_role(role: str) -> None:
        if role not in WRITE_ROLES:
            raise AttendancePermissionError("role cannot create attendance")

    @staticmethod
    def _require_manager(role: str) -> None:
        if role != "manager":
            raise AttendancePermissionError("only manager can correct attendance")


def _shift(value: object) -> str:
    if not isinstance(value, str) or value not in SHIFT_START:
        raise AttendanceValidationError("unsupported attendance shift")
    return value


def _clock_part(value: object, *, maximum: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise AttendanceValidationError(f"attendance {label} is out of range")
    return value


def _identity(staff_uuid: str, jalali_date: str, shift: str) -> str:
    return f"{staff_uuid}\x1f{jalali_date}\x1f{shift}"


def _metrics_dict(metrics: AttendanceMetrics) -> dict[str, int]:
    return {
        "worked": metrics.worked,
        "late": metrics.late,
        "early": metrics.early,
        "overtime": metrics.overtime,
        "shifts": metrics.shifts,
    }


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    if not value or "=" in value:
        raise ValueError
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64encode(decoded) != value:
        raise ValueError
    return decoded
