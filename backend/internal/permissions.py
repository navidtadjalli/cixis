"""DRF role permissions for private internal-domain endpoints."""
from __future__ import annotations

from collections.abc import Callable

from rest_framework.permissions import BasePermission

from internal.auth import ChannelSessionAuthentication


class RolePermission(BasePermission):
    allowed_roles: frozenset[str] = frozenset()

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) in self.allowed_roles
        )


def require_role(*roles: str) -> Callable:
    """Attach strict channel/session auth and the route's explicit role allowlist."""
    allowed_roles = frozenset(roles)

    class RequiredRolePermission(RolePermission):
        pass

    RequiredRolePermission.allowed_roles = allowed_roles

    def decorator(view):
        view.authentication_classes = [ChannelSessionAuthentication]
        view.permission_classes = [RequiredRolePermission]
        return view

    return decorator
