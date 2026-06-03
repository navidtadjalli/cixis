"""Day-closing domain logic: summary aggregation, SQLite backup rotation,
and the remote sync hook (sync body lives in TASK-019's sync module)."""
import shutil
from datetime import date

from django.conf import settings
from django.utils import timezone

from .models import (
    BackupRecord,
    DayClosing,
    Order,
    Payment,
    ResourcePurchase,
    ResourceSuggestion,
)


def compute_day_summary(business_date: date) -> dict:
    """Aggregate totals for a single business date (used by preview + close)."""
    orders = Order.objects.filter(business_date=business_date)
    payments = Payment.objects.filter(order__business_date=business_date)

    def method_total(method):
        return sum(
            payments.filter(method=method).values_list("amount", flat=True)
        )

    cash = method_total(Payment.Method.CASH)
    card = method_total(Payment.Method.CARD)
    bank = method_total(Payment.Method.BANK_TRANSFER)

    open_orders = orders.filter(
        status__in=[Order.Status.OPEN, Order.Status.PARTIALLY_PAID]
    )
    closed_orders = orders.filter(
        status__in=[Order.Status.PAID, Order.Status.CLOSED]
    )

    purchases_total = sum(
        ResourcePurchase.objects.filter(business_date=business_date).values_list(
            "cost", flat=True
        )
    )

    suggestions = list(
        ResourceSuggestion.objects.filter(
            created_for_date=business_date
        ).values("resource_name", "reason", "suggested_quantity")
    )
    for s in suggestions:
        s["suggested_quantity"] = float(s["suggested_quantity"])

    unresolved = [
        {
            "id": o.id,
            "order_number": o.order_number,
            "table_name": o.table.name if o.table else o.event_customer_label,
            "status": o.status,
            "remaining_amount": o.remaining_amount,
        }
        for o in open_orders
    ]

    return {
        "total_sales": cash + card + bank,
        "cash_total": cash,
        "card_total": card,
        "bank_transfer_total": bank,
        "orders_count": orders.count(),
        "closed_orders_count": closed_orders.count(),
        "open_orders_count": open_orders.count(),
        "table_usage_count": orders.exclude(table__isnull=True)
        .values("table_id")
        .distinct()
        .count(),
        "purchases_total": purchases_total,
        "resource_suggestions": suggestions,
        "unresolved_orders": unresolved,
    }


def make_backup() -> BackupRecord:
    """Copy the live SQLite DB into the backups dir, then prune to MAX_BACKUPS."""
    backup_dir = settings.BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"cixis-backup-{timestamp}.db"

    db_path = settings.DATABASES["default"]["NAME"]
    shutil.copy2(db_path, dest)

    record = BackupRecord.objects.create(
        file_path=str(dest),
        file_size=dest.stat().st_size,
        app_version=settings.APP_VERSION,
    )
    prune_backups()
    return record


def prune_backups():
    """Keep only the newest MAX_BACKUPS backup files (and their records)."""
    backup_dir = settings.BACKUP_DIR
    files = sorted(
        backup_dir.glob("cixis-backup-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in files[settings.MAX_BACKUPS:]:
        try:
            stale.unlink()
        except OSError:
            pass
        BackupRecord.objects.filter(file_path=str(stale)).delete()


def create_day_closing(business_date: date) -> DayClosing:
    """Persist a DayClosing snapshot for the given date from the live summary."""
    summary = compute_day_summary(business_date)
    return DayClosing.objects.create(
        business_date=business_date,
        total_sales=summary["total_sales"],
        cash_total=summary["cash_total"],
        card_total=summary["card_total"],
        bank_transfer_total=summary["bank_transfer_total"],
        orders_count=summary["orders_count"],
        closed_orders_count=summary["closed_orders_count"],
        open_orders_count=summary["open_orders_count"],
        table_usage_count=summary["table_usage_count"],
        purchases_total=summary["purchases_total"],
        resource_suggestions_snapshot=summary["resource_suggestions"],
        sync_status=DayClosing.SyncStatus.PENDING,
    )
