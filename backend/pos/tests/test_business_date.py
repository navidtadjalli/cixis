"""Business-date rollover honors the late-night cutoff (Ramadan use case)."""
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from pos import services


def _local(year, month, day, hour):
    """A tz-aware local datetime in the project timezone."""
    return timezone.make_aware(datetime(year, month, day, hour, 0))


@override_settings(BUSINESS_DAY_START_HOUR=6)
class BusinessTodayCutoffTests(TestCase):
    def test_after_midnight_before_cutoff_stays_previous_day(self):
        """02:00 (cafe still open) counts as the day that started yesterday."""
        with patch.object(
            timezone, "localtime", return_value=_local(2026, 6, 18, 2)
        ):
            self.assertEqual(services.business_today().isoformat(), "2026-06-17")

    def test_at_cutoff_hour_rolls_to_new_day(self):
        with patch.object(
            timezone, "localtime", return_value=_local(2026, 6, 18, 6)
        ):
            self.assertEqual(services.business_today().isoformat(), "2026-06-18")

    def test_evening_is_same_calendar_day(self):
        with patch.object(
            timezone, "localtime", return_value=_local(2026, 6, 18, 20)
        ):
            self.assertEqual(services.business_today().isoformat(), "2026-06-18")

    @override_settings(BUSINESS_DAY_START_HOUR=0)
    def test_zero_cutoff_matches_calendar_date(self):
        with patch.object(
            timezone, "localtime", return_value=_local(2026, 6, 18, 2)
        ):
            self.assertEqual(services.business_today().isoformat(), "2026-06-18")
