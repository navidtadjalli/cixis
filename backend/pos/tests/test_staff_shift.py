"""Unit tests for the staff shift math (late / early / overtime / full-day)."""
from datetime import time

from django.test import TestCase

from pos import staff_shift


class StaffShiftComputeTests(TestCase):
    def test_morning_on_time(self):
        m = staff_shift.compute("morning", False, time(9, 0), time(17, 0))
        self.assertEqual(m["late_minutes"], 0)
        self.assertEqual(m["early_minutes"], 0)
        self.assertEqual(m["overtime_minutes"], 0)
        self.assertEqual(m["shift_count"], 1)

    def test_morning_late_and_overtime(self):
        m = staff_shift.compute("morning", False, time(9, 30), time(18, 0))
        self.assertEqual(m["late_minutes"], 30)
        self.assertEqual(m["early_minutes"], 0)
        self.assertEqual(m["overtime_minutes"], 60)

    def test_early_arrival_is_tracked(self):
        m = staff_shift.compute("morning", False, time(8, 0), time(17, 0))
        self.assertEqual(m["early_minutes"], 60)
        self.assertEqual(m["late_minutes"], 0)

    def test_evening_early_in_and_over_past_midnight(self):
        # Came at 14:00 (shift starts 16:00) and left at 02:00 (ends 00:00).
        m = staff_shift.compute("evening", False, time(14, 0), time(2, 0))
        self.assertEqual(m["early_minutes"], 120)
        self.assertEqual(m["late_minutes"], 0)
        self.assertEqual(m["overtime_minutes"], 120)
        self.assertEqual(m["shift_count"], 1)

    def test_full_day_counts_as_two_shifts(self):
        m = staff_shift.compute("morning", True, time(9, 0), time(0, 0))
        self.assertEqual(m["shift_count"], 2)
        self.assertEqual(m["late_minutes"], 0)
        self.assertEqual(m["early_minutes"], 0)
        self.assertEqual(m["overtime_minutes"], 0)

    def test_full_day_late_and_overtime(self):
        # Full day 09:00->00:00 bounds; arrived 09:15, left 02:00.
        m = staff_shift.compute("morning", True, time(9, 15), time(2, 0))
        self.assertEqual(m["late_minutes"], 15)
        self.assertEqual(m["overtime_minutes"], 120)
        self.assertEqual(m["shift_count"], 2)
