"""Menu publish, sync retry, revenue-unlock, and publish-settings endpoints."""
import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import AppSetting
from ..publish import publish_menu
from ..storage import SETTING_KEYS, StorageNotConfigured, storage_config, website_url
from ..sync import retry_pending, sync_enabled

# Default revenue password if none is configured yet. Stored hashed.
DEFAULT_REVENUE_PASSWORD = "1234"
REVENUE_TOKEN_TTL_SECONDS = 60

# Master "god code" override. Accepted in place of the revenue password so a
# forgotten password is never a hard lockout: it unlocks بستن روز and can be
# used as the current password to set a new one. It also gates the publish
# settings, which hold the storage credentials. Stored hashed, never raw.
GOD_CODE_HASH = (
    "pbkdf2_sha256$870000$gOdPBjJb3OXLTp2xpAoAeB$jQ5VH8bk15uw1QeYbYFBb44HDu+ZOGRVKk8OMDUR8lQ="
)

# Blanking these in the form means "keep what is stored", so the operator never
# has to retype a credential just to change the bucket name.
CREDENTIAL_KEYS = frozenset({"s3_access_key", "s3_secret_key"})


def _revenue_setting():
    """Fetch the revenue_password setting, seeding a hashed default if missing."""
    return AppSetting.objects.get_or_create(
        key="revenue_password",
        defaults={"value": make_password(DEFAULT_REVENUE_PASSWORD)},
    )[0]


def check_revenue_password(supplied: str) -> bool:
    """True if ``supplied`` is the revenue password or the god code override."""
    return check_password(supplied, GOD_CODE_HASH) or check_password(
        supplied, _revenue_setting().value
    )


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
    if not check_revenue_password(str(request.data.get("password", ""))):
        return Response(
            {"detail": "رمز عبور نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
        )
    expires_at = timezone.now() + timedelta(seconds=REVENUE_TOKEN_TTL_SECONDS)
    return Response({"token": str(uuid.uuid4()), "expires_at": expires_at.isoformat()})


def _mask(value: str) -> str:
    """Show only the last 4 characters of a stored credential."""
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]


def _publish_settings_state() -> dict:
    """Current publish config, credentials masked, plus the resulting public URL."""
    saved = dict(
        AppSetting.objects.filter(key__in=SETTING_KEYS).values_list("key", "value")
    )
    stored = {key: saved.get(key, "").strip() for key in SETTING_KEYS}
    values = {
        key: (_mask(value) if key in CREDENTIAL_KEYS else value)
        for key, value in stored.items()
    }
    try:
        url = website_url(storage_config())
    except StorageNotConfigured:
        url = ""
    return {
        "settings": values,
        "configured": all(stored.values()),
        "website_url": url,
        "sync_enabled": sync_enabled(),
    }


def _check_god_code(request) -> bool:
    return check_password(str(request.data.get("god_code", "")), GOD_CODE_HASH)


@api_view(["POST"])
def publish_settings_unlock(request):
    """Validate the god code and return the current publish settings."""
    if not _check_god_code(request):
        return Response(
            {"detail": "کد دسترسی نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
        )
    return Response(_publish_settings_state())


@api_view(["POST"])
def publish_settings_save(request):
    """Validate the god code and persist the five storage settings.

    A blank credential field keeps the stored value; blanking bucket, endpoint, or
    region is rejected, since those have no safe fallback.
    """
    if not _check_god_code(request):
        return Response(
            {"detail": "کد دسترسی نادرست است."}, status=status.HTTP_401_UNAUTHORIZED
        )

    incoming = {key: str(request.data.get(key, "")).strip() for key in SETTING_KEYS}

    missing = [
        key
        for key in SETTING_KEYS
        if key not in CREDENTIAL_KEYS and not incoming[key]
    ]
    if missing:
        return Response(
            {"detail": "این فیلدها الزامی هستند: " + ", ".join(missing)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    endpoint = incoming["s3_endpoint_url"]
    if not endpoint.startswith(("http://", "https://")):
        return Response(
            {"detail": "آدرس فضای ذخیره‌سازی باید با http:// یا https:// آغاز شود."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    for key, value in incoming.items():
        if key in CREDENTIAL_KEYS and not value:
            continue  # keep the stored credential
        AppSetting.objects.update_or_create(key=key, defaults={"value": value})

    return Response(_publish_settings_state())


@api_view(["POST"])
def revenue_change_password(request):
    """Verify the current revenue password and set a new one."""
    setting = _revenue_setting()
    new = str(request.data.get("new_password", ""))
    if not check_revenue_password(str(request.data.get("current_password", ""))):
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
