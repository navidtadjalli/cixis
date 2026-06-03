"""Remote synchronization for day-closing records.

Day close always succeeds locally; the remote POST is best-effort. When no remote
server is configured (or it is unreachable) the DayClosing is left ``pending`` and
a SyncRecord is queued for later retry (TASK-019).
"""
import threading

import requests
from django.utils import timezone

from .models import AppSetting, DayClosing, SyncRecord

SYNC_TIMEOUT = 5


def _setting(key, default=""):
    obj = AppSetting.objects.filter(key=key).first()
    return obj.value if obj else default


def _day_closing_payload(dc: DayClosing) -> dict:
    return {
        "cafe_slug": _setting("cafe_slug", "cixis-cafe"),
        "business_date": dc.business_date.isoformat(),
        "total_sales": dc.total_sales,
        "cash_total": dc.cash_total,
        "card_total": dc.card_total,
        "bank_transfer_total": dc.bank_transfer_total,
        "orders_count": dc.orders_count,
        "closed_orders_count": dc.closed_orders_count,
        "open_orders_count": dc.open_orders_count,
        "table_usage_count": dc.table_usage_count,
        "purchases_total": dc.purchases_total,
    }


def _post_day_closing(payload: dict):
    remote_url = _setting("remote_server_url")
    api_key = _setting("api_key")
    if not remote_url:
        raise RuntimeError("سرور راه دور پیکربندی نشده است.")
    return requests.post(
        f"{remote_url.rstrip('/')}/api/private/day-closing-sync/",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=SYNC_TIMEOUT,
    )


def _mark_pending(dc: DayClosing, payload: dict, error: str):
    dc.sync_status = DayClosing.SyncStatus.PENDING
    dc.save(update_fields=["sync_status", "updated_at"])
    SyncRecord.objects.get_or_create(
        sync_type=SyncRecord.SyncType.DAY_CLOSING,
        local_object_id=dc.id,
        defaults={
            "payload_snapshot": payload,
            "status": SyncRecord.Status.PENDING,
            "error_message": error[:500],
        },
    )


def sync_day_closing(dc: DayClosing):
    """Attempt to push a single DayClosing to the remote server (synchronous)."""
    payload = _day_closing_payload(dc)
    try:
        resp = _post_day_closing(payload)
        if 200 <= resp.status_code < 300:
            dc.sync_status = DayClosing.SyncStatus.SYNCED
            dc.synced_at = timezone.now()
            dc.save(update_fields=["sync_status", "synced_at", "updated_at"])
            SyncRecord.objects.filter(
                sync_type=SyncRecord.SyncType.DAY_CLOSING, local_object_id=dc.id
            ).update(status=SyncRecord.Status.SYNCED)
            return
        _mark_pending(dc, payload, f"HTTP {resp.status_code}")
    except Exception as exc:  # network error, timeout, no remote configured
        _mark_pending(dc, payload, str(exc))


def sync_day_closing_async(dc: DayClosing):
    """Kick off the sync attempt without blocking the close response.

    If no remote server is configured we resolve synchronously to ``pending`` so the
    result is deterministic and no idle thread is spawned.
    """
    if not _setting("remote_server_url"):
        _mark_pending(dc, _day_closing_payload(dc), "سرور راه دور پیکربندی نشده است.")
        return
    threading.Thread(target=sync_day_closing, args=(dc,), daemon=True).start()
