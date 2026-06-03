"""Monthly report: aggregate stored DayClosing records for a year/month."""
from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .. import services
from ..models import DayClosing


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
