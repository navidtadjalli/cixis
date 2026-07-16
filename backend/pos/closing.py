"""Day-closing domain logic: summary aggregation, SQLite backup rotation,
and the remote sync hook (sync body lives in TASK-019's sync module)."""
import shutil
from datetime import date

from django.conf import settings
from django.utils import timezone

from . import services
from .models import (
    BackupRecord,
    DayClosing,
    Order,
    Payment,
    ResourcePurchase,
    ResourceSuggestion,
)


def untouched_preset_ids():
    """Ids of preset event codes nobody has rung anything up on.

    A preset code is a slot, like a table — bulk-created ahead of service so the
    cashier can find a guest by name. Until an item or payment lands on it, it is
    not an order and must stay out of the register: otherwise a hundred unused
    codes each read as an unresolved open order, and the close would settle them
    away, deleting the very list the operator set up.
    """
    return Order.objects.filter(
        is_preset=True, items__isnull=True, payments__isnull=True
    ).values_list("id", flat=True)


def compute_day_summary(business_date: date | None) -> dict:
    """Aggregate totals for the live register or a single historical date.

    ``business_date=None`` is the live register: every order not yet settled
    into a DayClosing, regardless of the calendar date it was rung up. This is
    what the closing preview shows, so a session that crosses midnight (e.g.
    Ramadan 18:00 -> 05:00) keeps all its orders visible until the cashier
    manually closes — nothing disappears or auto-closes at 00:00.

    Passing a concrete ``business_date`` scopes to that date's still-unsettled
    orders; reports use this to surface a specific unclosed historical day.
    Purchases/suggestions always reflect the current business date.
    """
    # Only orders not yet settled into a DayClosing count toward the live
    # summary; closing a day links its orders so the next shift starts at zero.
    orders = Order.objects.filter(day_closing__isnull=True).exclude(
        id__in=untouched_preset_ids()
    )
    payments = Payment.objects.filter(order__day_closing__isnull=True)
    if business_date is not None:
        orders = orders.filter(business_date=business_date)
        payments = payments.filter(order__business_date=business_date)

    purchases_date = business_date or services.business_today()

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

    # "How much have I sold so far" for the supervisor: the booked value of every
    # unsettled order, not just cash collected. For a partially paid order this is
    # the amount already paid plus the value of the items still remaining — i.e.
    # paid_amount + remaining_amount, which sums to the order's full subtotal.
    # Unlike total_sales (cash+card+bank actually received) this counts the
    # unpaid remainder of open orders.
    gross_sales = sum(
        orders.values_list("paid_amount", flat=True)
    ) + sum(orders.values_list("remaining_amount", flat=True))

    purchases_total = sum(
        ResourcePurchase.objects.filter(
            business_date=purchases_date
        ).values_list("cost", flat=True)
    )

    suggestions = list(
        ResourceSuggestion.objects.filter(
            created_for_date=purchases_date
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
        "gross_sales": gross_sales,
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


def create_day_closing(business_date: date, summary: dict | None = None) -> DayClosing:
    """Persist a DayClosing snapshot stamped with ``business_date``.

    ``summary`` lets the caller supply the live (all-unsettled) aggregate so a
    midnight-crossing session is settled into a single snapshot; when omitted
    the snapshot is scoped to ``business_date`` alone.
    """
    if summary is None:
        summary = compute_day_summary(business_date)
    return DayClosing.objects.create(
        business_date=business_date,
        total_sales=summary["total_sales"],
        gross_sales=summary["gross_sales"],
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
