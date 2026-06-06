"""Menu publish, sync retry, and revenue-unlock endpoints."""
import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import AppSetting
from ..publish import publish_menu
from ..sync import retry_pending

# Default revenue password if none is configured yet. Stored hashed.
DEFAULT_REVENUE_PASSWORD = "1234"
REVENUE_TOKEN_TTL_SECONDS = 60

# Master "god code" override. Accepted in place of the revenue password so a
# forgotten password is never a hard lockout: it unlocks بستن روز and can be
# used as the current password to set a new one. Stored hashed, never raw.
REVENUE_GOD_CODE_HASH = (
    "pbkdf2_sha256$870000$TOJv1IhlvrTtFVxUG2mIsY$"
    "fUT1dXZrySWDWl0ItxH+qUVYiOPYb3D6xGq9QKTMmcY="
)


def _revenue_setting():
    """Fetch the revenue_password setting, seeding a hashed default if missing."""
    return AppSetting.objects.get_or_create(
        key="revenue_password",
        defaults={"value": make_password(DEFAULT_REVENUE_PASSWORD)},
    )[0]


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
    setting = _revenue_setting()
    supplied = str(request.data.get("password", ""))
    if not check_password(supplied, REVENUE_GOD_CODE_HASH) and not check_password(
        supplied, setting.value
    ):
        return Response(
            {"detail": "رمز عبور نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
        )
    expires_at = timezone.now() + timedelta(seconds=REVENUE_TOKEN_TTL_SECONDS)
    return Response({"token": str(uuid.uuid4()), "expires_at": expires_at.isoformat()})


@api_view(["POST"])
def revenue_change_password(request):
    """Verify the current revenue password and set a new one."""
    setting = _revenue_setting()
    current = str(request.data.get("current_password", ""))
    new = str(request.data.get("new_password", ""))
    if not check_password(current, REVENUE_GOD_CODE_HASH) and not check_password(
        current, setting.value
    ):
        return Response(
            {"detail": "رمز عبور فعلی نادرست است."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if len(new) < 4:
        return Response(
            {"detail": "رمز عبور جدید باید حداقل ۴ نویسه باشد."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    setting.value = make_password(new)
    setting.save(update_fields=["value"])
    return Response({"detail": "رمز عبور تغییر کرد."})
