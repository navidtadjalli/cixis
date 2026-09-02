"""Role-separated, password-wrapped internal encryption keysets."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import tempfile
from typing import Any, Mapping
from uuid import uuid4

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag

from internal.crypto import EncryptedPayload, decrypt_payload, encrypt_payload


FORMAT_VERSION = 1
KEYRING_FILENAME = "keyring.json"
ROLES = frozenset(("supervisor", "manager", "god"))
KDF_PARAMS = {
    "memory_cost": 65536,
    "time_cost": 3,
    "parallelism": 1,
    "hash_len": 32,
}
KDF_SALT_BYTES = 16


class KeyAccessDenied(PermissionError):
    """Raised when a role tries to access unavailable key material."""


class KeyringStateError(ValueError):
    """Raised when keyring state is malformed or cannot be reconciled safely."""


@dataclass(frozen=True)
class DomainKeyset:
    encryption: bytes
    blind_index: bytes
    integrity: bytes


@dataclass(frozen=True)
class UnlockedKeysets:
    """Decrypted material returned only by a role-authorized unlock method."""

    key_generation: int
    wrapper_generation: int
    operational: DomainKeyset
    _manager: DomainKeyset | None

    @property
    def manager(self) -> DomainKeyset:
        if self._manager is None:
            raise KeyAccessDenied("this role cannot access the manager keyset")
        return self._manager


def derive_kek(password: str, salt: bytes) -> bytes:
    """Derive one 256-bit AES key-encryption key with Argon2id."""
    if len(salt) != KDF_SALT_BYTES:
        raise ValueError("Argon2id envelope salts must be exactly 16 bytes")
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        type=Type.ID,
        **KDF_PARAMS,
    )


class InternalKeyring:
    """Own versioned password envelopes below the authoritative internal root."""

    def __init__(self, *, internal_root: Path, installation_id: str, state: dict[str, Any]):
        self.internal_root = Path(internal_root).resolve()
        self.installation_id = installation_id
        self._state = state
        self._validate_state()

    @property
    def path(self) -> Path:
        return self.internal_root / KEYRING_FILENAME

    @classmethod
    def provision(
        cls,
        *,
        internal_root: Path,
        installation_id: str,
        passwords: Mapping[str, str],
        confirmations: Mapping[str, str] | None = None,
        password_generations: Mapping[str, int] | None = None,
    ) -> "InternalKeyring":
        """Create independent domain keysets once; retries verify and reuse them."""
        from internal.provisioning import validate_strong_password

        root = Path(internal_root).resolve()
        path = root / KEYRING_FILENAME
        if set(passwords) != ROLES:
            raise ValueError("provisioning requires supervisor, manager, and God passwords")
        if confirmations is None or set(confirmations) != ROLES:
            raise ValueError("provisioning requires explicit confirmation for every role")
        if path.exists():
            existing = cls.load(root, installation_id)
            for role in ROLES:
                existing._unlock(role, passwords[role], allow_god=True)
            return existing
        for role, password in passwords.items():
            if not validate_strong_password(password, confirmation=confirmations[role]):
                raise ValueError("provisioning password does not meet the strong-password rule")
        generations = password_generations or {}
        if set(generations) - ROLES:
            raise ValueError("password generations contain an unknown role")
        if any(not isinstance(generation, int) or generation < 0 for generation in generations.values()):
            raise ValueError("password generations must be non-negative integers")

        operational = _new_keyset()
        manager = _new_keyset()
        key_generation = 1
        envelopes = {
            role: _make_envelope(
                role=role,
                password=passwords[role],
                installation_id=installation_id,
                wrapper_generation=generations.get(role, 0),
                key_generation=key_generation,
                operational=operational,
                manager=manager if role in {"manager", "god"} else None,
            )
            for role in ROLES
        }
        keyring = cls(
            internal_root=root,
            installation_id=installation_id,
            state={
                "format_version": FORMAT_VERSION,
                "installation_id": installation_id,
                "key_generation": key_generation,
                "envelopes": envelopes,
                "staged": {},
                "retained": {role: [] for role in ROLES},
            },
        )
        keyring._persist()
        return keyring

    @classmethod
    def load(cls, internal_root: Path, installation_id: str) -> "InternalKeyring":
        root = Path(internal_root).resolve()
        path = root / KEYRING_FILENAME
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise KeyringStateError("cannot load the internal keyring") from error
        if state.get("installation_id") != installation_id:
            raise KeyringStateError("keyring belongs to a different CiXiS installation")
        return cls(internal_root=root, installation_id=installation_id, state=state)

    def unlock(self, role: str, password: str) -> UnlockedKeysets:
        """Unlock an operational role; recovery credentials are never operational."""
        if role == "god":
            raise KeyAccessDenied("God envelopes are restricted to recovery services")
        return self._unlock(role, password, allow_god=False)

    def unlock_for_recovery(self, role: str, password: str) -> UnlockedKeysets:
        """Unlock God material only for password reset/recovery tooling."""
        if role != "god":
            raise KeyAccessDenied("only God can use the recovery key envelope")
        return self._unlock(role, password, allow_god=True)

    def stage_password_change(
        self,
        role: str,
        *,
        current_password: str,
        new_password: str,
        confirmation: str,
        expected_generation: int,
    ) -> int:
        """Write and fsync an N+1 envelope while retaining the active envelope."""
        if role == "god":
            unlocked = self.unlock_for_recovery(role, current_password)
        else:
            unlocked = self.unlock(role, current_password)
        return self._stage_unlocked(
            role=role,
            unlocked=unlocked,
            new_password=new_password,
            confirmation=confirmation,
            expected_generation=expected_generation,
        )

    def stage_password_reset(
        self,
        target_role: str,
        *,
        god_password: str,
        new_password: str,
        confirmation: str,
        expected_generation: int,
    ) -> int:
        """Use recovery-only God material to stage a forgotten role's replacement."""
        if target_role not in {"supervisor", "manager"}:
            raise KeyAccessDenied("God may reset only supervisor or manager passwords")
        recovery = self.unlock_for_recovery("god", god_password)
        unlocked = UnlockedKeysets(
            key_generation=self._state["key_generation"],
            wrapper_generation=self._state["envelopes"][target_role]["wrapper_generation"],
            operational=recovery.operational,
            _manager=recovery.manager if target_role == "manager" else None,
        )
        return self._stage_unlocked(
            role=target_role,
            unlocked=unlocked,
            new_password=new_password,
            confirmation=confirmation,
            expected_generation=expected_generation,
        )

    def activate_staged(self, role: str, generation: int) -> None:
        """Make a CAS-committed staged wrapper active after its CiXiS update."""
        staged = self._state["staged"].get(role)
        if staged is None or staged["wrapper_generation"] != generation:
            raise KeyringStateError("no matching staged envelope to activate")
        self._activate_envelope(role, staged)
        del self._state["staged"][role]
        self._persist()

    def retained_generations(self, role: str) -> list[int]:
        """Return wrappers retained until a clean backup can retire them."""
        if role not in ROLES:
            raise KeyAccessDenied("unsupported keyring role")
        return [envelope["wrapper_generation"] for envelope in self._state["retained"][role]]

    def unlock_retained(
        self, role: str, password: str, *, wrapper_generation: int
    ) -> UnlockedKeysets:
        """Authenticate a retained envelope without exposing raw keyring state."""
        if role not in ROLES or role == "god":
            raise KeyAccessDenied("unsupported keyring role")
        for envelope in self._state["retained"][role]:
            if envelope["wrapper_generation"] == wrapper_generation:
                return _decrypt_envelope(
                    envelope=envelope,
                    role=role,
                    password=password,
                    installation_id=self.installation_id,
                )
        raise KeyAccessDenied("requested retained key envelope is unavailable")

    def reconcile_generations(self, observed_generations: Mapping[str, int]) -> list[str]:
        """Finish committed staging or discard pre-CAS staging after restart."""
        actions: list[str] = []
        for role, staged in tuple(self._state["staged"].items()):
            try:
                observed = observed_generations[role]
            except KeyError as error:
                raise KeyringStateError(f"missing observed generation for {role}") from error
            active_generation = self._state["envelopes"][role]["wrapper_generation"]
            staged_generation = staged["wrapper_generation"]
            if observed == staged_generation:
                self._activate_envelope(role, staged)
                del self._state["staged"][role]
                actions.append(f"activated:{role}")
            elif observed == active_generation:
                del self._state["staged"][role]
                actions.append(f"discarded:{role}")
            else:
                raise KeyringStateError(f"cannot reconcile {role} password generation")
        if actions:
            self._persist()
        return actions

    def _activate_envelope(self, role: str, envelope: dict[str, Any]) -> None:
        retained = self._state["retained"][role]
        retained.append(self._state["envelopes"][role])
        self._state["retained"][role] = retained[-1:]
        self._state["envelopes"][role] = envelope

    def _stage_unlocked(
        self,
        *,
        role: str,
        unlocked: UnlockedKeysets,
        new_password: str,
        confirmation: str,
        expected_generation: int,
    ) -> int:
        from internal.provisioning import validate_strong_password

        if role not in ROLES:
            raise KeyAccessDenied("unsupported keyring role")
        if not validate_strong_password(new_password, confirmation=confirmation):
            raise ValueError("replacement password does not meet the strong-password rule")
        active = self._state["envelopes"][role]
        if active["wrapper_generation"] != expected_generation:
            raise KeyringStateError("active envelope generation is stale")
        if role in self._state["staged"]:
            raise KeyringStateError("a password wrapper is already staged for this role")
        next_generation = expected_generation + 1
        self._state["staged"][role] = _make_envelope(
            role=role,
            password=new_password,
            installation_id=self.installation_id,
            wrapper_generation=next_generation,
            key_generation=self._state["key_generation"],
            operational=unlocked.operational,
            manager=unlocked._manager,
        )
        self._persist()
        return next_generation

    def _unlock(self, role: str, password: str, *, allow_god: bool) -> UnlockedKeysets:
        if role not in ROLES or (role == "god" and not allow_god):
            raise KeyAccessDenied("role is not authorized for this key envelope")
        return _decrypt_envelope(
            envelope=self._state["envelopes"][role],
            role=role,
            password=password,
            installation_id=self.installation_id,
        )

    def _validate_state(self) -> None:
        if self._state.get("format_version") != FORMAT_VERSION:
            raise KeyringStateError("unsupported internal keyring format")
        if not isinstance(self._state.get("key_generation"), int) or self._state["key_generation"] < 1:
            raise KeyringStateError("keyring has an invalid key generation")
        if set(self._state.get("envelopes", {})) != ROLES:
            raise KeyringStateError("keyring does not contain every role envelope")
        if not isinstance(self._state.get("staged"), dict):
            raise KeyringStateError("keyring staged envelope state is invalid")
        self._state.setdefault("retained", {role: [] for role in ROLES})
        if set(self._state["retained"]) != ROLES:
            raise KeyringStateError("keyring retained envelope state is invalid")
        for role, envelope in self._state["envelopes"].items():
            _validate_envelope_metadata(envelope, role, self.installation_id)
        for role, envelope in self._state["staged"].items():
            _validate_envelope_metadata(envelope, role, self.installation_id)
        for role, retained in self._state["retained"].items():
            if not isinstance(retained, list) or len(retained) > 1:
                raise KeyringStateError("keyring retained envelope count is invalid")
            for envelope in retained:
                _validate_envelope_metadata(envelope, role, self.installation_id)

    def _persist(self) -> None:
        self.internal_root.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            self._state, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".keyring-", dir=self.internal_root
        )
        try:
            if not _is_windows():
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as temporary:
                descriptor = -1
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.path)
            if not _is_windows():
                _fsync_directory(self.internal_root)
        finally:
            if descriptor != -1:
                os.close(descriptor)
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def _new_keyset() -> DomainKeyset:
    return DomainKeyset(
        encryption=secrets.token_bytes(32),
        blind_index=secrets.token_bytes(32),
        integrity=secrets.token_bytes(32),
    )


