import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from pos import services
from pos.models import (
    Category,
    DayClosing,
    Order,
    OrderItem,
    Payment,
    Product,
    Table,
)


class DateRangeReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.table = Table.objects.create(name="T1", sort_order=1)
        self.category = Category.objects.create(name="Drinks", sort_order=1)
        self.product = Product.objects.create(
            category=self.category, name="Tea", price=70, sort_order=1
        )
        self.today = services.business_today()

    def test_range_report_aggregates_orders_and_items(self):
        order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=self.today,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot="Tea",
            unit_price_snapshot=70,
            quantity=3,
            line_total=210,
        )
        services.recalc_order_totals(order)

        response = self.client.get(
            f"/api/reports/range/?from={self.today}&to={self.today}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["orders_count"], 1)
        self.assertEqual(response.data["orders_total"], 210)
        self.assertEqual(response.data["items_quantity_total"], 3)
        self.assertEqual(response.data["items_amount_total"], 210)
        self.assertEqual(response.data["items"][0]["product_name"], "Tea")
        self.assertEqual(response.data["items"][0]["quantity"], 3)


class MonthlyReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.table = Table.objects.create(name="T1", sort_order=1)
        self.today = services.business_today()
        self.tmp = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _close(self, payload):
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2",
            lambda src, dest: Path(dest).write_bytes(b"x"),
        ):
            return self.client.post(
                "/api/day-closing/close/", payload, format="json"
            )

    def _row_for(self, report, business_date):
        target = business_date.isoformat()
        return next(
            row for row in report["daily"] if row["business_date"] == target
        )

    def test_unclosed_day_with_orders_is_surfaced_live(self):
        """A day with orders but no DayClosing still shows its count + sales."""
        day = self.today.replace(day=15)
        order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.PAID,
            business_date=day,
        )
        Payment.objects.create(
            order=order, amount=250, method=Payment.Method.CASH
        )

        response = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )

        self.assertEqual(response.status_code, 200)
        row = self._row_for(response.data, day)
        self.assertEqual(row["orders_count"], 1)
        self.assertEqual(row["total_sales"], 250)
        self.assertFalse(row["is_closed"])
        self.assertEqual(response.data["days_count"], 1)
        self.assertEqual(response.data["total_sales"], 250)

    def test_closed_day_uses_snapshot_and_is_marked_closed(self):
        day = self.today.replace(day=10)
        DayClosing.objects.create(
            business_date=day,
            total_sales=900,
            cash_total=900,
            orders_count=4,
        )

        response = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )

        row = self._row_for(response.data, day)
        self.assertEqual(row["orders_count"], 4)
        self.assertEqual(row["total_sales"], 900)
        self.assertTrue(row["is_closed"])

    def test_closing_a_past_day_creates_snapshot_and_flips_is_closed(self):
        day = self.today - timedelta(days=1)
        order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.PAID,
            business_date=day,
        )
        Payment.objects.create(
            order=order, amount=300, method=Payment.Method.CASH
        )

        # Before: surfaced live, not closed.
        before = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )
        self.assertFalse(self._row_for(before.data, day)["is_closed"])

        close = self._close({"business_date": day.isoformat(), "confirm": True})
        self.assertEqual(close.status_code, 201)
        self.assertEqual(close.data["business_date"], day.isoformat())
        self.assertTrue(DayClosing.objects.filter(business_date=day).exists())

        # After: same date now comes from the snapshot.
        after = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )
        row = self._row_for(after.data, day)
        self.assertTrue(row["is_closed"])
        self.assertEqual(row["orders_count"], 1)
        self.assertEqual(row["total_sales"], 300)

    def test_multiple_closings_same_date_sum_into_one_row(self):
        """Several closings on one calendar date collapse to one summed row."""
        day = self.today.replace(day=8)
        DayClosing.objects.create(
            business_date=day, total_sales=300, cash_total=300, orders_count=2
        )
        DayClosing.objects.create(
            business_date=day, total_sales=500, card_total=500, orders_count=3
        )

        response = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )

        rows = [
            row
            for row in response.data["daily"]
            if row["business_date"] == day.isoformat()
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_sales"], 800)
        self.assertEqual(rows[0]["orders_count"], 5)
        self.assertTrue(rows[0]["is_closed"])
        self.assertEqual(response.data["total_sales"], 800)

    def test_cannot_close_future_day(self):
        future = (self.today + timedelta(days=1)).isoformat()
        response = self._close({"business_date": future, "confirm": True})
        self.assertEqual(response.status_code, 400)

    def test_unclosed_day_with_many_orders_yields_one_row(self):
        """Regression: Order's default ordering must not defeat distinct().

        Multiple orders on the same unclosed day must collapse to a single
        daily row, not one duplicate row per order.
        """
        day = self.today.replace(day=12)
        for _ in range(3):
            order = Order.objects.create(
                mode=Order.Mode.TABLE,
                table=self.table,
                status=Order.Status.PAID,
                business_date=day,
            )
            Payment.objects.create(
                order=order, amount=100, method=Payment.Method.CASH
            )

        response = self.client.get(
            f"/api/reports/monthly/?year={day.year}&month={day.month}"
        )

        self.assertEqual(response.status_code, 200)
        rows = [
            row
            for row in response.data["daily"]
            if row["business_date"] == day.isoformat()
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["orders_count"], 3)
        self.assertEqual(rows[0]["total_sales"], 300)
        self.assertFalse(rows[0]["is_closed"])
        self.assertEqual(response.data["days_count"], 1)
