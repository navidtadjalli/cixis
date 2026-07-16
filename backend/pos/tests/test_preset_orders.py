"""An untouched preset code is a slot, not an order: it must stay out of the
closing register and outlive the close, the way a table does."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from pos import closing, services
from pos.models import Category, Order, OrderItem, Payment, Product


class PresetOrderClosingTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.tmp.name)
        self.today = services.business_today()
        self.category = Category.objects.create(name="نوشیدنی")
        self.product = Product.objects.create(
            category=self.category, name="چای", price=20
        )

    def tearDown(self):
        self.tmp.cleanup()

    def fake_copy2(self, src, dest):
        """Stand in for snapshotting the SQLite file, which the test DB has none of."""
        Path(dest).write_bytes(b"test sqlite backup")
        return dest

    def close_day(self):
        with override_settings(BACKUP_DIR=self.backup_dir), patch(
            "pos.closing.shutil.copy2", self.fake_copy2
        ):
            return self.client.post(
                reverse("day-closing-close"), {"confirm": True}, "application/json"
            )

    def make_preset(self, label):
        return Order.objects.create(
            mode=Order.Mode.EVENT,
            event_customer_label=label,
            is_preset=True,
            business_date=self.today,
        )

    def ring_up(self, order, quantity=1):
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            unit_price_snapshot=self.product.price,
            quantity=quantity,
            line_total=self.product.price * quantity,
        )
        services.recalc_order_totals(order)

    def test_untouched_presets_are_absent_from_the_summary(self):
        for index in range(5):
            self.make_preset(f"A{index}")

        summary = closing.compute_day_summary(None)
        self.assertEqual(summary["orders_count"], 0)
        self.assertEqual(summary["open_orders_count"], 0)
        self.assertEqual(summary["unresolved_orders"], [])

    def test_a_used_preset_counts_like_any_order(self):
        used = self.make_preset("A1")
        self.make_preset("A2")
        self.ring_up(used)

        summary = closing.compute_day_summary(None)
        self.assertEqual(summary["orders_count"], 1)
        self.assertEqual(summary["gross_sales"], 20)
        self.assertEqual(
            [o["table_name"] for o in summary["unresolved_orders"]], ["A1"]
        )

    def test_a_preset_with_only_a_payment_counts(self):
        order = self.make_preset("A1")
        Payment.objects.create(order=order, amount=50, method=Payment.Method.CASH)

        summary = closing.compute_day_summary(None)
        self.assertEqual(summary["orders_count"], 1)
        self.assertEqual(summary["cash_total"], 50)

    def test_closing_settles_used_presets_and_spares_untouched_ones(self):
        used = self.make_preset("A1")
        spare = self.make_preset("A2")
        self.ring_up(used)

        self.assertEqual(self.close_day().status_code, 201)

        used.refresh_from_db()
        spare.refresh_from_db()
        self.assertIsNotNone(used.day_closing_id)
        # The unused code is still waiting in the event list for tomorrow.
        self.assertIsNone(spare.day_closing_id)
        self.assertEqual(spare.status, Order.Status.OPEN)

    def test_a_register_of_only_untouched_presets_has_nothing_to_close(self):
        self.make_preset("A1")

        self.assertEqual(self.close_day().status_code, 400)
        self.assertEqual(Order.objects.get().status, Order.Status.OPEN)
