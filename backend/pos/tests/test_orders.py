from django.test import TestCase
from rest_framework.test import APIClient

from pos import services
from pos.models import Category, Order, Product, Table


class OrderItemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.table = Table.objects.create(name="A1", sort_order=1)
        self.category = Category.objects.create(name="Drinks", sort_order=1)
        self.product = Product.objects.create(
            category=self.category, name="Tea", price=70, sort_order=1
        )
        self.order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=services.business_today(),
        )

    def add_item(self, quantity=1):
        return self.client.post(
            f"/api/orders/{self.order.id}/items/",
            {"product_id": self.product.id, "quantity": quantity},
            format="json",
        )

    def test_add_item_snapshots_name_and_price(self):
        response = self.add_item(quantity=2)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["product_name_snapshot"], "Tea")
        self.assertEqual(response.data["unit_price_snapshot"], 70)
        self.assertEqual(response.data["line_total"], 140)

    def test_price_snapshot_survives_later_product_price_change(self):
        response = self.add_item(quantity=1)
        self.assertEqual(response.status_code, 201)
        item_id = response.data["id"]

        self.product.price = 100
        self.product.save(update_fields=["price"])

        patched = self.client.patch(
            f"/api/order-items/{item_id}/", {"quantity": 3}, format="json"
        )

        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.data["unit_price_snapshot"], 70)
        self.assertEqual(patched.data["line_total"], 210)

    def test_total_recomputes_on_quantity_change(self):
        response = self.add_item(quantity=2)
        item_id = response.data["id"]
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, 140)

        patched = self.client.patch(
            f"/api/order-items/{item_id}/", {"quantity": 4}, format="json"
        )

        self.assertEqual(patched.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, 280)
        self.assertEqual(self.order.remaining_amount, 280)

    def test_block_item_edit_on_paid_order(self):
        response = self.add_item(quantity=1)
        item_id = response.data["id"]
        self.order.status = Order.Status.PAID
        self.order.save(update_fields=["status"])

        patched = self.client.patch(
            f"/api/order-items/{item_id}/", {"quantity": 2}, format="json"
        )

        self.assertEqual(patched.status_code, 400)
