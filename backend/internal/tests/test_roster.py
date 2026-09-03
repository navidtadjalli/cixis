"""Encrypted roster service and authorization contracts."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import Client, SimpleTestCase, override_settings

from internal.tests.test_auth import CHANNEL_SECRET


class RosterDomainTests(SimpleTestCase):
    def setUp(self):
        from internal.store import InternalStore

        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.store = InternalStore(
            internal_root=Path(self.temporary_directory.name),
            installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
            encryption_key=b"e" * 32,
            blind_index_key=b"b" * 32,
            integrity_key=b"i" * 32,
            key_generation=1,
        )

    def test_service_sorts_filters_and_updates_current_names(self):
        """Breaks if roster reads lose stable UUIDs, ordering, filters, or renames."""
        from internal.services.roster import RosterService

        service = RosterService(self.store)
        later = service.create(name="بردیا", actor_role="supervisor", sort_order=2)
        earlier = service.create(name="آرش", actor_role="manager", sort_order=1)
        service.deactivate(later.uuid, actor_role="manager")

        self.assertEqual(
            [member.name for member in service.list_members(status="active")],
            ["آرش"],
        )
        self.assertEqual(
            [member.name for member in service.list_members(status="inactive")],
            ["بردیا"],
        )
        renamed = service.rename(
            earlier.uuid, name="آرش جدید", actor_role="supervisor"
        )
        self.assertEqual(renamed.uuid, earlier.uuid)
        self.assertEqual(renamed.revision, 2)
        self.assertEqual(
            service.get(earlier.uuid).name,
            "آرش جدید",
        )

    def test_manager_only_status_changes_do_not_rewrite_frozen_snapshots(self):
        """Breaks if supervisor changes status or roster edits mutate final reports."""
        from internal.services.roster import RosterPermissionError, RosterService

        service = RosterService(self.store)
        member = service.create(name="آرش", actor_role="supervisor")
        snapshot = self.store.create(
            "finalized_snapshot", {"staff_uuid": member.uuid, "staff_name": "آرش"}
        )

        with self.assertRaises(RosterPermissionError):
            service.deactivate(member.uuid, actor_role="supervisor")
        service.rename(member.uuid, name="نام امروز", actor_role="manager")
        service.deactivate(member.uuid, actor_role="manager")
        service.reactivate(member.uuid, actor_role="manager")

        self.assertTrue(service.get(member.uuid).is_active)
        self.assertEqual(
            self.store.read(snapshot.uuid),
            {"staff_uuid": member.uuid, "staff_name": "آرش"},
        )


class RosterApiAuthorizationTests(SimpleTestCase):
    def setUp(self):
        from internal.auth import SessionRegistry
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
            key_generation=1,
        )
        self.service = RosterService(store)
        self.registry = SessionRegistry()
        self.settings_override = override_settings(
            INTERNAL_CHANNEL_SECRET=CHANNEL_SECRET,
            INTERNAL_SESSION_REGISTRY=self.registry,
            INTERNAL_INTEGRITY_VERIFIER=lambda: True,
            INTERNAL_ROSTER_SERVICE=self.service,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _client(self, role: str) -> Client:
        return Client(
            HTTP_X_CIXIS_CHANNEL_SECRET=CHANNEL_SECRET,
            HTTP_X_CIXIS_SESSION_TOKEN=self.registry.create(role),
        )

    def test_supervisor_can_add_and_rename_but_cannot_change_active_status(self):
        """Breaks if HTTP role rules exceed supervisor roster authority."""
        supervisor = self._client("supervisor")
        created = supervisor.post(
            "/api/internal/roster/",
            {"name": "آرش"},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        member_url = f"/api/internal/roster/{created.json()['uuid']}/"

        renamed = supervisor.patch(
            member_url,
            {"name": "آرش جدید"},
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "آرش جدید")
        self.assertEqual(supervisor.delete(member_url).status_code, 403)
        self.assertEqual(
            supervisor.post(f"{member_url}reactivate/").status_code,
            403,
        )

    def test_manager_can_deactivate_filter_and_reactivate(self):
        """Breaks if manager status changes or active/inactive filters regress."""
        member = self.service.create(name="بردیا", actor_role="manager")
        manager = self._client("manager")
        member_url = f"/api/internal/roster/{member.uuid}/"

        self.assertEqual(manager.delete(member_url).status_code, 204)
        inactive = manager.get("/api/internal/roster/?status=inactive")
        self.assertEqual(
            [row["uuid"] for row in inactive.json()],
            [member.uuid],
        )
        reactivated = manager.post(f"{member_url}reactivate/")
        self.assertEqual(reactivated.status_code, 200)
        self.assertTrue(reactivated.json()["is_active"])
