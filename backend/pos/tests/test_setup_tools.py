import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from pos import menu_seed
from pos.models import (
    AppSetting,
    Category,
    DayClosing,
    Order,
    OrderItem,
    Payment,
    Product,
    Table,
)
from pos.views.setup import MENU_FILE

GOD_CODE = "open-sesame"
PASSWORD = "1234"


@patch("pos.views.misc.GOD_CODE_HASH", make_password(GOD_CODE))
class SetupToolsTests(TestCase):
    def setUp(self):
        AppSetting.objects.create(
            key="revenue_password", value=make_password(PASSWORD)
        )

    def post(self, name, payload=None, password=PASSWORD):
        body = {"password": password, **(payload or {})}
        return self.client.post(reverse(name), body, "application/json")

    # --- auth ---------------------------------------------------------------

    def test_every_endpoint_rejects_a_wrong_password(self):
        for name in (
            "setup-wipe-tables",
            "setup-wipe-orders",
            "setup-wipe-menu",
            "setup-load-menu",
            "setup-bulk-tables",
            "setup-bulk-event-codes",
        ):
            with self.subTest(endpoint=name):
                res = self.post(name, {"count": 1, "start": 1, "end": 1}, "nope")
                self.assertEqual(res.status_code, 401)

    def test_god_code_authorizes(self):
        res = self.post("setup-bulk-tables", {"count": 1}, GOD_CODE)
        self.assertEqual(res.status_code, 201)

    # --- wipes --------------------------------------------------------------

    def test_wipe_tables_hard_deletes(self):
        Table.objects.create(name="میز ۱")
        Table.objects.create(name="میز ۲")

        res = self.post("setup-wipe-tables")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"deleted_tables": 2, "deleted_orders": 0})
        self.assertEqual(Table.objects.count(), 0)

    def test_wipe_tables_takes_unsettled_table_orders_with_it(self):
        table = Table.objects.create(name="میز ۱")
        Order.objects.create(mode=Order.Mode.TABLE, table=table)

        res = self.post("setup-wipe-tables")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"deleted_tables": 1, "deleted_orders": 1})
        self.assertEqual(Table.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_wipe_tables_keeps_settled_orders_and_event_codes(self):
        table = Table.objects.create(name="میز ۱")
        closing = DayClosing.objects.create(business_date=date(2026, 7, 16))
        settled = Order.objects.create(
            mode=Order.Mode.TABLE, table=table, day_closing=closing
        )
        code = Order.objects.create(
            mode=Order.Mode.EVENT, event_customer_label="A1", is_preset=True
        )

        res = self.post("setup-wipe-tables")
        self.assertEqual(res.json(), {"deleted_tables": 1, "deleted_orders": 0})

        # History survives the reset; it just loses the table it pointed at.
        settled.refresh_from_db()
        self.assertIsNone(settled.table_id)
        self.assertTrue(Order.objects.filter(pk=code.pk).exists())

    def test_wipe_menu_hard_deletes_and_keeps_order_history(self):
        category = Category.objects.create(name="نوشیدنی")
        product = Product.objects.create(category=category, name="چای", price=20)
        order = Order.objects.create(mode=Order.Mode.EVENT, event_customer_label="A1")
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot="چای",
            unit_price_snapshot=20,
            quantity=1,
            line_total=20,
        )

        res = self.post("setup-wipe-menu")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"deleted_products": 1, "deleted_categories": 1})
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)

        # The line survives with its snapshot; only the FK is cleared.
        item.refresh_from_db()
        self.assertIsNone(item.product_id)
        self.assertEqual(item.product_name_snapshot, "چای")
        self.assertEqual(item.line_total, 20)

    def test_wipe_orders_clears_every_order_with_its_items_and_payments(self):
        category = Category.objects.create(name="نوشیدنی")
        product = Product.objects.create(category=category, name="چای", price=20)
        table = Table.objects.create(name="میز ۱")
        table_order = Order.objects.create(mode=Order.Mode.TABLE, table=table)
        code = Order.objects.create(
            mode=Order.Mode.EVENT, event_customer_label="A1", is_preset=True
        )
        OrderItem.objects.create(
            order=table_order,
            product=product,
            product_name_snapshot="چای",
            unit_price_snapshot=20,
            quantity=1,
            line_total=20,
        )
        Payment.objects.create(
            order=table_order, amount=20, method=Payment.Method.CASH
        )

        res = self.post("setup-wipe-orders")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"deleted_orders": 2})
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertFalse(Order.objects.filter(pk=code.pk).exists())

        # The reset clears orders only — the catalog and tables stay put.
        self.assertEqual(Table.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)

    def test_wipe_orders_keeps_day_closing_snapshots(self):
        closing = DayClosing.objects.create(
            business_date=date(2026, 7, 16), total_sales=500
        )
        Order.objects.create(mode=Order.Mode.EVENT, event_customer_label="A1",
                             day_closing=closing)

        self.post("setup-wipe-orders")

        closing.refresh_from_db()
        self.assertEqual(closing.total_sales, 500)
        self.assertEqual(Order.objects.count(), 0)

    def test_wipe_orders_unblocks_a_table_wipe(self):
        table = Table.objects.create(name="میز ۱")
        Order.objects.create(mode=Order.Mode.TABLE, table=table)

        self.post("setup-wipe-orders")
        res = self.post("setup-wipe-tables")
        self.assertEqual(res.json(), {"deleted_tables": 1, "deleted_orders": 0})
        self.assertEqual(Table.objects.count(), 0)

    def test_wipe_menu_leaves_tables_alone(self):
        Table.objects.create(name="میز ۱")
        Category.objects.create(name="نوشیدنی")

        self.post("setup-wipe-menu")
        self.assertEqual(Table.objects.count(), 1)

    # --- load menu ----------------------------------------------------------

    def bundled_menu(self):
        with open(menu_seed.menu_path(MENU_FILE), encoding="utf-8") as fh:
            return json.load(fh)

    def test_load_menu_seeds_every_bundled_category_and_product(self):
        data = self.bundled_menu()
        expected_products = sum(len(c["items"]) for c in data["categories"])

        res = self.post("setup-load-menu")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.json(),
            {
                "categories_created": len(data["categories"]),
                "products_created": expected_products,
            },
        )
        self.assertEqual(Category.objects.count(), len(data["categories"]))
        self.assertEqual(Product.objects.count(), expected_products)

    def test_load_menu_carries_descriptions_and_prices_across(self):
        self.post("setup-load-menu")

        first = self.bundled_menu()["categories"][0]["items"][0]
        product = Product.objects.get(name=first["name"])
        self.assertEqual(product.price, first["price"])
        self.assertEqual(product.description, first.get("description", ""))

    def test_load_menu_twice_adds_nothing_and_keeps_edited_prices(self):
        self.post("setup-load-menu")
        product = Product.objects.first()
        product.price = 1
        product.save(update_fields=["price"])
        before = Product.objects.count()

        res = self.post("setup-load-menu")
        self.assertEqual(
            res.json(), {"categories_created": 0, "products_created": 0}
        )
        self.assertEqual(Product.objects.count(), before)
        product.refresh_from_db()
        self.assertEqual(product.price, 1)

    def test_load_menu_restores_the_menu_after_a_wipe(self):
        self.post("setup-load-menu")
        self.post("setup-wipe-menu")
        self.assertEqual(Product.objects.count(), 0)

        self.post("setup-load-menu")
        self.assertEqual(
            Product.objects.count(),
            sum(len(c["items"]) for c in self.bundled_menu()["categories"]),
        )

    def test_load_menu_marks_the_menu_seeded_so_first_launch_wont_reseed(self):
        self.post("setup-load-menu")
        self.assertEqual(AppSetting.objects.get(key="menu_seeded").value, "true")

    def test_load_menu_reports_a_missing_bundle_instead_of_crashing(self):
        with patch("pos.views.setup.MENU_FILE", "menu.does-not-exist.json"):
            res = self.post("setup-load-menu")
        self.assertEqual(res.status_code, 501)
        self.assertEqual(Product.objects.count(), 0)

    # --- bulk tables --------------------------------------------------------

    def test_bulk_tables_creates_persian_numbered_names(self):
        res = self.post("setup-bulk-tables", {"count": 3})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json(), {"created": 3, "skipped": 0})
        self.assertEqual(
            list(Table.objects.order_by("sort_order").values_list("name", flat=True)),
            ["میز ۱", "میز ۲", "میز ۳"],
        )

    def test_bulk_tables_skips_existing_names(self):
        Table.objects.create(name="میز ۲")

        res = self.post("setup-bulk-tables", {"count": 3})
        self.assertEqual(res.json(), {"created": 2, "skipped": 1})
        self.assertEqual(Table.objects.filter(name="میز ۲").count(), 1)
        self.assertEqual(Table.objects.count(), 3)

    def test_bulk_tables_accepts_persian_digits(self):
        res = self.post("setup-bulk-tables", {"count": "۲"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Table.objects.count(), 2)

    def test_bulk_tables_rejects_bad_counts(self):
        for count in (0, -1, "abc", 501):
            with self.subTest(count=count):
                res = self.post("setup-bulk-tables", {"count": count})
                self.assertEqual(res.status_code, 400)
        self.assertEqual(Table.objects.count(), 0)

    # --- bulk event codes ---------------------------------------------------

    def test_bulk_event_codes_range_is_inclusive_both_ends(self):
        res = self.post("setup-bulk-event-codes", {"prefix": "A", "start": 1, "end": 3})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json(), {"created": 3, "skipped": 0})
        self.assertEqual(
            sorted(
                Order.objects.values_list("event_customer_label", flat=True)
            ),
            ["A1", "A2", "A3"],
        )

    def test_bulk_event_codes_are_preset_open_event_orders(self):
        self.post("setup-bulk-event-codes", {"prefix": "A", "start": 1, "end": 1})

        order = Order.objects.get()
        self.assertTrue(order.is_preset)
        self.assertEqual(order.mode, Order.Mode.EVENT)
        self.assertEqual(order.status, Order.Status.OPEN)
        self.assertIsNone(order.table_id)

    def test_bulk_event_codes_assign_sequential_order_numbers(self):
        self.post("setup-bulk-event-codes", {"prefix": "A", "start": 1, "end": 3})
        numbers = sorted(Order.objects.values_list("order_number", flat=True))
        self.assertEqual(len(set(numbers)), 3)

    def test_bulk_event_codes_skip_already_active_labels(self):
        Order.objects.create(mode=Order.Mode.EVENT, event_customer_label="A2")

        res = self.post("setup-bulk-event-codes", {"prefix": "A", "start": 1, "end": 3})
        self.assertEqual(res.json(), {"created": 2, "skipped": 1})
        self.assertEqual(Order.objects.filter(event_customer_label="A2").count(), 1)

    def test_bulk_event_codes_allow_a_blank_prefix(self):
        res = self.post("setup-bulk-event-codes", {"prefix": "", "start": 7, "end": 8})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(
            sorted(Order.objects.values_list("event_customer_label", flat=True)),
            ["7", "8"],
        )

    def test_bulk_event_codes_reject_inverted_and_oversized_ranges(self):
        for payload in ({"start": 5, "end": 1}, {"start": 1, "end": 501}):
            with self.subTest(payload=payload):
                res = self.post("setup-bulk-event-codes", {"prefix": "A", **payload})
                self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
