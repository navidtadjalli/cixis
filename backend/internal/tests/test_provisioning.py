from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase


class PasswordPolicyTests(SimpleTestCase):
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

    def test_change_stages_then_reconciliation_discards_uncommitted_wrapper(self):
        """Breaks if a failed CiXiS CAS can leave the old password unusable."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import PasswordGenerationConflict, change_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
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
                restarted.unlock("supervisor", self.passwords["supervisor"]).generation,
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
            self.assertEqual(keyring.unlock("supervisor", replacement).generation, 1)

    def test_reconciliation_activates_wrapper_after_committed_generation(self):
        """Breaks if a crash after CiXiS CAS strands the new password envelope."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
            )
            replacement = "Replacement-رمز-۵۶۷۸!"
            keyring.stage_password_change(
                "supervisor",
                current_password=self.passwords["supervisor"],
                new_password=replacement,
                expected_generation=0,
            )

            self.assertEqual(keyring.reconcile_generations({"supervisor": 1}), ["activated:supervisor"])
            self.assertEqual(keyring.unlock("supervisor", replacement).generation, 1)

    def test_god_reset_rewraps_supervisor_without_its_current_password(self):
        """Breaks if recovery cannot restore a forgotten role with God authority."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import reset_role_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
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
            self.assertEqual(keyring.unlock("supervisor", reset).generation, 1)

    def test_god_reset_requires_the_real_cixis_cas_collaborator(self):
        """Breaks if recovery can report success without synchronizing CiXiS."""
        from internal.keyring import InternalKeyring
        from internal.provisioning import reset_role_password

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
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
