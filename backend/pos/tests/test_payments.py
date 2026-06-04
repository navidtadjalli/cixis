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
