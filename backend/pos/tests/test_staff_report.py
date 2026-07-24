"""API tests for the attendance entry endpoints and the monthly staff report."""
from django.test import TestCase
from rest_framework.test import APIClient

from pos.models import Category, Employee, Product, ShiftAttendance


class StaffReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = Employee.objects.create(name="سعید", sort_order=1)

        # Coffee category is free up to 10 units/month.
        self.coffee_cat = Category.objects.create(
            name="قهوه", sort_order=1, staff_free_monthly_quota=10
        )
        self.coffee = Product.objects.create(
            category=self.coffee_cat, name="اسپرسو", price=50, sort_order=1
        )
        # The peanut-butter shake is a single tagged product, free 1/month.
        self.drinks = Category.objects.create(name="شیک", sort_order=2)
        self.shake = Product.objects.create(
            category=self.drinks,
            name="شیک بادام‌زمینی",
            price=200,
            sort_order=1,
            staff_free_monthly_quota=1,
        )
        self.food = Category.objects.create(name="غذا", sort_order=3)
        self.plate = Product.objects.create(
            category=self.food, name="بشقاب", price=100, sort_order=1
        )

    def _add_consumption(
        self, product, quantity, business_date="2026-04-05", shift="morning"
    ):
        res = self.client.post(
            "/api/staff-consumption/",
            {
                "employee": self.employee.id,
                "product": product.id,
                "quantity": quantity,
                "business_date": business_date,
                "shift": shift,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()

    def _add_attendance(self, shift, check_in, check_out, business_date, full=False):
        res = self.client.post(
            "/api/attendance/",
            {
                "employee": self.employee.id,
                "business_date": business_date,
                "shift": shift,
                "check_in": check_in,
                "check_out": check_out,
                "is_full_day": full,
            },
            format="json",
        )
        self.assertIn(res.status_code, (200, 201), res.content)
        return res.json()

    def test_consumption_snapshots_price_and_line_total(self):
        row = self._add_consumption(self.coffee, 3)
        self.assertEqual(row["unit_price_snapshot"], 50)
        self.assertEqual(row["line_total"], 150)
        self.assertEqual(row["product_name_snapshot"], "اسپرسو")

    def test_consumption_list_only_returns_the_selected_shift(self):
        morning = self._add_consumption(self.coffee, 1, shift="morning")
        self._add_consumption(self.shake, 1, shift="evening")

        res = self.client.get(
            "/api/staff-consumption/",
            {"date": "2026-04-05", "shift": "morning"},
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual([row["id"] for row in res.json()], [morning["id"]])

    def test_fractional_consumption_is_priced_and_deducted_proportionally(self):
        coffee = self._add_consumption(self.coffee, "0.5")
        self._add_consumption(self.shake, "0.25")
        self._add_consumption(self.plate, "0.5")

        self.assertEqual(coffee["quantity"], 0.5)
        self.assertEqual(coffee["line_total"], 25)

        res = self.client.get(
            "/api/reports/staff-monthly/", {"from": "2026-04-01", "to": "2026-04-30"}
        )
        row = next(
            r for r in res.json()["employees"] if r["employee_id"] == self.employee.id
        )

        # gross = .5*50 + .25*200 + .5*100 = 125
        self.assertEqual(row["gross_tab"], 125)
        # Coffee and shake portions are both still inside their free quotas.
        self.assertEqual(row["free_value"], 75)
        self.assertEqual(row["free_coffee_units"], 0.5)
        self.assertEqual(row["free_shake_units"], 0.25)
        self.assertEqual(row["net_tab"], 50)

    def test_attendance_upsert_updates_not_duplicates(self):
        self._add_attendance("morning", "09:00", "17:00", "2026-04-05")
        second = self._add_attendance("morning", "09:30", "18:00", "2026-04-05")
        self.assertEqual(second["late_minutes"], 30)
        self.assertEqual(
            ShiftAttendance.objects.filter(
                employee=self.employee, business_date="2026-04-05", shift="morning"
            ).count(),
            1,
        )

    def test_monthly_report_aggregates_shifts_and_net_tab(self):
        # 12 coffees (10 free @50), 2 shakes (1 free @200), 1 plate @100.
        self._add_consumption(self.coffee, 12)
        self._add_consumption(self.shake, 2)
        self._add_consumption(self.plate, 1)

        # A full day (2 shifts) and an evening that came early + stayed over.
        self._add_attendance("morning", "09:00", "00:00", "2026-04-05", full=True)
        self._add_attendance("evening", "14:00", "02:00", "2026-04-06")

        res = self.client.get(
            "/api/reports/staff-monthly/", {"from": "2026-04-01", "to": "2026-04-30"}
        )
        self.assertEqual(res.status_code, 200, res.content)
        rows = res.json()["employees"]
        row = next(r for r in rows if r["employee_id"] == self.employee.id)

        self.assertEqual(row["shifts_count"], 3)
        self.assertEqual(row["late_minutes"], 0)
        self.assertEqual(row["early_minutes"], 120)
        self.assertEqual(row["overtime_minutes"], 120)

        # gross = 12*50 + 2*200 + 1*100 = 1100
        self.assertEqual(row["gross_tab"], 1100)
        # free = 10*50 (coffee) + 1*200 (shake) = 700
        self.assertEqual(row["free_value"], 700)
        self.assertEqual(row["free_coffee_units"], 10)
        self.assertEqual(row["free_shake_units"], 1)
        self.assertEqual(row["net_tab"], 400)

    def test_report_excludes_out_of_range_and_includes_idle_active(self):
        # Consumption outside the window must not count.
        self._add_consumption(self.coffee, 5, business_date="2026-03-30")
        res = self.client.get(
            "/api/reports/staff-monthly/", {"from": "2026-04-01", "to": "2026-04-30"}
        )
        row = next(
            r for r in res.json()["employees"] if r["employee_id"] == self.employee.id
        )
        self.assertEqual(row["gross_tab"], 0)
        self.assertEqual(row["shifts_count"], 0)
