"""Payments API. Recording a payment recalculates the order's paid/remaining
amounts and advances its status (partially_paid / paid)."""
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import services
from ..models import Order, Payment
from ..serializers import PaymentSerializer


def create_payment(order: Order, request) -> Response:
    """Create a Payment for ``order`` from the request body, then recalc totals."""
    if order.status == Order.Status.CLOSED:
        return Response(
            {"detail": "سفارش بسته‌شده قابل پرداخت نیست."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = int(request.data.get("amount"))
    except (TypeError, ValueError):
        raise ValidationError({"amount": "مبلغ نامعتبر است."})
    if amount <= 0:
        raise ValidationError({"amount": "مبلغ باید بزرگ‌تر از صفر باشد."})

    method = request.data.get("method")
    if method not in Payment.Method.values:
        raise ValidationError({"method": "روش پرداخت نامعتبر است."})

    payment = Payment.objects.create(
        order=order,
        amount=amount,
        method=method,
        payer_label=request.data.get("payer_label"),
        note=request.data.get("note"),
    )
    services.recalc_order_totals(order)
    return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
