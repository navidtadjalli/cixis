"""Private Electron channel and in-memory role-session authentication."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from typing import Callable

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication


CHANNEL_HEADER = "HTTP_X_CIXIS_CHANNEL_SECRET"
SESSION_HEADER = "HTTP_X_CIXIS_SESSION_TOKEN"
VALID_ROLES = frozenset({"supervisor", "manager", "god"})
IDLE_TIMEOUT = timedelta(minutes=15)
ABSOLUTE_TIMEOUT = timedelta(hours=12)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _decode_256_bit_secret(value: object) -> bytes | None:
    if (
        not isinstance(value, str)
        or not value
        or "=" in value
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for character in value
        )
    ):
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(
            padded.encode("ascii"), altchars=b"-_", validate=True
        )
    except (UnicodeEncodeError, ValueError, binascii.Error):
        return None
    if len(decoded) != 32:
        return None
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    return decoded if hmac.compare_digest(value, canonical) else None


def channel_is_authenticated(request) -> bool:
    """Compare only valid 256-bit Electron channel secrets in constant time."""
    expected = _decode_256_bit_secret(getattr(settings, "INTERNAL_CHANNEL_SECRET", None))
    supplied = _decode_256_bit_secret(request.META.get(CHANNEL_HEADER))
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


@dataclass(frozen=True)
class Session:
    token: str
    role: str
    created_at: datetime
    last_seen_at: datetime


class SessionRegistry:
    """Ephemeral capability tokens. Process replacement clears all state."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = _utcnow,
        shutdown_callback: Callable[[], None] | None = None,
    ):
        self._clock = clock
        self._shutdown_callback = shutdown_callback or (lambda: None)
        self._sessions: dict[str, Session] = {}
        self._shutdown_requested = False

    def create(self, role: str) -> str:
        if role not in VALID_ROLES:
            raise ValueError("unsupported role")
        now = self._clock()
        token = secrets.token_urlsafe(32)
        self._sessions[token] = Session(token, role, now, now)
        return token

    def validate(self, token: object) -> Session | None:
        if not isinstance(token, str):
            return None
        session = self._sessions.get(token)
        if session is None:
            return None
        now = self._clock()
        if now - session.last_seen_at >= IDLE_TIMEOUT or now - session.created_at >= ABSOLUTE_TIMEOUT:
            self.terminate()
            return None
        refreshed = Session(session.token, session.role, session.created_at, now)
        self._sessions[token] = refreshed
        return refreshed

    def revoke(self, token: object, *, terminate: bool = False) -> None:
        if isinstance(token, str):
            self._sessions.pop(token, None)
        if terminate:
            self.terminate()

    def terminate(self) -> None:
        self._sessions.clear()
        if not self._shutdown_requested:
            try:
                self._shutdown_callback()
            except Exception:
                raise ShutdownCallbackFailed("backend shutdown callback failed") from None
            self._shutdown_requested = True


class ShutdownCallbackFailed(RuntimeError):
    """A fail-closed termination request that must be retried by its caller."""


class UnlockThrottle:
    """Small in-memory exponential backoff for failed unlock attempts."""

    def __init__(self, *, clock: Callable[[], datetime] = _utcnow):
        self._clock = clock
        self._attempts: dict[str, tuple[int, datetime]] = {}

    def retry_after(self, key: str) -> int | None:
        attempt = self._attempts.get(key)
        if attempt is None:
            return None
        _, blocked_until = attempt
        remaining = (blocked_until - self._clock()).total_seconds()
        return max(1, int(remaining)) if remaining > 0 else None

    def record_failure(self, key: str) -> None:
        failures = self._attempts.get(key, (0, self._clock()))[0] + 1
        delay = min(2**failures, 300)
        self._attempts[key] = (failures, self._clock() + timedelta(seconds=delay))

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)


_default_registry: SessionRegistry | None = None
_default_throttle = UnlockThrottle()


def get_session_registry() -> SessionRegistry:
    global _default_registry
    configured = getattr(settings, "INTERNAL_SESSION_REGISTRY", None)
    if configured is not None:
        return configured
    if _default_registry is None:
        callback = getattr(settings, "INTERNAL_SHUTDOWN_CALLBACK", None)
        _default_registry = SessionRegistry(
            shutdown_callback=callback if callable(callback) else None
        )
    return _default_registry


def get_unlock_throttle() -> UnlockThrottle:
    configured = getattr(settings, "INTERNAL_UNLOCK_THROTTLE", None)
    return configured if configured is not None else _default_throttle


def authenticate_role(role: object, password: object) -> bool:
    """Authenticate with Task 3 key envelopes, or a wired runtime collaborator."""
    if role not in VALID_ROLES or not isinstance(password, str):
        return False
    authenticator = getattr(settings, "INTERNAL_ROLE_AUTHENTICATOR", None)
    if callable(authenticator):
        try:
            return bool(authenticator(role, password))
        except Exception:
            return False

    keyring_path = getattr(settings, "INTERNAL_KEYRING_PATH", None)
    installation_id = getattr(settings, "INTERNAL_INSTALLATION_ID", None)
    if not keyring_path or not installation_id:
        return False
    try:
        from internal.keyring import InternalKeyring

        keyring = InternalKeyring.load(keyring_path, installation_id)
        if role == "god":
            keyring.unlock_for_recovery(role, password)
        else:
            keyring.unlock(role, password)
    except Exception:
        return False
    return True


def integrity_is_verified() -> bool:
    verifier = getattr(settings, "INTERNAL_INTEGRITY_VERIFIER", None)
    if not callable(verifier):
        return True
    try:
        return bool(verifier())
    except Exception:
        return False


@dataclass(frozen=True)
class SessionPrincipal:
    role: str

    @property
    def is_authenticated(self) -> bool:
        return True


class IntegrityVerificationFailed(exceptions.APIException):
    status_code = 503
    default_detail = "Service unavailable."
    default_code = "service_unavailable"


class ChannelSessionAuthentication(BaseAuthentication):
    """Require both Electron channel secret and an active role capability token."""

    def authenticate(self, request):
        if not channel_is_authenticated(request):
            raise exceptions.AuthenticationFailed("Authentication required.")
        registry = get_session_registry()
        session = registry.validate(request.META.get(SESSION_HEADER))
        if session is None:
            raise exceptions.AuthenticationFailed("Authentication required.")
        if not integrity_is_verified():
            registry.terminate()
            raise IntegrityVerificationFailed()
        return SessionPrincipal(session.role), session

    def authenticate_header(self, request) -> str:
        return "ChannelSession"
