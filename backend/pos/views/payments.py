"""Payments API. Recording a payment recalculates the order's paid/remaining
amounts and advances its status (partially_paid / paid).

A payment may be either:
- an amount payment (``amount``) — settles a flat sum; when it clears the order
  every item is marked fully paid;
- an item split (``items``: ``[{"item_id", "quantity"}]``) — settles specific
  units per item, tracked in ``OrderItem.paid_quantity``. The amount is derived
  server-side from the units actually applied.
"""
from django.db.models import F
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import services
from ..models import Order, Payment
from ..serializers import PaymentSerializer


def _apply_item_split(order: Order, items_payload) -> int:
    """Increment paid_quantity per item and return the derived amount."""
    if not isinstance(items_payload, list):
        raise ValidationError({"items": "فهرست اقلام نامعتبر است."})

    amount = 0
    touched = []
    for entry in items_payload:
        try:
            item_id = int(entry["item_id"])
            qty = int(entry["quantity"])
        except (TypeError, ValueError, KeyError):
            raise ValidationError({"items": "آیتم نامعتبر است."})
        if qty <= 0:
            continue
        item = order.items.filter(id=item_id).first()
        if item is None:
            raise ValidationError({"items": "آیتم در این سفارش یافت نشد."})
        new_paid = min(item.quantity, item.paid_quantity + qty)
        added = new_paid - item.paid_quantity
        if added <= 0:
            continue
        amount += added * item.unit_price_snapshot
        item.paid_quantity = new_paid
        touched.append(item)

    if amount <= 0:
        raise ValidationError({"items": "هیچ آیتمی برای پرداخت انتخاب نشده است."})

    for item in touched:
        item.save(update_fields=["paid_quantity", "updated_at"])
    return amount


def create_payment(order: Order, request) -> Response:
    """Create a Payment for ``order`` from the request body, then recalc totals."""
    if order.status == Order.Status.CLOSED:
        return Response(
            {"detail": "سفارش بسته‌شده قابل پرداخت نیست."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    method = request.data.get("method")
    if method not in Payment.Method.values:
        raise ValidationError({"method": "روش پرداخت نامعتبر است."})

    items_payload = request.data.get("items")
    if items_payload:
        amount = _apply_item_split(order, items_payload)
    else:
        try:
            amount = int(request.data.get("amount"))
        except (TypeError, ValueError):
            raise ValidationError({"amount": "مبلغ نامعتبر است."})
        if amount <= 0:
            raise ValidationError({"amount": "مبلغ باید بزرگ‌تر از صفر باشد."})

    payment = Payment.objects.create(
        order=order,
        amount=amount,
        method=method,
        payer_label=request.data.get("payer_label"),
        note=request.data.get("note"),
    )
    services.recalc_order_totals(order)

    # A cleared order has every unit settled, regardless of how it was paid.
    if order.status == Order.Status.PAID:
        order.items.update(paid_quantity=F("quantity"))

    return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
