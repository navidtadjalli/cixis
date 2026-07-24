"""Shift math for the CiXiS staff tracker.

Pure functions over (shift, is_full_day, check_in, check_out) so the report
aggregation and the tests can share one source of truth. All times are
wall-clock ``datetime.time``; results are whole minutes.

Shift bounds (minutes from the business date's midnight):
- morning  09:00 -> 17:00   (540  -> 1020)
- evening  16:00 -> 00:00+1 (960  -> 1440)
- full day 09:00 -> 00:00+1 (540  -> 1440), and counts as two shifts

A check-out at or before the check-in is read as the next day (e.g. 14:00 ->
02:00), so overtime past a midnight end is measured correctly.
"""
from datetime import time

MORNING = "morning"
EVENING = "evening"

# (start, end) in minutes from midnight of the business date.
_BOUNDS = {
    MORNING: (9 * 60, 17 * 60),
    EVENING: (16 * 60, 24 * 60),
}
_FULL_DAY_BOUNDS = (9 * 60, 24 * 60)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def shift_bounds(shift: str, is_full_day: bool) -> tuple[int, int]:
    """Return (start, end) minutes-from-midnight for a shift record."""
    if is_full_day:
        return _FULL_DAY_BOUNDS
    return _BOUNDS.get(shift, _BOUNDS[MORNING])


def shift_count(is_full_day: bool) -> int:
    """A full day is worth two shifts in the monthly tally."""
    return 2 if is_full_day else 1


def compute(shift: str, is_full_day: bool, check_in: time, check_out: time) -> dict:
    """Late / early / overtime minutes + shift count for one attendance row.

    - late     = minutes the check-in fell after the shift start (0 if on time/early)
    - early    = minutes the check-in fell before the shift start (0 if late/on time)
    - overtime = minutes the check-out ran past the shift end (0 if none)
    """
    start, end = shift_bounds(shift, is_full_day)
    ci = _minutes(check_in)
    co = _minutes(check_out)
    # A check-out not strictly after the check-in belongs to the next day.
    if co <= ci:
        co += 24 * 60

    return {
        "late_minutes": max(0, ci - start),
        "early_minutes": max(0, start - ci),
        "overtime_minutes": max(0, co - end),
        "shift_count": shift_count(is_full_day),
    }
