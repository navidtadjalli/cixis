"""Shared domain helpers: order totals, table status, day-business-date."""
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

from .models import Order, Payment


# Order statuses that keep a table "busy" / block its deletion.
BLOCKING_STATUSES = (Order.Status.OPEN, Order.Status.PARTIALLY_PAID)
# Statuses where the order is still the table's "active" order. A fully PAID order
# is settled: the table frees up so the next customers get a fresh order.
ACTIVE_STATUSES = (
    Order.Status.OPEN,
    Order.Status.PARTIALLY_PAID,
)


def business_today() -> date:
    """Current business date, honoring the late-night rollover cutoff.

    A cafe open past midnight (e.g. Ramadan 18:00 -> 05:00) should keep the
    same business date until ``BUSINESS_DAY_START_HOUR`` so the live closing
    register doesn't reset at 00:00. Hours before the cutoff count as the
    previous calendar day.
    """
    now = timezone.localtime()
    start_hour = getattr(settings, "BUSINESS_DAY_START_HOUR", 0)
    if now.hour < start_hour:
        return (now - timedelta(days=1)).date()
    return now.date()


def is_date_closed(business_date) -> bool:
    """True if a DayClosing already exists for the given business date."""
    from .models import DayClosing

    if business_date is None:
        return False
    return DayClosing.objects.filter(business_date=business_date).exists()


def recalc_order_totals(order: Order) -> Order:
    """Recompute subtotal/paid/remaining from items + payments and update status.

    Does not touch status for closed orders.
    """
    # Query directly to bypass any stale prefetch cache on ``order``.
    from .models import OrderItem, Payment

    subtotal = sum(
        OrderItem.objects.filter(order=order).values_list("line_total", flat=True)
    )
    paid = sum(
        Payment.objects.filter(order=order).values_list("amount", flat=True)
    )
    order.subtotal = subtotal
    order.paid_amount = paid
    order.remaining_amount = subtotal - paid

    if order.status != Order.Status.CLOSED:
        if subtotal > 0 and paid >= subtotal:
            order.status = Order.Status.PAID
        elif paid > 0:
            order.status = Order.Status.PARTIALLY_PAID
        else:
            order.status = Order.Status.OPEN
    order.save()
    return order


def active_order_for_table(table) -> Order | None:
    """Latest not-yet-closed order linked to a table, if any."""
    return (
        table.orders.filter(status__in=ACTIVE_STATUSES, closed_at__isnull=True)
        .order_by("-opened_at", "-id")
        .first()
    )


def table_status(order: Order | None) -> str:
    """Derive a table's display status from its active order."""
    if order is None:
        return "empty"
    if order.status == Order.Status.OPEN:
        return "occupied"
    if order.status == Order.Status.PARTIALLY_PAID:
        return "partially_paid"
    if order.status == Order.Status.PAID:
        return "paid"
    return "empty"
