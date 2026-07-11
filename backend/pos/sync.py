"""Remote synchronization for day-closing records.

Day close always succeeds locally; the remote POST is best-effort. When the remote
is configured but unreachable the DayClosing is left ``pending`` and a SyncRecord is
queued for later retry (TASK-019).

Sync is off by default. With ``sync_enabled`` false the close resolves straight to
``local_only`` — a terminal state, so the closing screen shows no retry prompt for
a push that is never going to happen.
"""
import threading

import requests
from django.utils import timezone

from .models import AppSetting, DayClosing, SyncRecord

SYNC_TIMEOUT = 5

TRUTHY = {"1", "true", "yes", "on"}


def _setting(key, default=""):
    obj = AppSetting.objects.filter(key=key).first()
    return obj.value if obj else default


def sync_enabled() -> bool:
    return _setting("sync_enabled", "false").strip().lower() in TRUTHY


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


def _mark_local_only(dc: DayClosing):
    """Resolve the close without queueing anything: nothing will ever retry it."""
    dc.sync_status = DayClosing.SyncStatus.LOCAL_ONLY
    dc.save(update_fields=["sync_status", "updated_at"])


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


def retry_pending() -> dict:
    """Re-attempt every pending/failed SyncRecord. Returns a small result summary."""
    if not sync_enabled():
        return {"synced": 0, "failed": 0, "total": 0}

    records = SyncRecord.objects.filter(
        status__in=[SyncRecord.Status.PENDING, SyncRecord.Status.FAILED]
    )
    synced = failed = 0
    for record in records:
        record.attempt_count += 1
        record.last_attempt_at = timezone.now()
        try:
            if record.sync_type == SyncRecord.SyncType.DAY_CLOSING:
                resp = _post_day_closing(record.payload_snapshot)
            else:
                record.save(update_fields=["attempt_count", "last_attempt_at"])
                continue
            if 200 <= resp.status_code < 300:
                record.status = SyncRecord.Status.SYNCED
                record.error_message = None
                record.save()
                dc = DayClosing.objects.filter(id=record.local_object_id).first()
                if dc:
                    dc.sync_status = DayClosing.SyncStatus.SYNCED
                    dc.synced_at = timezone.now()
                    dc.save(update_fields=["sync_status", "synced_at", "updated_at"])
                synced += 1
            else:
                record.status = SyncRecord.Status.FAILED
                record.error_message = f"HTTP {resp.status_code}"
                record.save()
                failed += 1
        except Exception as exc:
            record.status = SyncRecord.Status.FAILED
            record.error_message = str(exc)[:500]
            record.save()
            failed += 1
    return {"synced": synced, "failed": failed, "total": synced + failed}


def sync_day_closing_async(dc: DayClosing):
    """Kick off the sync attempt without blocking the close response.

    Sync disabled resolves to ``local_only``; enabled-but-unconfigured resolves to
    ``pending``. Both are synchronous so the result is deterministic and no idle
    thread is spawned.
    """
    if not sync_enabled():
        _mark_local_only(dc)
        return
    if not _setting("remote_server_url"):
        _mark_pending(dc, _day_closing_payload(dc), "سرور راه دور پیکربندی نشده است.")
        return
    threading.Thread(target=_threaded_sync, args=(dc.id,), daemon=True).start()


def _threaded_sync(day_closing_id: int):
    """Run a sync in a worker thread, then release the per-thread DB connection.

    Background threads get their own DB connection; closing it avoids leaking
    SQLite handles over the app's lifetime.
    """
    from django.db import connection

    try:
        dc = DayClosing.objects.filter(id=day_closing_id).first()
        if dc:
            sync_day_closing(dc)
    finally:
        connection.close()
