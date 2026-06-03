"""Shared domain helpers: order totals, table status, day-business-date."""
from datetime import date

from django.utils import timezone

from .models import Order, Payment


# Order statuses that keep a table "busy" / block its deletion.
BLOCKING_STATUSES = (Order.Status.OPEN, Order.Status.PARTIALLY_PAID)
# Statuses where the order is still the table's "active" (not yet closed) order.
ACTIVE_STATUSES = (
    Order.Status.OPEN,
    Order.Status.PARTIALLY_PAID,
    Order.Status.PAID,
)


def business_today() -> date:
    """Today's business date (local timezone)."""
    return timezone.localdate()


def recalc_order_totals(order: Order) -> Order:
    """Recompute subtotal/paid/remaining from items + payments and update status.

    Does not touch status for closed orders.
    """
    subtotal = sum(item.line_total for item in order.items.all())
    paid = sum(p.amount for p in order.payments.all())
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
