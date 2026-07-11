from unittest.mock import patch

from django.test import TestCase

from pos.models import AppSetting, Category, MenuPublishRecord, Product
from pos.publish import build_menu_payload, publish_menu, render_menu_html

STORAGE_SETTINGS = {
    "s3_access_key": "AKIAEXAMPLE",
    "s3_secret_key": "shhh",
    "s3_bucket": "cixis",
    "s3_endpoint_url": "https://s3.ir-thr-at1.arvanstorage.ir",
    "s3_region": "ir-thr-at1",
}


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

    def _configure_storage(self):
        for key, value in STORAGE_SETTINGS.items():
            AppSetting.objects.update_or_create(key=key, defaults={"value": value})

    def test_build_menu_payload_filters_active_and_preserves_ordering(self):
        payload = build_menu_payload()

        self.assertEqual([c["name"] for c in payload["categories"]], ["Food", "Drinks"])
        food_products = payload["categories"][0]["products"]
        self.assertEqual([p["name"] for p in food_products], ["Sold Out Soup", "Burger"])
        self.assertFalse(food_products[0]["is_available"])
        self.assertEqual([p["sort_order"] for p in food_products], [1, 2])

    def test_render_menu_html_includes_products_and_flags_unavailable(self):
        html = render_menu_html(build_menu_payload())

        self.assertIn("Burger", html)
        self.assertIn("Tea", html)
        self.assertNotIn("Inactive", html)
        self.assertIn("ناموجود", html)

    def test_build_menu_payload_excludes_unpublishable_products(self):
        Product.objects.create(
            category=self.food,
            name="Staff Only",
            price=50,
            is_publishable=False,
            sort_order=4,
        )

        payload = build_menu_payload()
        food_products = payload["categories"][0]["products"]

        self.assertNotIn("Staff Only", [p["name"] for p in food_products])
        self.assertNotIn("Staff Only", render_menu_html(payload))

    def test_publish_menu_without_storage_config_records_failed_attempt(self):
        result = publish_menu()

        self.assertFalse(result["success"])
        record = MenuPublishRecord.objects.get()
        self.assertEqual(record.status, MenuPublishRecord.Status.FAILED)
        self.assertIn("تنظیمات فضای ذخیره‌سازی", record.error_message)

    @patch("pos.publish.upload_html")
    def test_publish_menu_uploads_index_html_and_returns_website_url(self, upload):
        self._configure_storage()

        result = publish_menu()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["url"], "https://cixis.s3-website.ir-thr-at1.arvanstorage.ir"
        )
        object_name, html, config = upload.call_args.args
        self.assertEqual(object_name, "index.html")
        self.assertIn("Burger", html)
        self.assertEqual(config["s3_bucket"], "cixis")
        self.assertEqual(
            MenuPublishRecord.objects.get().status, MenuPublishRecord.Status.SUCCESS
        )

    @patch("pos.publish.upload_html", side_effect=RuntimeError("boom"))
    def test_publish_menu_records_upload_failure_without_raising(self, _upload):
        self._configure_storage()

        result = publish_menu()

        self.assertFalse(result["success"])
        record = MenuPublishRecord.objects.get()
        self.assertEqual(record.status, MenuPublishRecord.Status.FAILED)
        self.assertIn("boom", record.error_message)