def _make_envelope(
    *,
    role: str,
    password: str,
    installation_id: str,
    wrapper_generation: int,
    key_generation: int,
    operational: DomainKeyset,
    manager: DomainKeyset | None,
) -> dict[str, Any]:
    envelope_id = str(uuid4())
    salt = secrets.token_bytes(KDF_SALT_BYTES)
    metadata = {
        "format_version": FORMAT_VERSION,
        "installation_id": installation_id,
        "role": role,
        "envelope_id": envelope_id,
        "wrapper_generation": wrapper_generation,
        "key_generation": key_generation,
    }
    encrypted = encrypt_payload(
        key=derive_kek(password, salt),
        aad=_envelope_aad(metadata),
        payload={
            "key_generation": key_generation,
            "operational": _encode_keyset(operational),
            "manager": _encode_keyset(manager) if manager is not None else None,
        },
    )
    return {
        **metadata,
        "kdf": {"algorithm": "argon2id", **KDF_PARAMS},
        "salt": _encode(salt),
        "nonce": _encode(encrypted.nonce),
        "ciphertext": _encode(encrypted.ciphertext),
    }


def _decrypt_envelope(
    *, envelope: Mapping[str, Any], role: str, password: str, installation_id: str
) -> UnlockedKeysets:
    metadata = {
        field: envelope.get(field)
        for field in (
            "format_version",
            "installation_id",
            "role",
            "envelope_id",
            "wrapper_generation",
            "key_generation",
        )
    }
    if (
        metadata["format_version"] != FORMAT_VERSION
        or metadata["installation_id"] != installation_id
        or metadata["role"] != role
        or envelope.get("kdf") != {"algorithm": "argon2id", **KDF_PARAMS}
    ):
        raise KeyringStateError("key envelope metadata does not match this role")
    try:
        decrypted = decrypt_payload(
            key=derive_kek(password, _decode(envelope["salt"])),
            aad=_envelope_aad(metadata),
            encrypted=EncryptedPayload(
                nonce=_decode(envelope["nonce"]), ciphertext=_decode(envelope["ciphertext"])
            ),
        )
    except (KeyError, TypeError, ValueError, InvalidTag) as error:
        raise KeyAccessDenied("password cannot unlock this key envelope") from error
    if decrypted.get("key_generation") != metadata["key_generation"]:
        raise KeyringStateError("key envelope generation does not match its payload")
    operational = _decode_keyset(decrypted.get("operational"))
    manager_payload = decrypted.get("manager")
    manager = _decode_keyset(manager_payload) if manager_payload is not None else None
    if role == "supervisor" and manager is not None:
        raise KeyringStateError("supervisor envelope contains manager key material")
    if role in {"manager", "god"} and manager is None:
        raise KeyringStateError("privileged envelope lacks manager key material")
    return UnlockedKeysets(
        key_generation=metadata["key_generation"],
        wrapper_generation=metadata["wrapper_generation"],
        operational=operational,
        _manager=manager,
    )


