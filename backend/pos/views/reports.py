"""Reports: monthly DayClosing rollup and an ad-hoc date-range order report."""
from datetime import date

from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import services
from ..models import DayClosing, Order, OrderItem


@api_view(["GET"])
def monthly(request):
    """Aggregate DayClosing rows for ?year=&month= (defaults to current month)."""
    today = services.business_today()
    year = int(request.query_params.get("year", today.year))
    month = int(request.query_params.get("month", today.month))

    qs = DayClosing.objects.filter(
        business_date__year=year, business_date__month=month
    ).order_by("business_date")

    totals = qs.aggregate(
        total_sales=Sum("total_sales"),
        cash_total=Sum("cash_total"),
        card_total=Sum("card_total"),
        bank_transfer_total=Sum("bank_transfer_total"),
        purchases_total=Sum("purchases_total"),
    )

    daily = [
        {
            "business_date": dc.business_date.isoformat(),
            "total_sales": dc.total_sales,
            "cash_total": dc.cash_total,
            "card_total": dc.card_total,
            "bank_transfer_total": dc.bank_transfer_total,
            "orders_count": dc.orders_count,
        }
        for dc in qs
    ]

    return Response(
        {
            "year": year,
            "month": month,
            "total_sales": totals["total_sales"] or 0,
            "cash_total": totals["cash_total"] or 0,
            "card_total": totals["card_total"] or 0,
            "bank_transfer_total": totals["bank_transfer_total"] or 0,
            "purchases_total": totals["purchases_total"] or 0,
            "days_count": qs.count(),
            "daily": daily,
        }
    )


def _parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({field: "تاریخ نامعتبر است (YYYY-MM-DD)."})


@api_view(["GET"])
def date_range(request):
    """Aggregate orders + ordered items between ?from= and ?to= (inclusive).

    Returns the order count/total for the range plus, per product, the summed
    quantity ordered and the summed amount of those items.
    """
    today = services.business_today()
    from_date = _parse_date(request.query_params.get("from", today.isoformat()), "from")
    to_date = _parse_date(request.query_params.get("to", today.isoformat()), "to")
    if from_date > to_date:
        raise ValidationError({"from": "تاریخ شروع بعد از تاریخ پایان است."})

    orders = Order.objects.filter(
        business_date__gte=from_date, business_date__lte=to_date
    )
    order_totals = orders.aggregate(total=Sum("subtotal"))

    rows = (
        OrderItem.objects.filter(
            order__business_date__gte=from_date,
            order__business_date__lte=to_date,
        )
        .values("product_name_snapshot")
        .annotate(quantity=Sum("quantity"), amount=Sum("line_total"))
        .order_by("-amount")
    )
    items = [
        {
            "product_name": row["product_name_snapshot"],
            "quantity": row["quantity"] or 0,
            "amount": row["amount"] or 0,
        }
        for row in rows
    ]

    return Response(
        {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "orders_count": orders.count(),
            "orders_total": order_totals["total"] or 0,
            "items": items,
            "items_quantity_total": sum(i["quantity"] for i in items),
            "items_amount_total": sum(i["amount"] for i in items),
        }
    )
