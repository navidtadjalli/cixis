from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase


class InternalKeyringTests(SimpleTestCase):
    passwords = {
        "supervisor": "Supervisor-رمز-۱۲۳۴!",
        "manager": "Manager-رمز-۵۶۷۸!",
        "god": "God-رمز-۹۸۷۶!",
    }
    installation_id = "c3e29c3e-e3e6-4a47-bb42-a07269bec0d4"

    def test_argon2id_derivation_requires_the_specified_salt_and_result_sizes(self):
        """Breaks if password envelopes stop deriving a 32-byte Argon2id KEK."""
        from internal.keyring import derive_kek

        password = "Supervisor-رمز-۱۲۳۴!"
        salt = b"s" * 16

        self.assertEqual(derive_kek(password, salt), derive_kek(password, salt))
        self.assertEqual(len(derive_kek(password, salt)), 32)
        with self.assertRaises(ValueError):
            derive_kek(password, b"too-short-salt")

    def test_supervisor_envelope_cannot_expose_the_manager_keyset(self):
        """Breaks if supervisor password starts decrypting manager-only material."""
        from internal.keyring import InternalKeyring, KeyAccessDenied

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )

            supervisor = keyring.unlock("supervisor", self.passwords["supervisor"])
            self.assertEqual(len(supervisor.operational.encryption), 32)
            with self.assertRaises(KeyAccessDenied):
                _ = supervisor.manager

    def test_manager_and_recovery_only_god_paths_can_access_both_keysets(self):
        """Breaks if God material is exposed through ordinary operational unlocks."""
        from internal.keyring import InternalKeyring, KeyAccessDenied

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )

            manager = keyring.unlock("manager", self.passwords["manager"])
            self.assertEqual(len(manager.operational.integrity), 32)
            self.assertEqual(len(manager.manager.blind_index), 32)
            with self.assertRaises(KeyAccessDenied):
                keyring.unlock("god", self.passwords["god"])
            recovery = keyring.unlock_for_recovery("god", self.passwords["god"])
            self.assertEqual(len(recovery.manager.encryption), 32)

    def test_provisioning_is_idempotent_and_envelope_file_has_no_password_plaintext(self):
        """Breaks if retrying first-run replaces keys or writes role passwords to disk."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = InternalKeyring.provision(
                internal_root=root,
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            second = InternalKeyring.provision(
                internal_root=root,
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )

            self.assertEqual(
                first.unlock("manager", self.passwords["manager"]).manager.encryption,
                second.unlock("manager", self.passwords["manager"]).manager.encryption,
            )
            persisted = (root / "keyring.json").read_bytes()
            self.assertNotIn(self.passwords["supervisor"].encode(), persisted)
            self.assertNotIn(self.passwords["manager"].encode(), persisted)

    def test_windows_persistence_skips_posix_only_mode_and_directory_fsync(self):
        """Breaks if keyring writes call POSIX-only APIs on the Windows target."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            with patch(
                "internal.keyring._is_windows", return_value=True, create=True
            ), patch("internal.keyring.os.fchmod", side_effect=AttributeError):
                keyring = InternalKeyring.provision(
                    internal_root=Path(directory),
                    installation_id=self.installation_id,
                    passwords=self.passwords,
                    confirmations=self.passwords,
                )

            self.assertTrue(keyring.path.exists())

    def test_unlocked_keysets_keep_key_generation_separate_from_wrapper_generation(self):
        """Breaks if a password re-wrap changes the generation supplied to records."""
        from internal.keyring import InternalKeyring
        from internal.store import InternalStore

        with TemporaryDirectory() as directory:
            root = Path(directory)
            keyring = InternalKeyring.provision(
                internal_root=root,
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            first = keyring.unlock("supervisor", self.passwords["supervisor"])
            store = InternalStore(
                internal_root=root / "store",
                installation_id=self.installation_id,
                encryption_key=first.operational.encryption,
                blind_index_key=first.operational.blind_index,
                integrity_key=first.operational.integrity,
                key_generation=first.key_generation,
            )
            record = store.create("roster", {"name": "آرش"})
            replacement = "Replacement-رمز-۵۶۷۸!"
            keyring.stage_password_change(
                "supervisor",
                current_password=self.passwords["supervisor"],
                new_password=replacement,
                confirmation=replacement,
                expected_generation=0,
            )
            keyring.activate_staged("supervisor", 1)

            reopened = InternalKeyring.load(root, self.installation_id).unlock(
                "supervisor", replacement
            )
            reopened_store = InternalStore(
                internal_root=root / "store",
                installation_id=self.installation_id,
                encryption_key=reopened.operational.encryption,
                blind_index_key=reopened.operational.blind_index,
                integrity_key=reopened.operational.integrity,
                key_generation=reopened.key_generation,
            )
            self.assertEqual(first.key_generation, 1)
            self.assertEqual(reopened.key_generation, 1)
            self.assertEqual(reopened.wrapper_generation, 1)
            self.assertEqual(reopened_store.read(record.uuid), {"name": "آرش"})

    def test_activation_retains_the_prior_envelope_until_clean_backup(self):
        """Breaks if activation deletes the old valid envelope before retention cleanup."""
        from internal.keyring import InternalKeyring

        with TemporaryDirectory() as directory:
            root = Path(directory)
            keyring = InternalKeyring.provision(
                internal_root=root,
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
            keyring.activate_staged("supervisor", 1)

            restarted = InternalKeyring.load(root, self.installation_id)
            retained = restarted.unlock_retained(
                "supervisor", self.passwords["supervisor"], wrapper_generation=0
            )
            self.assertEqual(retained.wrapper_generation, 0)
            self.assertEqual(restarted.retained_generations("supervisor"), [0])

    def test_generic_retained_unlock_rejects_god_envelopes(self):
        """Breaks if retained God material bypasses recovery-only access rules."""
        from internal.keyring import InternalKeyring, KeyAccessDenied

        with TemporaryDirectory() as directory:
            keyring = InternalKeyring.provision(
                internal_root=Path(directory),
                installation_id=self.installation_id,
                passwords=self.passwords,
                confirmations=self.passwords,
            )
            replacement = "God-new-رمز-۵۶۷۸!"
            keyring.stage_password_change(
                "god",
                current_password=self.passwords["god"],
                new_password=replacement,
                confirmation=replacement,
                expected_generation=0,
            )
            keyring.activate_staged("god", 1)

            with self.assertRaises(KeyAccessDenied):
                keyring.unlock_retained(
                    "god", self.passwords["god"], wrapper_generation=0
                )
