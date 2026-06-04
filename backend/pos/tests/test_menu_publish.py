from django.test import TestCase

from pos.models import Category, MenuPublishRecord, Product
from pos.publish import build_menu_payload, publish_menu


class MenuPublishTests(TestCase):
    def setUp(self):
        self.drinks = Category.objects.create(name="Drinks", sort_order=2)
        self.food = Category.objects.create(name="Food", sort_order=1)
        Product.objects.create(
            category=self.food,
            name="Burger",
            price=240,
            is_available=True,
            sort_order=2,
        )
        Product.objects.create(
            category=self.food,
            name="Sold Out Soup",
            price=110,
            is_available=False,
            sort_order=1,
        )
        Product.objects.create(
            category=self.food,
            name="Inactive",
            price=10,
            is_active=False,
            sort_order=3,
        )
        Product.objects.create(
            category=self.drinks,
            name="Tea",
            price=80,
            sort_order=1,
        )

    def test_build_menu_payload_filters_active_and_preserves_ordering(self):
        payload = build_menu_payload()

        self.assertEqual([c["name"] for c in payload["categories"]], ["Food", "Drinks"])
        food_products = payload["categories"][0]["products"]
        self.assertEqual([p["name"] for p in food_products], ["Sold Out Soup", "Burger"])
        self.assertFalse(food_products[0]["is_available"])
        self.assertEqual([p["sort_order"] for p in food_products], [1, 2])

    def test_publish_menu_without_remote_records_failed_attempt(self):
        result = publish_menu()

        self.assertFalse(result["success"])
        record = MenuPublishRecord.objects.get()
        self.assertEqual(record.status, MenuPublishRecord.Status.FAILED)
        self.assertIn("سرور راه دور", record.error_message)
