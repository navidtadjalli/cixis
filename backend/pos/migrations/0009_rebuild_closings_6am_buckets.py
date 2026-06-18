"""Rebuild DayClosing history from order data using a 6AM business-day boundary.

Earlier dated/per-row closes (and the 0008 backfill) left orders linked to the
wrong closings and the stored snapshots out of sync with reality, so the monthly
report read zeros. This migration throws that away and rebuilds from the orders
themselves:

- Every order is bucketed by its ``created_at`` into a 6AM business day, i.e.
  ``[date 06:00, date+1 06:00)`` local time (Asia/Tehran). An order rung up at
  03:00 belongs to the *previous* calendar day's bucket.
- One DayClosing is created per bucket with totals recomputed from that bucket's
  orders/payments, and every order is linked to its bucket's closing.

Per the rebuild decision, ALL buckets (including the current day) are closed, so
the live preview resets to zero and the cashier starts a fresh register.

Irreversible: the old DayClosing rows (and their original sync_status /
backup_path / synced_at) are discarded. Only Order.day_closing references a
DayClosing (on_delete=SET_NULL), so deleting the old rows is safe.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import migrations

TEHRAN = ZoneInfo("Asia/Tehran")
DAY_START_HOUR = 6

_OPEN = ("open", "partially_paid")
_CLOSED = ("paid", "closed")


def _business_date(created_at):
    """The 6AM-boundary business date for a (tz-aware, UTC) timestamp."""
    local = created_at.astimezone(TEHRAN)
    if local.hour < DAY_START_HOUR:
        local = local - timedelta(days=1)
    return local.date()


def rebuild(apps, schema_editor):
    Order = apps.get_model("pos", "Order")
    Payment = apps.get_model("pos", "Payment")
    DayClosing = apps.get_model("pos", "DayClosing")
    ResourcePurchase = apps.get_model("pos", "ResourcePurchase")

    # Clean slate: SET_NULL clears every order's day_closing as the rows go.
    DayClosing.objects.all().delete()

    orders = list(Order.objects.all())
    if not orders:
        return

    # Bucket orders by their 6AM business date, restamping business_date so it
    # agrees with the bucket the order was actually settled into.
    buckets: dict = {}
    for order in orders:
        bdate = _business_date(order.created_at)
        if order.business_date != bdate:
            order.business_date = bdate
            order.save(update_fields=["business_date"])
        buckets.setdefault(bdate, []).append(order)

    for bdate, group in buckets.items():
        ids = [o.id for o in group]
        payments = Payment.objects.filter(order_id__in=ids)

        def method_total(method):
            return sum(
                payments.filter(method=method).values_list("amount", flat=True)
            )

        cash = method_total("cash")
        card = method_total("card")
        bank = method_total("bank_transfer")
        purchases = sum(
            ResourcePurchase.objects.filter(business_date=bdate).values_list(
                "cost", flat=True
            )
        )

        closing = DayClosing.objects.create(
            business_date=bdate,
            total_sales=cash + card + bank,
            cash_total=cash,
            card_total=card,
            bank_transfer_total=bank,
            orders_count=len(group),
            closed_orders_count=sum(1 for o in group if o.status in _CLOSED),
            open_orders_count=sum(1 for o in group if o.status in _OPEN),
            table_usage_count=len({o.table_id for o in group if o.table_id}),
            purchases_total=purchases,
            sync_status="pending",
        )
        Order.objects.filter(id__in=ids).update(day_closing=closing)


def noop(apps, schema_editor):
    # Irreversible: the original closing snapshots are gone. No-op reverse keeps
    # the migration formally reversible.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0008_backfill_pre_close_orders"),
    ]

    operations = [
        migrations.RunPython(rebuild, noop),
    ]
