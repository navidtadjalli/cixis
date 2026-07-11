from unittest.mock import Mock, patch

from django.test import TestCase

from pos.models import AppSetting, DayClosing, SyncRecord
from pos import services
from pos.sync import retry_pending, sync_day_closing_async


class SyncTests(TestCase):
    def setUp(self):
        self.day_closing = DayClosing.objects.create(
            business_date=services.business_today(),
            total_sales=500,
            cash_total=100,
            card_total=300,
            bank_transfer_total=100,
            orders_count=3,
            closed_orders_count=3,
            open_orders_count=0,
            table_usage_count=2,
            purchases_total=50,
        )

    def _enable_sync(self):
        AppSetting.objects.update_or_create(
            key="sync_enabled", defaults={"value": "true"}
        )

    def test_sync_disabled_marks_local_only_and_queues_nothing(self):
        sync_day_closing_async(self.day_closing)

        self.day_closing.refresh_from_db()
        self.assertEqual(
            self.day_closing.sync_status, DayClosing.SyncStatus.LOCAL_ONLY
        )
        self.assertFalse(SyncRecord.objects.exists())

    def test_retry_pending_is_a_noop_while_sync_is_disabled(self):
        self._enable_sync()
        sync_day_closing_async(self.day_closing)
        AppSetting.objects.filter(key="sync_enabled").update(value="false")

        self.assertEqual(retry_pending(), {"synced": 0, "failed": 0, "total": 0})
        record = SyncRecord.objects.get(local_object_id=self.day_closing.id)
        self.assertEqual(record.attempt_count, 0)

    def test_no_remote_async_leaves_day_closing_pending_and_creates_sync_record(self):
        self._enable_sync()

        sync_day_closing_async(self.day_closing)

        self.day_closing.refresh_from_db()
        self.assertEqual(self.day_closing.sync_status, DayClosing.SyncStatus.PENDING)
        record = SyncRecord.objects.get(local_object_id=self.day_closing.id)
        self.assertEqual(record.status, SyncRecord.Status.PENDING)
        self.assertEqual(record.attempt_count, 0)

    def test_retry_pending_increments_attempt_count_without_remote(self):
        self._enable_sync()
        sync_day_closing_async(self.day_closing)

        result = retry_pending()

        self.assertEqual(result["failed"], 1)
        record = SyncRecord.objects.get(local_object_id=self.day_closing.id)
        self.assertEqual(record.attempt_count, 1)
        self.assertEqual(record.status, SyncRecord.Status.FAILED)

    @patch("pos.sync.requests.post")
    def test_retry_pending_success_marks_record_and_day_closing_synced(self, post):
        self._enable_sync()
        sync_day_closing_async(self.day_closing)
        AppSetting.objects.create(key="remote_server_url", value="https://example.test")
        AppSetting.objects.create(key="api_key", value="secret")
        post.return_value = Mock(status_code=201)

        result = retry_pending()

        self.assertEqual(result["synced"], 1)
        record = SyncRecord.objects.get(local_object_id=self.day_closing.id)
        self.assertEqual(record.status, SyncRecord.Status.SYNCED)
        self.assertEqual(record.attempt_count, 1)
        self.day_closing.refresh_from_db()
        self.assertEqual(self.day_closing.sync_status, DayClosing.SyncStatus.SYNCED)
        self.assertIsNotNone(self.day_closing.synced_at)
