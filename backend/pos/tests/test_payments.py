from django.test import TestCase
from rest_framework.test import APIClient

from pos import services
from pos.models import Category, Order, Payment, Product, Table


class PaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.table = Table.objects.create(name="P1", sort_order=1)
        self.category = Category.objects.create(name="Food", sort_order=1)
        self.product = Product.objects.create(
            category=self.category, name="Cake", price=100, sort_order=1
        )
        self.order = Order.objects.create(
            mode=Order.Mode.TABLE,
            table=self.table,
            status=Order.Status.OPEN,
            business_date=services.business_today(),
        )
        item = self.client.post(
            f"/api/orders/{self.order.id}/items/",
            {"product_id": self.product.id, "quantity": 3},
            format="json",
        )
        self.assertEqual(item.status_code, 201)

    def pay(self, amount, method=Payment.Method.CARD):
        return self.client.post(
            f"/api/orders/{self.order.id}/payments/",
            {"amount": amount, "method": method},
            format="json",
        )

    def test_partial_payment_marks_order_partially_paid(self):
        response = self.pay(100)

        self.assertEqual(response.status_code, 201)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_PAID)
        self.assertEqual(self.order.paid_amount, 100)
        self.assertEqual(self.order.remaining_amount, 200)

    def test_full_payment_marks_order_paid(self):
        response = self.pay(300, Payment.Method.CASH)

        self.assertEqual(response.status_code, 201)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.paid_amount, 300)
        self.assertEqual(self.order.remaining_amount, 0)

    def test_multiple_payments_accumulate_and_reduce_remaining(self):
        first = self.pay(120, Payment.Method.CASH)
        second = self.pay(180, Payment.Method.BANK_TRANSFER)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_amount, 300)
        self.assertEqual(self.order.remaining_amount, 0)
        self.assertEqual(self.order.status, Order.Status.PAID)

    def split(self, item_id, quantity, method=Payment.Method.CARD):
        return self.client.post(
            f"/api/orders/{self.order.id}/payments/",
            {"method": method, "items": [{"item_id": item_id, "quantity": quantity}]},
            format="json",
        )

    def test_item_split_records_paid_quantity_and_derives_amount(self):
        item = self.order.items.first()
        response = self.split(item.id, 2)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], 200)
        item.refresh_from_db()
        self.assertEqual(item.paid_quantity, 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_amount, 200)
        self.assertEqual(self.order.remaining_amount, 100)
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_PAID)

    def test_item_split_clamps_to_remaining_quantity(self):
        item = self.order.items.first()
        self.split(item.id, 2)
        # Requesting more than what is left only pays the remaining 1 unit.
        response = self.split(item.id, 5)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["amount"], 100)
        item.refresh_from_db()
        self.assertEqual(item.paid_quantity, 3)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_full_amount_payment_marks_all_items_paid(self):
        item = self.order.items.first()
        self.pay(300, Payment.Method.CASH)

        item.refresh_from_db()
        self.assertEqual(item.paid_quantity, item.quantity)
