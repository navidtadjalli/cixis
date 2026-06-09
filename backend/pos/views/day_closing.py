"""Day Closing API: preview today's summary and execute the close."""
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .. import closing, services
from ..models import DayClosing
from ..sync import sync_day_closing_async


@api_view(["GET"])
def preview(request):
    """Return the aggregated closing summary for today (before committing)."""
    today = services.business_today()
    return Response(closing.compute_day_summary(today))


@api_view(["POST"])
def close(request):
    """Execute the day close.

    - Optional ``business_date`` (YYYY-MM-DD) closes a past day; defaults to today.
    - Future date -> 400.
    - Open orders + confirm!=true -> 400 with the unresolved list.
    - Already closed for the date -> 400.
    - Otherwise: snapshot DayClosing, back up the SQLite DB (prune to 7), and
      attempt a non-blocking remote sync.
    """
    today = services.business_today()
    raw_date = request.data.get("business_date")
    if raw_date:
        try:
            target = date.fromisoformat(str(raw_date))
        except ValueError:
            return Response(
                {"detail": "تاریخ نامعتبر است (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target > today:
            return Response(
                {"detail": "نمی‌توان روز آینده را بست."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        target = today

    confirm = str(request.data.get("confirm")).lower() in ("true", "1", "yes")

    if DayClosing.objects.filter(business_date=target).exists():
        return Response(
            {"detail": "این روز قبلاً بسته شده است."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    summary = closing.compute_day_summary(target)
    if summary["unresolved_orders"] and not confirm:
        return Response(
            {
                "detail": "سفارش‌های باز وجود دارد.",
                "unresolved_orders": summary["unresolved_orders"],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    day_closing = closing.create_day_closing(target)
    backup = closing.make_backup()
    sync_day_closing_async(day_closing)
    day_closing.refresh_from_db()

    return Response(
        {
            "id": day_closing.id,
            "business_date": day_closing.business_date.isoformat(),
            "total_sales": day_closing.total_sales,
            "cash_total": day_closing.cash_total,
            "card_total": day_closing.card_total,
            "bank_transfer_total": day_closing.bank_transfer_total,
            "orders_count": day_closing.orders_count,
            "closed_orders_count": day_closing.closed_orders_count,
            "open_orders_count": day_closing.open_orders_count,
            "table_usage_count": day_closing.table_usage_count,
            "purchases_total": day_closing.purchases_total,
            "sync_status": day_closing.sync_status,
            "synced_at": day_closing.synced_at,
            "backup_path": backup.file_path,
        },
        status=status.HTTP_201_CREATED,
    )
