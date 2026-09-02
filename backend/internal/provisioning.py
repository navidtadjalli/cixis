"""Password-policy and CiXiS generation protocol for internal key envelopes."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from internal.keyring import InternalKeyring, KeyAccessDenied, KeyringStateError


class PasswordValidationError(ValueError):
    """Raised when a proposed password misses the product policy."""


class PasswordAuthenticationError(PermissionError):
    """Raised when the current password does not authenticate."""


class PasswordGenerationConflict(KeyringStateError):
    """Raised when the narrow CiXiS compare-and-swap observes stale state."""


def validate_strong_password(
    candidate: str, *, current: str | None = None, confirmation: str | None = None
) -> bool:
    """Apply the role-password rule without normalizing Unicode or whitespace."""
    return (
        isinstance(candidate, str)
        and len(candidate) >= 12
        and any(character.isalpha() for character in candidate)
        and any(not character.isalpha() for character in candidate)
        and candidate not in {"1234", "0000"}
        and candidate != current
        and (confirmation is None or confirmation == candidate)
    )


def change_password(
    keyring: InternalKeyring,
    *,
    role: str,
    current_password: str,
    new_password: str,
    confirmation: str,
    current_hash: str,
    expected_generation: int,
    verify_password: Callable[[str, str], bool],
    hash_password: Callable[[str], str],
    cas_writer: Callable[..., int | None],
) -> int:
    """Stage, CAS, and activate a self-service password envelope change."""
    if not verify_password(current_password, current_hash):
        raise PasswordAuthenticationError("current CiXiS password is incorrect")
    if not validate_strong_password(
        new_password, current=current_password, confirmation=confirmation
    ):
        raise PasswordValidationError("new password does not meet the strong-password rule")
    try:
        staged_generation = keyring.stage_password_change(
            role,
            current_password=current_password,
            new_password=new_password,
            expected_generation=expected_generation,
        )
    except KeyAccessDenied as error:
        raise PasswordAuthenticationError("current keyring password is incorrect") from error
    committed_generation = cas_writer(
        role,
        expected_hash=current_hash,
        expected_generation=expected_generation,
        replacement_hash=hash_password(new_password),
    )
    if committed_generation != staged_generation:
        raise PasswordGenerationConflict("CiXiS password generation changed concurrently")
    keyring.activate_staged(role, staged_generation)
    return staged_generation


def reset_role_password(
    keyring: InternalKeyring,
    *,
    target_role: str,
    god_password: str,
    new_password: str,
    confirmation: str,
    expected_generation: int,
    current_hash: str | None = None,
    hash_password: Callable[[str], str] | None = None,
    cas_writer: Callable[..., int | None] | None = None,
) -> int:
    """Re-wrap a supervisor/manager envelope with recovery-only God authority.

    The narrow Task 1 CAS writer is mandatory: no wrapper becomes active before
    its matching CiXiS hash/generation update commits.
    """
    if not validate_strong_password(new_password, confirmation=confirmation):
        raise PasswordValidationError("reset password does not meet the strong-password rule")
    if cas_writer is None or current_hash is None or hash_password is None:
        raise ValueError("resets require the current CiXiS hash, hasher, and CAS writer")
    try:
        staged_generation = keyring.stage_password_reset(
            target_role,
            god_password=god_password,
            new_password=new_password,
            expected_generation=expected_generation,
        )
    except KeyAccessDenied as error:
        raise PasswordAuthenticationError("God password is incorrect or unauthorized") from error
    committed_generation = cas_writer(
        target_role,
        expected_hash=current_hash,
        expected_generation=expected_generation,
        replacement_hash=hash_password(new_password),
    )
    if committed_generation != staged_generation:
        raise PasswordGenerationConflict("CiXiS password generation changed concurrently")
    keyring.activate_staged(target_role, staged_generation)
    return staged_generation


def reconcile_generations(
    keyring: InternalKeyring, observed_generations: Mapping[str, int]
) -> list[str]:
    """Expose restart reconciliation without granting callers raw envelope state."""
    return keyring.reconcile_generations(observed_generations)
