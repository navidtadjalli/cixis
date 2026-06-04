from django.test import TestCase
from rest_framework.test import APIClient

from pos.models import Order, Table
from pos import services


class TableApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_list_rename_and_reorder_tables(self):
        created = self.client.post("/api/tables/", {"name": "Table 1"}, format="json")
        self.assertEqual(created.status_code, 201)
        table_id = created.data["id"]
        self.assertEqual(created.data["sort_order"], 1)

        Table.objects.create(name="Table 2", sort_order=2)

        renamed = self.client.patch(
            f"/api/tables/{table_id}/",
            {"name": "Window", "sort_order": 5},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.data["name"], "Window")
        self.assertEqual(renamed.data["sort_order"], 5)

        listed = self.client.get("/api/tables/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([t["name"] for t in listed.data], ["Table 2", "Window"])

    def test_delete_table_with_active_open_order_returns_409(self):
        table = Table.objects.create(name="Busy", sort_order=1)
        Order.objects.create(
            mode=Order.Mode.TABLE,
            table=table,
            status=Order.Status.OPEN,
            business_date=services.business_today(),
        )

        response = self.client.delete(f"/api/tables/{table.id}/")

        self.assertEqual(response.status_code, 409)
        table.refresh_from_db()
        self.assertTrue(table.is_active)

    def test_delete_empty_table_soft_deletes_and_excludes_from_list(self):
        table = Table.objects.create(name="Empty", sort_order=1)

        deleted = self.client.delete(f"/api/tables/{table.id}/")
        self.assertEqual(deleted.status_code, 204)
        table.refresh_from_db()
        self.assertFalse(table.is_active)

        listed = self.client.get("/api/tables/")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data, [])
