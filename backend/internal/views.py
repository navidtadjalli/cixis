"""Minimal private API boundary. Domain routes arrive in later tasks."""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT, HTTP_401_UNAUTHORIZED, HTTP_429_TOO_MANY_REQUESTS

from internal.auth import (
    SESSION_HEADER,
    authenticate_role,
    channel_is_authenticated,
    get_session_registry,
    get_unlock_throttle,
)
from internal.permissions import require_role


def _unlock_client_key(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def unlock(request):
    if not channel_is_authenticated(request):
        return Response({"detail": "Authentication required."}, status=HTTP_401_UNAUTHORIZED)

    throttle = get_unlock_throttle()
    client_key = _unlock_client_key(request)
    retry_after = throttle.retry_after(client_key)
    if retry_after is not None:
        response = Response({"detail": "Unlock temporarily unavailable."}, status=HTTP_429_TOO_MANY_REQUESTS)
        response["Retry-After"] = str(retry_after)
        return response

    role = request.data.get("role") if isinstance(request.data, dict) else None
    password = request.data.get("password") if isinstance(request.data, dict) else None
    if not authenticate_role(role, password):
        throttle.record_failure(client_key)
        return Response({"detail": "Authentication failed."}, status=HTTP_401_UNAUTHORIZED)

    throttle.clear(client_key)
    token = get_session_registry().create(role)
    return Response({"session_token": token, "role": role})


@api_view(["POST"])
@require_role("supervisor", "manager", "god")
def lock(request):
    get_session_registry().revoke(request.META.get(SESSION_HEADER), terminate=True)
    return Response(status=HTTP_204_NO_CONTENT)


@api_view(["GET"])
@require_role("supervisor", "manager", "god")
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@require_role("supervisor", "manager")
def roster_placeholder(request):
    """Task 4 route contract only; Task 6 supplies roster data and services."""
    return Response({"detail": "Roster service is not available."}, status=501)
