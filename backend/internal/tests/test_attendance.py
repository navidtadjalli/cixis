"""Attendance calculation, encrypted persistence, correction, and API contracts."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import Client, SimpleTestCase, override_settings

from internal.tests.test_auth import CHANNEL_SECRET


class AttendanceCalculationTests(SimpleTestCase):
    def test_cross_midnight_and_equal_times_use_exact_integer_minutes(self):
        """Breaks if midnight normalization or scheduled metrics drift."""
        from internal.services.attendance import calculate_attendance

        evening = calculate_attendance("evening", 16, 33, 1, 10)

        self.assertEqual(
            (evening.worked, evening.late, evening.early, evening.overtime, evening.shifts),
            (517, 33, 0, 70, 1),
        )
        self.assertEqual(
            calculate_attendance("morning", 9, 0, 9, 0).worked,
            1440,
        )

    def test_shift_and_clock_inputs_are_strict_bounded_integers(self):
        """Breaks if booleans, invalid shifts, or out-of-range clocks enter storage."""
        from internal.services.attendance import AttendanceValidationError, calculate_attendance

        invalid_inputs = (
            ("night", 9, 0, 17, 0),
            ("morning", True, 0, 17, 0),
            ("morning", 24, 0, 17, 0),
            ("morning", 9, 60, 17, 0),
            ("morning", 9, 0, -1, 0),
            ("morning", 9, 0, 17, 60),
        )

        for values in invalid_inputs:
            with self.subTest(values=values), self.assertRaises(AttendanceValidationError):
                calculate_attendance(*values)


class AttendanceDomainTests(SimpleTestCase):
    def setUp(self):
        from internal.services.roster import RosterService
        from internal.store import InternalStore

        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store = InternalStore(
            internal_root=Path(self.temporary_directory.name),
            installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            manager_encryption_key=b"E" * 32,
            manager_blind_index_key=b"B" * 32,
            manager_integrity_key=b"I" * 32,
            key_generation=1,
        )
        self.roster = RosterService(self.store)
        self.member = self.roster.create(name="آرش", actor_role="manager")

    def _service(self, **kwargs):
        from internal.services.attendance import AttendanceService

        return AttendanceService(
            self.store,
            self.roster,
            finalized_months=kwargs.pop("finalized_months", set()),
            today=kwargs.pop("today", "1405-06-12"),
            **kwargs,
        )

    def _create(self, service, **kwargs):
        values = {
            "staff_uuid": self.member.uuid,
            "jalali_date": "1405-06-11",
            "shift": "morning",
            "check_in_hour": 9,
            "check_in_minute": 0,
            "check_out_hour": 17,
            "check_out_minute": 0,
            "actor_role": "supervisor",
        }
        values.update(kwargs)
        return service.create(**values)

    def test_create_persists_both_shifts_but_rejects_an_exact_duplicate(self):
        """Breaks if identity is not staff/date/shift or duplicate save upserts."""
        from internal.services.attendance import AttendanceDuplicateError

        service = self._service()
        morning = self._create(service)
        evening = self._create(
            service,
            shift="evening",
            check_in_hour=16,
            check_in_minute=33,
            check_out_hour=1,
            check_out_minute=10,
        )

        with self.assertRaises(AttendanceDuplicateError):
            self._create(service, check_in_hour=10)

        entries = service.list_entries(jalali_date="1405-06-11")
        self.assertEqual([entry.uuid for entry in entries], [morning.uuid, evening.uuid])
        self.assertEqual(entries[1].metrics.worked, 517)
        self.assertEqual(len(self.store.list_records("attendance")), 2)
        self.assertEqual(len(self.store.list_records("operational_audit")), 2)

    def test_create_rejects_future_finalized_inactive_and_unauthorized_inputs(self):
        """Breaks if entry bypasses Jalali locks, active roster, or role boundaries."""
        from internal.jalali import DateLockedError
        from internal.services.attendance import (
            AttendancePermissionError,
            AttendanceValidationError,
        )

        with self.assertRaises(DateLockedError):
            self._create(self._service(), jalali_date="1405-06-13")
        with self.assertRaises(DateLockedError):
            self._create(
                self._service(finalized_months={"1405-06"}),
                jalali_date="1405-06-11",
            )
        with self.assertRaises(AttendancePermissionError):
            self._create(self._service(), actor_role="god")

        self.roster.deactivate(self.member.uuid, actor_role="manager")
        with self.assertRaises(AttendanceValidationError):
            self._create(self._service())

    def test_create_rechecks_month_lock_after_acquiring_immediate_transaction(self):
        """Breaks if finalization can race between validation and attendance insert."""
        observed_transaction_state = []
        store = self.store

        class FinalizedMonthsProbe:
            def contains(self, month):
                observed_transaction_state.append(store._connection.in_transaction)
                return False

        self._create(self._service(finalized_months=FinalizedMonthsProbe()))

        self.assertEqual(observed_transaction_state, [True])

    def test_manager_preview_recomputes_month_and_confirm_appends_audit(self):
        """Breaks if correction impact, revision binding, or manager audit disappears."""
        service = self._service()
        original = self._create(service)

        preview = service.preview_correction(
            original.uuid,
            changes={
                "check_in_hour": 10,
                "check_out_hour": 18,
            },
            reason="اصلاح ساعت",
            actor_role="manager",
        )

        self.assertEqual(preview.action, "update")
        self.assertEqual(len(preview.impact), 1)
        self.assertEqual(preview.impact[0]["before"]["worked"], 480)
        self.assertEqual(preview.impact[0]["after"]["worked"], 480)
        self.assertEqual(preview.impact[0]["after"]["late"], 60)
        self.assertEqual(preview.impact[0]["after"]["overtime"], 60)

        result = service.confirm_correction(preview.token, actor_role="manager")

        self.assertEqual(result.action, "update")
        self.assertEqual(result.entry.revision, 2)
        self.assertEqual(result.entry.metrics.late, 60)
        audit = self.store.list_records("manager_audit")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0][1]["action"], "attendance.update")
        self.assertEqual(audit[0][1]["reason"], "اصلاح ساعت")

    def test_supervisor_cannot_correct_and_stale_preview_cannot_mutate(self):
        """Breaks if saved rows become mutable or month changes evade token conflicts."""
        from internal.services.attendance import (
            AttendanceConflictError,
            AttendancePermissionError,
        )

        service = self._service()
        original = self._create(service)
        with self.assertRaises(AttendancePermissionError):
            service.preview_correction(
                original.uuid,
                changes={"check_in_hour": 10},
                actor_role="supervisor",
            )

        preview = service.preview_correction(
            original.uuid,
            changes={"check_in_hour": 10},
            actor_role="manager",
        )
        self._create(
            service,
            shift="evening",
            check_in_hour=16,
            check_out_hour=23,
        )

        with self.assertRaises(AttendanceConflictError):
            service.confirm_correction(preview.token, actor_role="manager")
        self.assertEqual(service.get(original.uuid).revision, 1)

    def test_malformed_correction_base64_is_a_fail_closed_conflict(self):
        """Breaks if malformed tokens escape as decoder errors or reach mutation code."""
        from internal.services.attendance import AttendanceConflictError

        with self.assertRaises(AttendanceConflictError):
            self._service().confirm_correction("a.a", actor_role="manager")

    def test_manager_can_preview_and_confirm_delete(self):
        """Breaks if an unfinalized manager deletion is not previewed and audited."""
        service = self._service()
        original = self._create(service)

        preview = service.preview_correction(
            original.uuid,
            delete=True,
            reason="ثبت تکراری",
            actor_role="manager",
        )
        self.assertEqual(preview.impact[0]["after"]["shifts"], 0)

        result = service.confirm_correction(preview.token, actor_role="manager")

        self.assertEqual(result.action, "delete")
        self.assertIsNone(result.entry)
        self.assertEqual(service.list_entries(), ())
        self.assertEqual(
            self.store.list_records("manager_audit")[0][1]["action"],
            "attendance.delete",
        )

    def test_audit_failure_rolls_back_record_manifest_and_indexes(self):
        """Breaks if attendance can commit without its required audit event."""
        class FailingAudit:
            def append(self, **event):
                raise RuntimeError("audit unavailable")

        service = self._service(operational_audit=FailingAudit())

        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            self._create(service)

        self.assertEqual(self.store.list_records("attendance"), ())
        self.assertFalse(
            self.store.has_blind_index(
                "attendance",
                "attendance_identity",
                f"{self.member.uuid}\x1f1405-06-11\x1fmorning",
            )
        )

    def test_audit_records_are_append_only_at_the_store_boundary(self):
        """Breaks if trusted store helpers can rewrite or remove audit history."""
        from internal.store import IntegrityError

        self._create(self._service())
        record, payload = self.store.list_records("operational_audit")[0]

        with self.assertRaises(IntegrityError):
            self.store.update(record.uuid, payload, expected_revision=record.revision)
        with self.assertRaises(IntegrityError):
            self.store.delete(record.uuid, expected_revision=record.revision)

    def test_store_delete_requires_an_expected_revision(self):
        """Breaks if a future domain can bypass delete conflict detection."""
        entry = self._create(self._service())

        with self.assertRaises(TypeError):
            self.store.delete(entry.uuid)

    def test_audit_chain_serializes_head_check_and_append_itself(self):
        """Breaks if a direct audit append can race into a duplicate chain head."""
        from internal.audit import AuditChain

        observed_transaction_state = []
        original_list_records = self.store.list_records

        def observed_list_records(record_type):
            if record_type == "operational_audit":
                observed_transaction_state.append(self.store._connection.in_transaction)
            return original_list_records(record_type)

        self.store.list_records = observed_list_records
        AuditChain(self.store, "operational").append(
            actor_role="supervisor",
            action="attendance.probe",
            before=None,
            after={"value": 1},
        )

        self.assertEqual(observed_transaction_state, [True])

    def test_operational_keys_cannot_decrypt_manager_correction_audit(self):
        """Breaks if manager-only audit details use the supervisor keyset."""
        from internal.services.attendance import AttendanceService
        from internal.services.roster import RosterService
        from internal.store import InternalStore, StoreKeyUnavailable

        root = Path(self.temporary_directory.name) / "split-keysets"
        manager_store = InternalStore(
            internal_root=root,
            installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            manager_encryption_key=b"E" * 32,
            manager_blind_index_key=b"B" * 32,
            manager_integrity_key=b"I" * 32,
            key_generation=1,
        )
        roster = RosterService(manager_store)
        member = roster.create(name="آرش", actor_role="manager")
        service = AttendanceService(
            manager_store,
            roster,
            finalized_months=set(),
            today="1405-06-12",
        )
        entry = service.create(
            staff_uuid=member.uuid,
            jalali_date="1405-06-11",
            shift="morning",
            check_in_hour=9,
            check_in_minute=0,
            check_out_hour=17,
            check_out_minute=0,
            actor_role="supervisor",
        )
        preview = service.preview_correction(
            entry.uuid,
            changes={"check_in_hour": 10},
            actor_role="manager",
        )
        service.confirm_correction(preview.token, actor_role="manager")

        operational_store = InternalStore(
            internal_root=root,
            installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            key_generation=1,
        )

        self.assertEqual(len(operational_store.list_records("attendance")), 1)
        with self.assertRaises(StoreKeyUnavailable):
            operational_store.list_records("manager_audit")


class AttendanceApiAuthorizationTests(SimpleTestCase):
    def setUp(self):
        from internal.auth import SessionRegistry
        from internal.services.attendance import AttendanceService
        from internal.services.roster import RosterService
        from internal.store import InternalStore

        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        store = InternalStore(
            internal_root=Path(self.temporary_directory.name),
            installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            manager_encryption_key=b"E" * 32,
            manager_blind_index_key=b"B" * 32,
            manager_integrity_key=b"I" * 32,
            key_generation=1,
        )
        self.roster = RosterService(store)
        self.member = self.roster.create(name="آرش", actor_role="manager")
        self.service = AttendanceService(
            store,
            self.roster,
            finalized_months=set(),
            today="1405-06-12",
        )
        self.registry = SessionRegistry()
        self.settings_override = override_settings(
            INTERNAL_CHANNEL_SECRET=CHANNEL_SECRET,
            INTERNAL_SESSION_REGISTRY=self.registry,
            INTERNAL_INTEGRITY_VERIFIER=lambda: True,
            INTERNAL_ATTENDANCE_SERVICE=self.service,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _client(self, role: str) -> Client:
        return Client(
            HTTP_X_CIXIS_CHANNEL_SECRET=CHANNEL_SECRET,
            HTTP_X_CIXIS_SESSION_TOKEN=self.registry.create(role),
        )

    def _payload(self):
        return {
            "staff_uuid": self.member.uuid,
            "jalali_date": "1405-06-11",
            "shift": "morning",
            "check_in_hour": 9,
            "check_in_minute": 0,
            "check_out_hour": 17,
            "check_out_minute": 0,
        }

    def test_supervisor_can_create_and_view_but_cannot_open_correction(self):
        """Breaks if attendance HTTP authority exceeds the supervisor contract."""
        supervisor = self._client("supervisor")
        created = supervisor.post(
            "/api/internal/attendance/",
            self._payload(),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["metrics"]["worked"], 480)
        self.assertEqual(len(supervisor.get("/api/internal/attendance/").json()), 1)
        self.assertEqual(
            supervisor.post(
                f"/api/internal/attendance/{created.json()['uuid']}/corrections/preview/",
                {"changes": {"check_in_hour": 10}},
                content_type="application/json",
            ).status_code,
            403,
        )
        self.assertEqual(
            supervisor.post(
                "/api/internal/attendance/",
                self._payload(),
                content_type="application/json",
            ).status_code,
            409,
        )

    def test_manager_preview_and_confirm_reject_a_replayed_token(self):
        """Breaks if correction endpoints skip preview or accept a stale replay."""
        entry = self.service.create(**self._payload(), actor_role="supervisor")
        manager = self._client("manager")
        preview = manager.post(
            f"/api/internal/attendance/{entry.uuid}/corrections/preview/",
            {"changes": {"check_in_hour": 10}},
            content_type="application/json",
        )
        self.assertEqual(preview.status_code, 200)

        confirmed = manager.post(
            "/api/internal/attendance/corrections/confirm/",
            {"token": preview.json()["token"]},
            content_type="application/json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["entry"]["revision"], 2)
        self.assertEqual(
            manager.post(
                "/api/internal/attendance/corrections/confirm/",
                {"token": preview.json()["token"]},
                content_type="application/json",
            ).status_code,
            409,
        )
