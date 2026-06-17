"""Backfill orphan orders left unsettled by dated (per-row) closes.

The per-row "بستن روز" in the monthly report closes a single business_date and
only settles orders with that exact date. Orders with a NULL or mismatched
business_date were never linked to a DayClosing, so they kept inflating the live
preview forever. This one-off backfill links every still-unsettled order created
before the most recent close to that closing, so the preview stops counting
them.

Cutoff is the last closing's ``created_at`` (the moment the close happened), not
its calendar date: this avoids accidentally settling a fresh order that was rung
up *after* the final close on the same day.
"""
from django.db import migrations


def settle_pre_close_orders(apps, schema_editor):
    Order = apps.get_model("pos", "Order")
    DayClosing = apps.get_model("pos", "DayClosing")

    last = DayClosing.objects.order_by("-created_at", "-id").first()
    if last is None:
        return

    # Attach each orphan to a closing on its OWN business_date so no single day
    # absorbs orders that don't belong to it. ``created_at`` order means the
    # latest close on a date wins when a day was closed more than once.
    closing_by_date = {
        dc.business_date: dc
        for dc in DayClosing.objects.order_by("created_at")
    }

    orphans = Order.objects.filter(
        day_closing__isnull=True,
        created_at__lt=last.created_at,
    )
    for order in orphans:
        order_date = order.business_date or order.created_at.date()
        # Fall back to the last close when the order's own day was never closed
        # (or it has no date); otherwise it would stay stuck in the preview.
        order.day_closing = closing_by_date.get(order_date, last)
        order.save(update_fields=["day_closing"])


def noop(apps, schema_editor):
    # Irreversible: we can't tell which orders this backfill linked vs. ones the
    # close legitimately settled. No-op so the migration is still reversible.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0007_dayclosing_business_date_not_unique"),
    ]

    operations = [
        migrations.RunPython(settle_pre_close_orders, noop),
    ]
