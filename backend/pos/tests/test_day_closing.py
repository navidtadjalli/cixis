import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from pos import closing, services
from pos.models import (
    Category,
    DayClosing,
    Order,
    Payment,
    Product,
    ResourcePurchase,
    ResourceSuggestion,
    Table,
)


class DayClosingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tmp = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.tmp.name)
        self.today = services.business_today()
        self.table = Table.objects.create(name="D1", sort_order=1)
        self.category = Category.objects.create(name="Meals", sort_order=1)
        self.product = Product.objects.create(
            category=self.category, name="Plate", price=100, sort_order=1
        )

    def tearDown(self):
        self.tmp.cleanup()

    def create_paid_order(self, quantity=2):
        order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=self.today,
        )
        item = self.client.post(
            f"/api/orders/{order.id}/items/",
            {"product_id": self.product.id, "quantity": quantity},
            format="json",
        )
        self.assertEqual(item.status_code, 201)
        payment = self.client.post(
            f"/api/orders/{order.id}/payments/",
            {"amount": 200, "method": Payment.Method.CARD},
            format="json",
        )
        self.assertEqual(payment.status_code, 201)
        order.refresh_from_db()
        return order

    def fake_copy2(self, src, dest):
        Path(dest).write_bytes(b"test sqlite backup")
        return dest

    def test_preview_aggregates_totals_correctly(self):
        self.create_paid_order()
        ResourcePurchase.objects.create(
            name="Milk", quantity=2, unit="l", cost=30, business_date=self.today
        )
        ResourceSuggestion.objects.create(
            resource_name="Beans",
            reason="Low stock",
            suggested_quantity=1.5,
            created_for_date=self.today,
        )

        response = self.client.get("/api/day-closing/preview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_sales"], 200)
        self.assertEqual(response.data["card_total"], 200)
        self.assertEqual(response.data["orders_count"], 1)
        self.assertEqual(response.data["closed_orders_count"], 1)
        self.assertEqual(response.data["open_orders_count"], 0)
        self.assertEqual(response.data["table_usage_count"], 1)
        self.assertEqual(response.data["purchases_total"], 30)
        self.assertEqual(response.data["resource_suggestions"][0]["resource_name"], "Beans")

    def test_close_creates_backup_file(self):
        self.create_paid_order()
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            response = self.client.post(
                "/api/day-closing/close/", {"confirm": False}, format="json"
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Path(response.data["backup_path"]).exists())
        self.assertEqual(len(list(self.backup_dir.glob("cixis-backup-*.db"))), 1)

    def test_make_backup_eight_times_leaves_only_seven_files(self):
        class FakeLocalTime:
            def __init__(self):
                self.count = 0

            def strftime(self, fmt):
                self.count += 1
                return f"20260101-00000{self.count}"

        fake_time = FakeLocalTime()
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ), patch("pos.closing.timezone.localtime", return_value=fake_time):
            for i in range(8):
                record = closing.make_backup()
                if i < 7:
                    os.utime(record.file_path, (i + 1, i + 1))

        files = list(self.backup_dir.glob("cixis-backup-*.db"))
        self.assertEqual(len(files), 7)

    def test_close_blocked_with_open_orders_until_confirmed(self):
        Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=self.today,
        )

        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            blocked = self.client.post(
                "/api/day-closing/close/", {"confirm": False}, format="json"
            )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("unresolved_orders", blocked.data)
        self.assertEqual(DayClosing.objects.count(), 0)

        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            confirmed = self.client.post(
                "/api/day-closing/close/", {"confirm": True}, format="json"
            )
        self.assertEqual(confirmed.status_code, 201)
        self.assertEqual(DayClosing.objects.count(), 1)

    def _paid_order_on(self, business_date, amount=200):
        order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=business_date,
        )
        self.client.post(
            f"/api/orders/{order.id}/items/",
            {"product_id": self.product.id, "quantity": 2},
            format="json",
        )
        self.client.post(
            f"/api/orders/{order.id}/payments/",
            {"amount": amount, "method": Payment.Method.CARD},
            format="json",
        )
        order.refresh_from_db()
        return order

    def test_preview_includes_unsettled_orders_from_a_previous_date(self):
        """A past-midnight session: yesterday's unclosed orders stay visible."""
        yesterday = self.today - timedelta(days=1)
        self._paid_order_on(yesterday, amount=150)
        self._paid_order_on(self.today, amount=200)

        response = self.client.get("/api/day-closing/preview/")

        self.assertEqual(response.status_code, 200)
        # Both orders count toward the live register regardless of date.
        self.assertEqual(response.data["orders_count"], 2)
        self.assertEqual(response.data["total_sales"], 350)

    def test_live_close_settles_orders_across_dates_into_one_snapshot(self):
        """Manual close settles the whole open session, then preview is zero."""
        yesterday = self.today - timedelta(days=1)
        self._paid_order_on(yesterday, amount=150)
        self._paid_order_on(self.today, amount=200)

        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            closed = self.client.post(
                "/api/day-closing/close/", {"confirm": True}, format="json"
            )

        self.assertEqual(closed.status_code, 201)
        self.assertEqual(closed.data["business_date"], self.today.isoformat())
        self.assertEqual(closed.data["orders_count"], 2)
        self.assertEqual(closed.data["total_sales"], 350)
        # Every order is now settled; the live register resets to zero.
        self.assertEqual(
            Order.objects.filter(day_closing__isnull=True).count(), 0
        )
        preview = self.client.get("/api/day-closing/preview/")
        self.assertEqual(preview.data["orders_count"], 0)
        self.assertEqual(preview.data["total_sales"], 0)

    def test_can_close_multiple_times_in_one_day(self):
        """Cashier may close whenever; same calendar day -> several closings."""
        self._paid_order_on(self.today, amount=100)
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            first = self.client.post(
                "/api/day-closing/close/", {"confirm": True}, format="json"
            )
        self.assertEqual(first.status_code, 201)

        # New orders arrive after the first close; a second close settles them.
        self._paid_order_on(self.today, amount=250)
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            second = self.client.post(
                "/api/day-closing/close/", {"confirm": True}, format="json"
            )
        self.assertEqual(second.status_code, 201)

        self.assertEqual(
            DayClosing.objects.filter(business_date=self.today).count(), 2
        )
        self.assertEqual(first.data["total_sales"], 100)
        self.assertEqual(second.data["total_sales"], 250)

    def test_close_with_nothing_to_settle_is_rejected(self):
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            response = self.client.post(
                "/api/day-closing/close/", {"confirm": True}, format="json"
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DayClosing.objects.count(), 0)
