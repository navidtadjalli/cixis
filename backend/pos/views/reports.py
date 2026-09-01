"""Reports: monthly DayClosing rollup and an ad-hoc date-range order report."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .. import closing, services, staff_shift
from ..models import (
    DayClosing,
    Employee,
    Order,
    OrderItem,
    ShiftAttendance,
    StaffConsumption,
)

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
    """Aggregate days for an inclusive Gregorian ?from=&to= range.

    The closing-day UI converts its Jalali month selection to this range before
    making the request. Legacy Gregorian ?year=&month= parameters remain as a
    fallback for API consumers that have not migrated yet.

    Closed days come from their DayClosing snapshot. Days that have orders but
    were never closed (e.g. an app update landed before the day was closed) are
    computed live from Order/Payment data so their counts aren't lost; those
    rows carry ``is_closed: false``.
    """
    raw_from = request.query_params.get("from")
    raw_to = request.query_params.get("to")
    uses_legacy_month = not raw_from and not raw_to

    if raw_from or raw_to:
        if not raw_from or not raw_to:
            raise ValidationError({"detail": "بازه تاریخ را کامل وارد کنید."})
        from_date = _parse_date(raw_from, "from")
        to_date = _parse_date(raw_to, "to")
        if from_date > to_date:
            raise ValidationError({"detail": "تاریخ شروع بعد از تاریخ پایان است."})
    else:
        today = services.business_today()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        from_date = date(year, month, 1)
        if month == 12:
            to_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            to_date = date(year, month + 1, 1) - timedelta(days=1)

    # A date may have several closings (cashier closes whenever they like), so
    # sum each date's snapshots into a single daily row.
    closings = DayClosing.objects.filter(
        business_date__range=(from_date, to_date)
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
            business_date__range=(from_date, to_date),
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
            **(
                {"year": year, "month": month}
                if uses_legacy_month
                else {}
            ),
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
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
def paid_orders(request):
    """Return paid tickets for one business day, optionally scoped to a table."""
    today = services.business_today()
    business_date = _parse_date(
        request.query_params.get("business_date", today.isoformat()), "business_date"
    )
    raw_table_id = request.query_params.get("table_id")
    table_id = None
    if raw_table_id:
        try:
            table_id = int(raw_table_id)
        except ValueError:
            raise ValidationError({"table_id": "میز نامعتبر است."})

    orders = Order.objects.filter(
        business_date=business_date,
        status=Order.Status.PAID,
    )
    if table_id is not None:
        orders = orders.filter(table_id=table_id)

    return Response(
        {
            "business_date": business_date.isoformat(),
            "table_id": table_id,
            "orders": closing.settled_order_receipts(
                orders.order_by("-closed_at", "-id")
            ),
        }
    )


def _free_allowance(consumptions) -> dict:
    """Value staff eat for free within their monthly quota, over ``consumptions``.

    ``consumptions`` must be ordered chronologically. Each quantity is charged
    to a product-level pool first (the tagged peanut-butter shake), else its
    category pool (the coffee category). Fractional quantities consume the same
    fraction of quota and price. Returns the free value plus how many units fell
    under the category (coffee) vs product (shake) pools, for display.
    """
    product_units: dict[int, list[tuple[Decimal, Decimal]]] = defaultdict(list)
    category_units: dict[int, list[tuple[Decimal, Decimal]]] = defaultdict(list)
    product_quota: dict[int, int] = {}
    category_quota: dict[int, int] = {}

    for c in consumptions:
        product = c.product
        if product is None:
            continue
        quantity = max(Decimal("0"), c.quantity)
        price = Decimal(c.unit_price_snapshot)
        if product.staff_free_monthly_quota > 0:
            product_units[product.id].append((quantity, price))
            product_quota[product.id] = product.staff_free_monthly_quota
        elif product.category and product.category.staff_free_monthly_quota > 0:
            category_units[product.category_id].append((quantity, price))
            category_quota[product.category_id] = (
                product.category.staff_free_monthly_quota
            )

    def consume(entries, quota):
        remaining = Decimal(quota)
        value = Decimal("0")
        units = Decimal("0")
        for quantity, price in entries:
            if remaining <= 0:
                break
            take = min(quantity, remaining)
            value += price * take
            units += take
            remaining -= take
        return value, units

    free_value = Decimal("0")
    shake_units = Decimal("0")
    for pid, entries in product_units.items():
        value, units = consume(entries, product_quota[pid])
        free_value += value
        shake_units += units

    coffee_units = Decimal("0")
    for cid, entries in category_units.items():
        value, units = consume(entries, category_quota[cid])
        free_value += value
        coffee_units += units

    return {
        "free_value": free_value,
        "free_coffee_units": coffee_units,
        "free_shake_units": shake_units,
    }


@api_view(["GET"])
def staff_monthly(request):
    """Per-employee shift + tab report for ?from=&to= (inclusive Gregorian range).

    The frontend maps the picked Jalali month to this range. Per person:
    shifts worked (full day = 2), total late/early/overtime minutes, the gross
    tab, the free-allowance deduction, and the net tab owed.
    """
    today = services.business_today()
    from_date = _parse_date(
        request.query_params.get("from", today.replace(day=1).isoformat()), "from"
    )
    to_date = _parse_date(request.query_params.get("to", today.isoformat()), "to")
    if from_date > to_date:
        raise ValidationError({"from": "تاریخ شروع بعد از تاریخ پایان است."})

    attendances = ShiftAttendance.objects.filter(
        business_date__gte=from_date, business_date__lte=to_date
    )
    consumptions = (
        StaffConsumption.objects.filter(
            business_date__gte=from_date, business_date__lte=to_date
        )
        .select_related("product", "product__category")
        .order_by("business_date", "id")
    )

    # Rows for every active employee, plus removed staff that still have data in
    # the range so a past month reads correctly.
    names = dict(Employee.objects.values_list("id", "name"))
    active_ids = set(
        Employee.objects.filter(is_active=True).values_list("id", flat=True)
    )
    rows: dict[int, dict] = {}

    def _row(employee_id: int) -> dict:
        row = rows.get(employee_id)
        if row is None:
            row = rows[employee_id] = {
                "employee_id": employee_id,
                "employee_name": names.get(employee_id, "—"),
                "shifts_count": 0,
                "late_minutes": 0,
                "early_minutes": 0,
                "overtime_minutes": 0,
                "gross_tab": Decimal("0"),
                "free_value": Decimal("0"),
                "free_coffee_units": Decimal("0"),
                "free_shake_units": Decimal("0"),
                "net_tab": Decimal("0"),
                "_consumptions": [],
            }
        return row

    for att in attendances:
        row = _row(att.employee_id)
        metrics = staff_shift.compute(
            att.shift, att.is_full_day, att.check_in, att.check_out
        )
        row["shifts_count"] += metrics["shift_count"]
        row["late_minutes"] += metrics["late_minutes"]
        row["early_minutes"] += metrics["early_minutes"]
        row["overtime_minutes"] += metrics["overtime_minutes"]

    for con in consumptions:
        row = _row(con.employee_id)
        row["gross_tab"] += con.line_total
        row["_consumptions"].append(con)

    # Ensure active employees with no activity still appear (zeros).
    for employee_id in active_ids:
        _row(employee_id)

    result = []
    for row in rows.values():
        free = _free_allowance(row.pop("_consumptions"))
        row["free_value"] = free["free_value"]
        row["free_coffee_units"] = free["free_coffee_units"]
        row["free_shake_units"] = free["free_shake_units"]
        row["net_tab"] = row["gross_tab"] - free["free_value"]
        result.append(row)

    result.sort(key=lambda r: (r["employee_id"] not in active_ids, r["employee_name"]))

    return Response(
        {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "employees": result,
        }
    )


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
