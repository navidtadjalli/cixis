from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from pos.models import AppSetting

GOD_CODE = "open-sesame"
VALID = {
    "god_code": GOD_CODE,
    "s3_access_key": "AKIAEXAMPLE",
    "s3_secret_key": "super-secret-value",
    "s3_bucket": "cixis",
    "s3_endpoint_url": "https://s3.ir-thr-at1.arvanstorage.ir",
    "s3_region": "ir-thr-at1",
}


@patch("pos.views.misc.GOD_CODE_HASH", make_password(GOD_CODE))
class PublishSettingsTests(TestCase):
    def _save(self, **overrides):
        return self.client.post(
            reverse("publish-settings-save"),
            {**VALID, **overrides},
            "application/json",
        )

    def _unlock(self, god_code=GOD_CODE):
        return self.client.post(
            reverse("publish-settings-unlock"),
            {"god_code": god_code},
            "application/json",
        )

    def test_unlock_rejects_wrong_god_code(self):
        self.assertEqual(self._unlock("nope").status_code, 401)

    def test_save_rejects_wrong_god_code(self):
        self.assertEqual(self._save(god_code="nope").status_code, 401)
        self.assertFalse(AppSetting.objects.filter(key="s3_bucket").exists())

    def test_save_persists_all_five_settings(self):
        self.assertEqual(self._save().status_code, 200)

        stored = dict(AppSetting.objects.values_list("key", "value"))
        self.assertEqual(stored["s3_access_key"], "AKIAEXAMPLE")
        self.assertEqual(stored["s3_secret_key"], "super-secret-value")
        self.assertEqual(stored["s3_bucket"], "cixis")
        self.assertEqual(stored["s3_region"], "ir-thr-at1")

    def test_unlock_masks_credentials_but_not_bucket(self):
        self._save()

        body = self._unlock().json()

        self.assertEqual(body["settings"]["s3_secret_key"], "•" * 14 + "alue")
        self.assertEqual(body["settings"]["s3_access_key"], "•" * 7 + "MPLE")
        self.assertEqual(body["settings"]["s3_bucket"], "cixis")
        self.assertTrue(body["configured"])
        self.assertEqual(
            body["website_url"], "https://cixis.s3-website.ir-thr-at1.arvanstorage.ir"
        )

    def test_blank_credential_keeps_the_stored_one(self):
        self._save()

        self._save(s3_secret_key="", s3_access_key="", s3_bucket="renamed")

        stored = dict(AppSetting.objects.values_list("key", "value"))
        self.assertEqual(stored["s3_secret_key"], "super-secret-value")
        self.assertEqual(stored["s3_access_key"], "AKIAEXAMPLE")
        self.assertEqual(stored["s3_bucket"], "renamed")

    def test_blank_bucket_is_rejected(self):
        res = self._save(s3_bucket="")

        self.assertEqual(res.status_code, 400)
        self.assertIn("s3_bucket", res.json()["detail"])

    def test_endpoint_url_must_be_http(self):
        res = self._save(s3_endpoint_url="s3.example.ir")

        self.assertEqual(res.status_code, 400)
        self.assertFalse(AppSetting.objects.filter(key="s3_bucket").exists())

    def test_unconfigured_state_reports_no_website_url(self):
        body = self._unlock().json()

        self.assertFalse(body["configured"])
        self.assertEqual(body["website_url"], "")
        self.assertFalse(body["sync_enabled"])
