"""Menu publish logic: build a snapshot of the active menu and POST it to the
remote QR-menu server. Every attempt is recorded as a MenuPublishRecord."""
import time

import requests
from django.utils import timezone

from .models import AppSetting, Category, MenuPublishRecord

PUBLISH_TIMEOUT = 8


def _setting(key, default=""):
    obj = AppSetting.objects.filter(key=key).first()
    return obj.value if obj else default


def build_menu_payload() -> dict:
    """Snapshot active categories with their active products (ordered).

    Unavailable products are included but flagged; inactive products are excluded.
    """
    categories = []
    for cat in Category.objects.filter(is_active=True).order_by("sort_order", "id"):
        products = [
            {
                "name": p.name,
                "price": p.price,
                "is_available": p.is_available,
                "sort_order": p.sort_order,
            }
            for p in cat.products.filter(is_active=True).order_by("sort_order", "id")
        ]
        categories.append(
            {"name": cat.name, "sort_order": cat.sort_order, "products": products}
        )

    return {
        "cafe_slug": _setting("cafe_slug", "cixis-cafe"),
        "version": str(int(time.time())),
        "published_at": timezone.now().isoformat(),
        "categories": categories,
    }


def publish_menu() -> dict:
    """Build + POST the menu snapshot. Returns {success, published_at, error?}.

    Network failures never raise — they are captured into the publish record.
    """
    payload = build_menu_payload()
    remote_url = _setting("remote_server_url")
    api_key = _setting("api_key")
    now = timezone.now()

    record = MenuPublishRecord(
        version=payload["version"],
        payload_snapshot=payload,
        status=MenuPublishRecord.Status.PENDING,
    )

    try:
        if not remote_url:
            raise RuntimeError("سرور راه دور پیکربندی نشده است.")
        resp = requests.post(
            f"{remote_url.rstrip('/')}/api/private/menu-snapshots/",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=PUBLISH_TIMEOUT,
        )
        if 200 <= resp.status_code < 300:
            record.status = MenuPublishRecord.Status.SUCCESS
            record.published_at = now
            record.save()
            return {"success": True, "published_at": now.isoformat()}
        raise RuntimeError(f"HTTP {resp.status_code}")
    except Exception as exc:
        record.status = MenuPublishRecord.Status.FAILED
        record.error_message = str(exc)[:500]
        record.save()
        return {"success": False, "published_at": None, "error": str(exc)}
