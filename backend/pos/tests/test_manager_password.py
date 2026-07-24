"""Tests for the manager password tier and its interaction with other tiers."""
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse

from pos.models import AppSetting

GOD_CODE = "open-sesame"


@patch("pos.views.misc.GOD_CODE_HASH", make_password(GOD_CODE))
class ManagerPasswordTests(TestCase):
    def setUp(self):
        AppSetting.objects.create(
            key="revenue_password", value=make_password("1234")
        )

    def test_unlock_with_default_flags_must_change(self):
        res = self.client.post(
            reverse("manager-unlock"), {"password": "0000"}, "application/json"
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("token", body)
        self.assertTrue(body["must_change"])

    def test_wrong_password_rejected(self):
        res = self.client.post(
            reverse("manager-unlock"), {"password": "nope"}, "application/json"
        )
        self.assertEqual(res.status_code, 401)

    def test_god_code_unlocks_manager(self):
        res = self.client.post(
            reverse("manager-unlock"), {"password": GOD_CODE}, "application/json"
        )
        self.assertEqual(res.status_code, 200)

    def test_change_clears_must_change_and_rotates(self):
        res = self.client.post(
            reverse("manager-change-password"),
            {"current_password": "0000", "new_password": "5678"},
            "application/json",
        )
        self.assertEqual(res.status_code, 200)

        setting = AppSetting.objects.get(key="manager_password")
        self.assertTrue(check_password("5678", setting.value))
        self.assertEqual(
            AppSetting.objects.get(key="manager_password_changed").value, "1"
        )

        after = self.client.post(
            reverse("manager-unlock"), {"password": "5678"}, "application/json"
        )
        self.assertFalse(after.json()["must_change"])
        old = self.client.post(
            reverse("manager-unlock"), {"password": "0000"}, "application/json"
        )
        self.assertEqual(old.status_code, 401)

    def test_god_code_resets_forgotten_manager_password(self):
        res = self.client.post(
            reverse("manager-change-password"),
            {"current_password": GOD_CODE, "new_password": "5678"},
            "application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            check_password(
                "5678", AppSetting.objects.get(key="manager_password").value
            )
        )

    def test_manager_password_also_unlocks_revenue_tier(self):
        # The manager's code works everywhere the supervisor's does (closing/entry).
        self.client.post(
            reverse("manager-change-password"),
            {"current_password": "0000", "new_password": "5678"},
            "application/json",
        )
        res = self.client.post(
            reverse("revenue-unlock"), {"password": "5678"}, "application/json"
        )
        self.assertEqual(res.status_code, 200)

    def test_revenue_password_does_not_unlock_manager_report(self):
        # Supervisor's password must NOT open the manager-only report tab.
        res = self.client.post(
            reverse("manager-unlock"), {"password": "1234"}, "application/json"
        )
        self.assertEqual(res.status_code, 401)
