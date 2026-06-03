"""Menu publish, sync retry, and revenue-unlock endpoints."""
import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import AppSetting
from ..publish import publish_menu
from ..sync import retry_pending

# Default revenue password if none is configured yet.
DEFAULT_REVENUE_PASSWORD = "1234"
REVENUE_TOKEN_TTL_SECONDS = 60


@api_view(["POST"])
def menu_publish(request):
    """Build the menu snapshot and push it to the remote QR server."""
    result = publish_menu()
    code = status.HTTP_200_OK if result["success"] else status.HTTP_502_BAD_GATEWAY
    return Response(result, status=code)


@api_view(["POST"])
def sync_retry(request):
    """Retry all pending/failed sync records."""
    return Response(retry_pending())


@api_view(["POST"])
def revenue_unlock(request):
    """Validate the revenue password and return a short-lived reveal token."""
    setting, _ = AppSetting.objects.get_or_create(
        key="revenue_password", defaults={"value": DEFAULT_REVENUE_PASSWORD}
    )
    supplied = str(request.data.get("password", ""))
    if supplied != setting.value:
        return Response(
            {"detail": "رمز عبور نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
        )
    expires_at = timezone.now() + timedelta(seconds=REVENUE_TOKEN_TTL_SECONDS)
    return Response({"token": str(uuid.uuid4()), "expires_at": expires_at.isoformat()})
