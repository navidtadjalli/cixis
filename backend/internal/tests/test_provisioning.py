from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase


class PasswordPolicyTests(SimpleTestCase):
    def test_provisioning_rejects_passwords_without_explicit_confirmations(self):
        """Breaks if provisioning treats supplied passwords as their own confirmation."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                InternalKeyring.provision(
                    internal_root=Path(directory),
                    installation_id="c3e29c3e-e3e6-4a47-bb42-a07269bec0d4",
                    passwords={
                        "supervisor": "Supervisor-رمز-۱۲۳۴!",
                        "manager": "Manager-رمز-۵۶۷۸!",
                        "god": "God-رمز-۹۸۷۶!",
                    },
                )

    def test_password_policy_requires_exact_confirmation_and_strong_new_value(self):
        """Breaks if weak, unchanged, or mismatched passwords can wrap keysets."""
        from internal.provisioning import validate_strong_password

        current = "Current-رمز-۱۲۳۴!"
        self.assertTrue(
            validate_strong_password(
                "Replacement-رمز-۵۶۷۸!",
                current=current,
                confirmation="Replacement-رمز-۵۶۷۸!",
            )
        )
        self.assertFalse(validate_strong_password("1234", current=current))
        self.assertFalse(validate_strong_password("0000", current=current))
        self.assertFalse(validate_strong_password("onlyletterslong", current=current))
        self.assertFalse(validate_strong_password(current, current=current))
        self.assertFalse(validate_strong_password("Replacement-رمز-۵۶۷۸!", current=current))
        self.assertFalse(
            validate_strong_password(
                "Replacement-رمز-۵۶۷۸!",
                current=current,
                confirmation="replacement-رمز-۵۶۷۸!",
            )
        )


class PasswordGenerationProtocolTests(SimpleTestCase):
    passwords = {
        "supervisor": "Supervisor-رمز-۱۲۳۴!",
        "manager": "Manager-رمز-۵۶۷۸!",
        "god": "God-رمز-۹۸۷۶!",
    }
    installation_id = "c3e29c3e-e3e6-4a47-bb42-a07269bec0d4"

    def _provision(self, directory: str):
        from internal.keyring import InternalKeyring

        return InternalKeyring.provision(
            internal_root=Path(directory),
            installation_id=self.installation_id,
            passwords=self.passwords,
            confirmations=self.passwords,
        )

    def test_failure_before_staged_persistence_keeps_active_envelope_on_disk(self):
        """Breaks if a pre-write failure leaves no usable authorized envelope."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            with patch.object(keyring, "_persist", side_effect=OSError("before write")):
                with self.assertRaises(OSError):
                    keyring.stage_password_change(
                        "supervisor",
                        current_password=self.passwords["supervisor"],
                        new_password="Replacement-رمز-۵۶۷۸!",
                        confirmation="Replacement-رمز-۵۶۷۸!",
                        expected_generation=0,
                    )

            restarted = InternalKeyring.load(Path(directory), self.installation_id)
            self.assertEqual(
                restarted.unlock("supervisor", self.passwords["supervisor"]).wrapper_generation,
                0,
            )

    def test_failure_after_staged_persistence_reconciles_to_a_valid_active_envelope(self):
        """Breaks if a post-write interruption makes the current role unusable."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            real_persist = keyring._persist

            def persist_then_interrupt():
                real_persist()
                raise OSError("after write")

            with patch.object(keyring, "_persist", side_effect=persist_then_interrupt):
                with self.assertRaises(OSError):
                    keyring.stage_password_change(
                        "supervisor",
                        current_password=self.passwords["supervisor"],
                        new_password="Replacement-رمز-۵۶۷۸!",
                        confirmation="Replacement-رمز-۵۶۷۸!",
                        expected_generation=0,
                    )

            restarted = InternalKeyring.load(Path(directory), self.installation_id)
            self.assertEqual(restarted.reconcile_generations({"supervisor": 0}), ["discarded:supervisor"])
            self.assertEqual(
                restarted.unlock("supervisor", self.passwords["supervisor"]).wrapper_generation,
                0,
            )

    def test_hash_failure_after_staging_keeps_one_valid_envelope(self):
        """Breaks if a password-hash failure strands a staged wrapper."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import change_password

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            replacement = "Replacement-رمز-۵۶۷۸!"
            with self.assertRaises(OSError):
                change_password(
                    keyring,
                    role="supervisor",
                    current_password=self.passwords["supervisor"],
                    new_password=replacement,
                    confirmation=replacement,
                    current_hash="old-supervisor-hash",
                    expected_generation=0,
                    verify_password=lambda candidate, stored: candidate == self.passwords["supervisor"],
                    hash_password=lambda password: (_ for _ in ()).throw(OSError("hash failed")),
                    cas_writer=lambda role, **kwargs: 1,
                )

            restarted = InternalKeyring.load(Path(directory), self.installation_id)
            self.assertEqual(restarted.reconcile_generations({"supervisor": 0}), ["discarded:supervisor"])
            self.assertEqual(
                restarted.unlock("supervisor", self.passwords["supervisor"]).wrapper_generation,
                0,
            )

    def test_post_cas_activation_interruption_reconciles_the_new_wrapper(self):
        """Breaks if a crash after CiXiS success loses every authorized wrapper."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import change_password

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            replacement = "Replacement-رمز-۵۶۷۸!"
            with patch.object(keyring, "activate_staged", side_effect=OSError("activate")):
                with self.assertRaises(OSError):
                    change_password(
                        keyring,
                        role="supervisor",
                        current_password=self.passwords["supervisor"],
                        new_password=replacement,
                        confirmation=replacement,
                        current_hash="old-supervisor-hash",
                        expected_generation=0,
                        verify_password=lambda candidate, stored: candidate == self.passwords["supervisor"],
                        hash_password=lambda password: f"hashed:{password}",
                        cas_writer=lambda role, **kwargs: 1,
                    )

            restarted = InternalKeyring.load(Path(directory), self.installation_id)
            self.assertEqual(restarted.reconcile_generations({"supervisor": 1}), ["activated:supervisor"])
            self.assertEqual(restarted.unlock("supervisor", replacement).wrapper_generation, 1)
            self.assertEqual(restarted.retained_generations("supervisor"), [0])

    def test_manager_and_god_self_changes_preserve_role_capabilities(self):
        """Breaks if privileged self-changes lose manager keys or God recovery access."""
        from internal.keyring import InternalKeyring, KeyAccessDenied
        from internal.provisioning import change_password

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            manager_replacement = "Manager-new-رمز-۱۲۳۴!"
            god_replacement = "God-new-رمز-۵۶۷۸!"
            for role, current, replacement in (
                ("manager", self.passwords["manager"], manager_replacement),
                ("god", self.passwords["god"], god_replacement),
            ):
                self.assertEqual(
                    change_password(
                        keyring,
                        role=role,
                        current_password=current,
                        new_password=replacement,
                        confirmation=replacement,
                        current_hash=f"old-{role}-hash",
                        expected_generation=0,
                        verify_password=lambda candidate, stored, current=current: candidate == current,
                        hash_password=lambda password: f"hashed:{password}",
                        cas_writer=lambda role, **kwargs: 1,
                    ),
                    1,
                )

            manager = keyring.unlock("manager", manager_replacement)
            self.assertEqual(manager.wrapper_generation, 1)
            self.assertEqual(len(manager.manager.integrity), 32)
            with self.assertRaises(KeyAccessDenied):
                keyring.unlock("god", god_replacement)
            self.assertEqual(
                keyring.unlock_for_recovery("god", god_replacement).wrapper_generation,
                1,
            )

    def test_god_reset_rewraps_manager_and_retains_generation_n(self):
        """Breaks if God reset cannot retain manager's active N envelope for backup."""
        from internal.provisioning import reset_role_password

        with TemporaryDirectory() as directory:
            keyring = self._provision(directory)
            replacement = "Manager-reset-رمز-۱۲۳۴!"
            self.assertEqual(
                reset_role_password(
                    keyring,
                    target_role="manager",
                    god_password=self.passwords["god"],
                    new_password=replacement,
                    confirmation=replacement,
                    expected_generation=0,
                    current_hash="old-manager-hash",
                    hash_password=lambda password: f"hashed:{password}",
                    cas_writer=lambda role, **kwargs: 1,
                ),
                1,
            )
            self.assertEqual(keyring.unlock("manager", replacement).wrapper_generation, 1)
            self.assertEqual(keyring.retained_generations("manager"), [0])

    def test_change_stages_then_reconciliation_discards_uncommitted_wrapper(self):
        """Breaks if a failed CiXiS CAS can leave the old password unusable."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import PasswordGenerationConflict, change_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            replacement = "Replacement-رمز-۵۶۷۸!"
            with self.assertRaises(PasswordGenerationConflict):
                change_password(
                    keyring,
                    role="supervisor",
                    current_password=self.passwords["supervisor"],
                    new_password=replacement,
                    confirmation=replacement,
                    current_hash="old-supervisor-hash",
                    expected_generation=0,
                    verify_password=lambda candidate, stored: candidate == self.passwords["supervisor"] and stored == "old-supervisor-hash",
                    hash_password=lambda password: f"hashed:{password}",
                    cas_writer=lambda role, **kwargs: None,
                )

            restarted = InternalKeyring.load(Path(directory), self.installation_id)
            self.assertEqual(restarted.reconcile_generations({"supervisor": 0}), ["discarded:supervisor"])
            self.assertEqual(
                restarted.unlock("supervisor", self.passwords["supervisor"]).wrapper_generation,
                0,
            )

    def test_change_activates_only_after_the_matching_cixis_generation_commits(self):
        """Breaks if a matching CAS does not make the new envelope available."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import change_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            replacement = "Replacement-رمز-۵۶۷۸!"
            generation = change_password(
                keyring,
                role="supervisor",
                current_password=self.passwords["supervisor"],
                new_password=replacement,
                confirmation=replacement,
                current_hash="old-supervisor-hash",
                expected_generation=0,
                verify_password=lambda candidate, stored: candidate == self.passwords["supervisor"] and stored == "old-supervisor-hash",
                hash_password=lambda password: f"hashed:{password}",
                cas_writer=lambda role, **kwargs: 1,
            )

            self.assertEqual(generation, 1)
            self.assertEqual(keyring.unlock("supervisor", replacement).wrapper_generation, 1)

    def test_reconciliation_activates_wrapper_after_committed_generation(self):
        """Breaks if a crash after CiXiS CAS strands the new password envelope."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            replacement = "Replacement-رمز-۵۶۷۸!"
            keyring.stage_password_change(
                "supervisor",
                current_password=self.passwords["supervisor"],
                new_password=replacement,
                confirmation=replacement,
                expected_generation=0,
            )

            self.assertEqual(keyring.reconcile_generations({"supervisor": 1}), ["activated:supervisor"])
            self.assertEqual(keyring.unlock("supervisor", replacement).wrapper_generation, 1)

    def test_god_reset_rewraps_supervisor_without_its_current_password(self):
        """Breaks if recovery cannot restore a forgotten role with God authority."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import reset_role_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            reset = "Reset-رمز-۱۲۳۴!"
            generation = reset_role_password(
                keyring,
                target_role="supervisor",
                god_password=self.passwords["god"],
                new_password=reset,
                confirmation=reset,
                expected_generation=0,
                current_hash="old-supervisor-hash",
                hash_password=lambda password: f"hashed:{password}",
                cas_writer=lambda role, **kwargs: 1
            )

            self.assertEqual(generation, 1)
            self.assertEqual(keyring.unlock("supervisor", reset).wrapper_generation, 1)

    def test_god_reset_requires_the_real_cixis_cas_collaborator(self):
        """Breaks if recovery can report success without synchronizing CiXiS."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import reset_role_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )

            with self.assertRaises(ValueError):
                reset_role_password(
                    keyring,
                    target_role="supervisor",
                    god_password=self.passwords["god"],
                    new_password="Reset-رمز-۱۲۳۴!",
                    confirmation="Reset-رمز-۱۲۳۴!",
                    expected_generation=0,
                )
            self.assertEqual(keyring.reconcile_generations({}), [])
