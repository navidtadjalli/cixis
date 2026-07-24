"""Tests for the Majaz guest-code bulk generator and per-code editing."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from pos.models import GuestCode


class GuestCodeTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_bulk_creates_inclusive_range(self):
        res = self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "الف", "start": 1, "end": 3},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["created"], 3)
        self.assertEqual(GuestCode.objects.count(), 3)
        self.assertTrue(GuestCode.objects.filter(code="الف1").exists())
        self.assertTrue(GuestCode.objects.filter(code="الف3").exists())

    def test_bulk_skips_existing(self):
        self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "الف", "start": 1, "end": 3},
            format="json",
        )
        res = self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "الف", "start": 1, "end": 5},
            format="json",
        )
        self.assertEqual(res.json()["created"], 2)
        self.assertEqual(res.json()["skipped"], 3)
        self.assertEqual(GuestCode.objects.count(), 5)

    def test_bulk_accepts_persian_digits(self):
        res = self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "ب", "start": "۱", "end": "۳"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["created"], 3)

    def test_bulk_rejects_reversed_range(self):
        res = self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "ب", "start": 5, "end": 1},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_bulk_rejects_oversized_range(self):
        res = self.client.post(
            reverse("guest-codes-bulk"),
            {"prefix": "ب", "start": 1, "end": 1000},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_patch_updates_guest_fields(self):
        code = GuestCode.objects.create(code="ج1")
        res = self.client.patch(
            f"/api/guest-codes/{code.id}/",
            {
                "guest_name": "مهمان",
                "guest_count": 3,
                "men_count": 2,
                "women_count": 1,
                "paid_entry": True,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        code.refresh_from_db()
        self.assertEqual(code.guest_name, "مهمان")
        self.assertEqual(code.men_count, 2)
        self.assertTrue(code.paid_entry)

    def test_delete_removes_code(self):
        code = GuestCode.objects.create(code="ج2")
        res = self.client.delete(f"/api/guest-codes/{code.id}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(GuestCode.objects.filter(id=code.id).exists())