def _validate_envelope_metadata(
    envelope: Mapping[str, Any], role: str, installation_id: str
) -> None:
    metadata = {
        field: envelope.get(field)
        for field in (
            "format_version",
            "installation_id",
            "role",
            "envelope_id",
            "wrapper_generation",
            "key_generation",
        )
    }
    if (
        metadata["format_version"] != FORMAT_VERSION
        or metadata["installation_id"] != installation_id
        or metadata["role"] != role
        or not isinstance(metadata["envelope_id"], str)
        or not isinstance(metadata["wrapper_generation"], int)
        or not isinstance(metadata["key_generation"], int)
        or metadata["wrapper_generation"] < 0
        or metadata["key_generation"] < 1
        or envelope.get("kdf") != {"algorithm": "argon2id", **KDF_PARAMS}
    ):
        raise KeyringStateError("key envelope metadata does not match this role")
    try:
        if len(_decode(envelope["salt"])) != KDF_SALT_BYTES:
            raise ValueError
        if len(_decode(envelope["nonce"])) != 12 or len(_decode(envelope["ciphertext"])) < 16:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise KeyringStateError("key envelope binary metadata is invalid") from error


def _is_windows() -> bool:
    return os.name == "nt"


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _envelope_aad(metadata: Mapping[str, Any]) -> bytes:
    return json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _encode_keyset(keyset: DomainKeyset) -> dict[str, str]:
    return {
        "encryption": _encode(keyset.encryption),
        "blind_index": _encode(keyset.blind_index),
        "integrity": _encode(keyset.integrity),
    }


def _decode_keyset(value: Any) -> DomainKeyset:
    if not isinstance(value, dict) or set(value) != {"encryption", "blind_index", "integrity"}:
        raise KeyringStateError("key envelope contains an invalid domain keyset")
    keyset = DomainKeyset(**{name: _decode(value[name]) for name in value})
    if any(len(key) != 32 for key in (keyset.encryption, keyset.blind_index, keyset.integrity)):
        raise KeyringStateError("key envelope contains a non-256-bit domain key")
    return keyset


def _encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("key envelope binary field is invalid")
    return base64.b64decode(value.encode("ascii"), validate=True)
