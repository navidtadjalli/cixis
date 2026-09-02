from pathlib import Path
from tempfile import TemporaryDirectory

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
            )
            second = InternalKeyring.provision(
                internal_root=root,
                installation_id=self.installation_id,
                passwords=self.passwords,
            )

            self.assertEqual(
                first.unlock("manager", self.passwords["manager"]).manager.encryption,
                second.unlock("manager", self.passwords["manager"]).manager.encryption,
            )
            persisted = (root / "keyring.json").read_bytes()
            self.assertNotIn(self.passwords["supervisor"].encode(), persisted)
            self.assertNotIn(self.passwords["manager"].encode(), persisted)

