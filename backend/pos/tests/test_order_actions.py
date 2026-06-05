from django.test import TestCase
from rest_framework.test import APIClient

from pos import services
from pos.models import Category, Order, OrderItem, Product, Table


class OrderMoveAndMergeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.t1 = Table.objects.create(name="T1", sort_order=1)
        self.t2 = Table.objects.create(name="T2", sort_order=2)
        self.category = Category.objects.create(name="Drinks", sort_order=1)
        self.product = Product.objects.create(
            category=self.category, name="Tea", price=70, sort_order=1
        )

    def _order(self, table):
        return Order.objects.create(
            mode=Order.Mode.TABLE,
            table=table,
            status=Order.Status.OPEN,
            business_date=services.business_today(),
        )

    def _add_item(self, order, qty=1, price=None):
        unit = self.product.price if price is None else price
        return OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            unit_price_snapshot=unit,
            quantity=qty,
            line_total=unit * qty,
        )

    def test_move_to_occupied_table_swaps_instead_of_orphaning(self):
        order_a = self._order(self.t1)
        order_b = self._order(self.t2)

        response = self.client.patch(
            f"/api/orders/{order_a.id}/", {"table_id": self.t2.id}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        order_a.refresh_from_db()
        order_b.refresh_from_db()
        # A moved onto T2; B pushed back onto the vacated T1 (not orphaned).
        self.assertEqual(order_a.table_id, self.t2.id)
        self.assertEqual(order_b.table_id, self.t1.id)

    def test_move_to_empty_table_just_moves(self):
        order_a = self._order(self.t1)

        response = self.client.patch(
            f"/api/orders/{order_a.id}/", {"table_id": self.t2.id}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        order_a.refresh_from_db()
        self.assertEqual(order_a.table_id, self.t2.id)

    def test_add_items_from_merges_and_empties_source(self):
        target = self._order(self.t1)
        source = self._order(self.t2)
        self._add_item(target, qty=1)
        self._add_item(source, qty=2)

        response = self.client.post(
            f"/api/orders/{target.id}/add-items-from/",
            {"source_order_id": source.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(target.items.count(), 1)
        self.assertEqual(target.items.first().quantity, 3)
        self.assertEqual(target.subtotal, 210)
        self.assertEqual(source.items.count(), 0)

    def test_delete_empty_order_succeeds(self):
        order = self._order(self.t1)

        response = self.client.delete(f"/api/orders/{order.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Order.objects.filter(id=order.id).exists())

    def test_delete_order_with_items_is_blocked(self):
        order = self._order(self.t1)
        self._add_item(order, qty=1)

        response = self.client.delete(f"/api/orders/{order.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Order.objects.filter(id=order.id).exists())
