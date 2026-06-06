from django.test import TestCase
from rest_framework.test import APIClient

from pos import services
from pos.models import Category, Order, OrderItem, Product, Table


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
