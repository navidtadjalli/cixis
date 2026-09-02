"""Version-one authenticated encryption helpers for internal payloads."""
from dataclasses import dataclass
import json
import secrets
from collections.abc import Mapping
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_BYTES = 32
NONCE_BYTES = 12


@dataclass(frozen=True)
class EncryptedPayload:
    """AEAD ciphertext paired with its unique per-key nonce."""

    nonce: bytes
    ciphertext: bytes


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_key(key: bytes) -> None:
    if len(key) != KEY_BYTES:
        raise ValueError("internal encryption keys must be 256 bits")


def encrypt_payload(
    *, key: bytes, aad: bytes, payload: Mapping[str, Any]
) -> EncryptedPayload:
    """Encrypt one canonical JSON payload with a freshly generated GCM nonce."""
    _validate_key(key)
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, _canonical_json(payload), aad)
    return EncryptedPayload(nonce=nonce, ciphertext=ciphertext)


def decrypt_payload(
    *, key: bytes, aad: bytes, encrypted: EncryptedPayload
) -> dict[str, Any]:
    """Authenticate/decrypt a payload; callers receive ``InvalidTag`` on tamper."""
    _validate_key(key)
    plaintext = AESGCM(key).decrypt(encrypted.nonce, encrypted.ciphertext, aad)
    value = json.loads(plaintext.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("internal encrypted payload must be a JSON object")
    return value
