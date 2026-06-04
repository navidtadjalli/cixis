from django.test import TestCase
from rest_framework.test import APIClient

from pos.models import Category, Product


class ProductApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="Coffee", sort_order=1)

    def test_create_and_list_products(self):
        created = self.client.post(
            "/api/products/",
            {"category": self.category.id, "name": "Latte", "price": 120},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["name"], "Latte")
        self.assertEqual(created.data["sort_order"], 1)

        listed = self.client.get("/api/products/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(listed.data[0]["name"], "Latte")

    def test_availability_toggle_persists(self):
        product = Product.objects.create(
            category=self.category, name="Mocha", price=150, sort_order=1
        )

        response = self.client.patch(
            f"/api/products/{product.id}/",
            {"is_available": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertFalse(product.is_available)

    def test_soft_deleted_product_is_excluded_from_get(self):
        product = Product.objects.create(
            category=self.category, name="Espresso", price=90, sort_order=1
        )

        deleted = self.client.delete(f"/api/products/{product.id}/")
        self.assertEqual(deleted.status_code, 204)
        product.refresh_from_db()
        self.assertFalse(product.is_active)

        listed = self.client.get("/api/products/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data, [])

    def test_category_sort_order_patch(self):
        response = self.client.patch(
            f"/api/categories/{self.category.id}/",
            {"sort_order": 9},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.sort_order, 9)
