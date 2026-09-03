"""Canonical Jalali business-date contracts."""
from datetime import datetime, timezone

from django.test import SimpleTestCase


class JalaliContractTests(SimpleTestCase):
    def test_persian_digits_normalize_and_real_leap_date_validates(self):
        """Breaks if Persian input or Esfand leap-day validation regresses."""
        from internal.jalali import JalaliValidationError, parse_jalali_date

        self.assertEqual(parse_jalali_date("۱۴۰۳/۱۲/۳۰"), "1403-12-30")
        self.assertEqual(parse_jalali_date("1403-12-30"), "1403-12-30")
        with self.assertRaises(JalaliValidationError):
            parse_jalali_date("1402/12/30")

    def test_rejects_noncanonical_dates_and_gregorian_years(self):
        """Breaks if ambiguous widths, impossible days, or Gregorian input pass."""
        from internal.jalali import JalaliValidationError, parse_jalali_date

        for value in (
            "1403/1/01",
            "1403-01/01",
            "1403-07-31",
            "2026-03-21",
            "۱۴۰۳/۱۳/۰۱",
            None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(JalaliValidationError):
                    parse_jalali_date(value)

    def test_month_parser_normalizes_persian_digits_and_rejects_bad_widths(self):
        """Breaks if month filters accept noncanonical or invalid Jalali values."""
        from internal.jalali import JalaliValidationError, parse_jalali_month

        self.assertEqual(parse_jalali_month("۱۴۰۵/۰۶"), "1405-06")
        self.assertEqual(parse_jalali_month("1405-06"), "1405-06")
        for value in ("1405/6", "1405-00", "1405-13", "2026-03"):
            with self.subTest(value=value):
                with self.assertRaises(JalaliValidationError):
                    parse_jalali_month(value)

    def test_tehran_today_uses_local_midnight_and_returns_jalali(self):
        """Breaks if UTC date is used across Tehran's midnight boundary."""
        from internal.jalali import tehran_today

        instant = datetime(2026, 3, 20, 20, 31, tzinfo=timezone.utc)

        self.assertEqual(tehran_today(now=instant), "1405-01-01")

    def test_mutability_rejects_future_and_finalized_jalali_dates(self):
        """Breaks if domain writes can enter the future or a finalized month."""
        from internal.jalali import DateLockedError, assert_mutable_business_date

        self.assertEqual(
            assert_mutable_business_date(
                "۱۴۰۴/۱۲/۲۹", finalized_months=set(), today="1405-01-01"
            ),
            "1404-12-29",
        )
        with self.assertRaises(DateLockedError):
            assert_mutable_business_date(
                "1405-01-02", finalized_months=set(), today="1405-01-01"
            )
        with self.assertRaises(DateLockedError):
            assert_mutable_business_date(
                "1404-12-29", finalized_months={"1404-12"}, today="1405-01-01"
            )
