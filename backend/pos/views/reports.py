"""Reports: monthly DayClosing rollup and an ad-hoc date-range order report."""
from datetime import date

from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import closing, services
from ..models import DayClosing, Order, OrderItem

# Keys summed across daily rows to build the month totals.
_MONTH_TOTAL_KEYS = (
    "total_sales",
    "cash_total",
    "card_total",
    "bank_transfer_total",
    "purchases_total",
)


@api_view(["GET"])
def monthly(request):
    """Aggregate the month's days for ?year=&month= (defaults to current month).

    Closed days come from their DayClosing snapshot. Days that have orders but
    were never closed (e.g. an app update landed before the day was closed) are
    computed live from Order/Payment data so their counts aren't lost; those
    rows carry ``is_closed: false``.
    """
    today = services.business_today()
    year = int(request.query_params.get("year", today.year))
    month = int(request.query_params.get("month", today.month))

    # A date may have several closings (cashier closes whenever they like), so
    # sum each date's snapshots into a single daily row.
    closings = DayClosing.objects.filter(
        business_date__year=year, business_date__month=month
    ).order_by("business_date")
    closed_dates = {dc.business_date for dc in closings}

    by_date: dict[str, dict] = {}
    for dc in closings:
        key = dc.business_date.isoformat()
        row = by_date.get(key)
        if row is None:
            by_date[key] = {
                "business_date": key,
                "total_sales": dc.total_sales,
                "cash_total": dc.cash_total,
                "card_total": dc.card_total,
                "bank_transfer_total": dc.bank_transfer_total,
                "purchases_total": dc.purchases_total,
                "orders_count": dc.orders_count,
                "is_closed": True,
            }
        else:
            row["total_sales"] += dc.total_sales
            row["cash_total"] += dc.cash_total
            row["card_total"] += dc.card_total
            row["bank_transfer_total"] += dc.bank_transfer_total
            row["purchases_total"] += dc.purchases_total
            row["orders_count"] += dc.orders_count
    daily = list(by_date.values())

    # Surface days that have orders but no DayClosing snapshot yet.
    # Only orders not yet settled into a DayClosing count as an "open" day; once
    # settled (possibly into another date's snapshot via a midnight-crossing
    # close) they belong to that snapshot, not a phantom open row.
    # ``.order_by()`` clears Order's default ordering (opened_at, id); without
    # it those columns leak into the SELECT and defeat ``.distinct()``, yielding
    # one duplicate row per order instead of one row per date.
    open_dates = (
        Order.objects.filter(
            business_date__year=year,
            business_date__month=month,
            day_closing__isnull=True,
        )
        .exclude(business_date__in=closed_dates)
        .exclude(business_date__isnull=True)
        .order_by()
        .values_list("business_date", flat=True)
        .distinct()
    )
    for business_date in open_dates:
        summary = closing.compute_day_summary(business_date)
        daily.append(
            {
                "business_date": business_date.isoformat(),
                "total_sales": summary["total_sales"],
                "cash_total": summary["cash_total"],
                "card_total": summary["card_total"],
                "bank_transfer_total": summary["bank_transfer_total"],
                "purchases_total": summary["purchases_total"],
                "orders_count": summary["orders_count"],
                "is_closed": False,
            }
        )

    daily.sort(key=lambda row: row["business_date"])

    totals = {key: sum(row[key] for row in daily) for key in _MONTH_TOTAL_KEYS}

    return Response(
        {
            "year": year,
            "month": month,
            **totals,
            "days_count": len(daily),
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
