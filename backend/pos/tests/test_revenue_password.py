from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse

from pos.models import AppSetting

GOD_CODE = "open-sesame"


@patch("pos.views.misc.GOD_CODE_HASH", make_password(GOD_CODE))
class RevenuePasswordTests(TestCase):
    def setUp(self):
        AppSetting.objects.create(
            key="revenue_password", value=make_password("1234")
        )

    def test_unlock_with_correct_password(self):
        res = self.client.post(
            reverse("revenue-unlock"), {"password": "1234"}, "application/json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

    def test_unlock_with_wrong_password(self):
        res = self.client.post(
            reverse("revenue-unlock"), {"password": "nope"}, "application/json"
        )
        self.assertEqual(res.status_code, 401)

    def test_change_password_stores_hash_and_rotates(self):
        res = self.client.post(
            reverse("revenue-change-password"),
            {"current_password": "1234", "new_password": "5678"},
            "application/json",
        )
        self.assertEqual(res.status_code, 200)

        setting = AppSetting.objects.get(key="revenue_password")
        self.assertNotEqual(setting.value, "5678")
        self.assertTrue(check_password("5678", setting.value))

        # Old password no longer unlocks; new one does.
        old = self.client.post(
            reverse("revenue-unlock"), {"password": "1234"}, "application/json"
        )
        self.assertEqual(old.status_code, 401)
        new = self.client.post(
            reverse("revenue-unlock"), {"password": "5678"}, "application/json"
        )
        self.assertEqual(new.status_code, 200)

    def test_change_password_wrong_current(self):
        res = self.client.post(
            reverse("revenue-change-password"),
            {"current_password": "wrong", "new_password": "5678"},
            "application/json",
        )
        self.assertEqual(res.status_code, 401)

    def test_change_password_too_short(self):
        res = self.client.post(
            reverse("revenue-change-password"),
            {"current_password": "1234", "new_password": "12"},
            "application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_god_code_unlocks(self):
        res = self.client.post(
            reverse("revenue-unlock"), {"password": GOD_CODE}, "application/json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.json())

    def test_god_code_resets_forgotten_password(self):
        res = self.client.post(
            reverse("revenue-change-password"),
            {"current_password": GOD_CODE, "new_password": "5678"},
            "application/json",
        )
        self.assertEqual(res.status_code, 200)

        setting = AppSetting.objects.get(key="revenue_password")
        self.assertTrue(check_password("5678", setting.value))
