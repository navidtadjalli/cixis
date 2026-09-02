from django.test import SimpleTestCase


class AuthenticatedEncryptionTests(SimpleTestCase):
    def test_round_trip_uses_a_fresh_96_bit_nonce_and_hides_persian_plaintext(self):
        from internal.crypto import decrypt_payload, encrypt_payload

        key = bytes(range(32))
        aad = b"cixis-internal|v1|record-uuid|roster|1"
        plaintext = {"name": "آرش", "month": "1405-06"}

        encrypted = encrypt_payload(key=key, aad=aad, payload=plaintext)

        self.assertEqual(len(encrypted.nonce), 12)
        self.assertNotIn("آرش".encode(), encrypted.ciphertext)
        self.assertEqual(
            decrypt_payload(key=key, aad=aad, encrypted=encrypted), plaintext
        )

    def test_rejects_ciphertext_changed_after_encryption(self):
        from cryptography.exceptions import InvalidTag

        from internal.crypto import EncryptedPayload, decrypt_payload, encrypt_payload

        key = bytes(range(32))
        aad = b"cixis-internal|v1|record-uuid|roster|1"
        encrypted = encrypt_payload(key=key, aad=aad, payload={"name": "آرش"})
        tampered = EncryptedPayload(
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext[:-1] + b"x",
        )

        with self.assertRaises(InvalidTag):
            decrypt_payload(key=key, aad=aad, encrypted=tampered)
