"""Strict Jalali input normalization and Tehran business-date rules."""
from __future__ import annotations

from datetime import date, datetime, timezone
import re
from collections.abc import Container
from zoneinfo import ZoneInfo


TEHRAN = ZoneInfo("Asia/Tehran")
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
DATE_PATTERN = re.compile(r"^([0-9]{4})([-/])([0-9]{2})\2([0-9]{2})$")
MONTH_PATTERN = re.compile(r"^([0-9]{4})([-/])([0-9]{2})$")
JALALI_BREAKS = (
    -61,
    9,
    38,
    199,
    426,
    686,
    756,
    818,
    1111,
    1181,
    1210,
    1635,
    2060,
    2097,
    2192,
    2262,
    2324,
    2394,
    2456,
    3178,
)


class JalaliValidationError(ValueError):
    """Raised when a business date/month is not canonical Jalali input."""


class DateLockedError(ValueError):
    """Raised when a business date cannot accept domain mutations."""


def _jalali_year_info(year: int) -> tuple[int, int]:
    """Return (leap index, Gregorian March day of Farvardin 1)."""
    if year < JALALI_BREAKS[0] or year >= JALALI_BREAKS[-1]:
        raise JalaliValidationError("Jalali year is unsupported")
    gregorian_year = year + 621
    leap_jalali = -14
    previous = JALALI_BREAKS[0]
    jump = 0
    for boundary in JALALI_BREAKS[1:]:
        jump = boundary - previous
        if year < boundary:
            break
        leap_jalali += (jump // 33) * 8 + (jump % 33) // 4
        previous = boundary
    offset = year - previous
    leap_jalali += (offset // 33) * 8 + ((offset % 33) + 3) // 4
    if jump % 33 == 4 and jump - offset == 4:
        leap_jalali += 1
    leap_gregorian = (
        gregorian_year // 4
        - ((gregorian_year // 100 + 1) * 3) // 4
        - 150
    )
    march_day = 20 + leap_jalali - leap_gregorian
    if jump - offset < 6:
        offset = offset - jump + ((jump + 4) // 33) * 33
    leap = ((offset + 1) % 33 - 1) % 4
    if leap == -1:
        leap = 4
    return leap, march_day


def _is_leap_year(year: int) -> bool:
    return _jalali_year_info(year)[0] == 0


def _validate_year_month(year: int, month: int) -> None:
    if not 1200 <= year <= 1599 or not 1 <= month <= 12:
        raise JalaliValidationError("invalid Jalali year or month")


def _normalize(value: object) -> str:
    if not isinstance(value, str):
        raise JalaliValidationError("Jalali value must be text")
    return value.translate(PERSIAN_DIGITS)


def parse_jalali_date(value: object) -> str:
    """Normalize exact YYYY/MM/DD or YYYY-MM-DD Jalali input to ASCII."""
    matched = DATE_PATTERN.fullmatch(_normalize(value))
    if matched is None:
        raise JalaliValidationError("invalid Jalali date format")
    year, month, day = map(int, (matched[1], matched[3], matched[4]))
    _validate_year_month(year, month)
    month_length = 31 if month <= 6 else 30
    if month == 12 and not _is_leap_year(year):
        month_length = 29
    if not 1 <= day <= month_length:
        raise JalaliValidationError("invalid Jalali day")
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_jalali_month(value: object) -> str:
    """Normalize exact YYYY/MM or YYYY-MM Jalali input to ASCII."""
    matched = MONTH_PATTERN.fullmatch(_normalize(value))
    if matched is None:
        raise JalaliValidationError("invalid Jalali month format")
    year, month = map(int, (matched[1], matched[3]))
    _validate_year_month(year, month)
    return f"{year:04d}-{month:02d}"


def _gregorian_to_jalali(value: date) -> str:
    year = value.year - 621
    _, march_day = _jalali_year_info(year)
    new_year = date(value.year, 3, march_day)
    if value < new_year:
        year -= 1
        _, march_day = _jalali_year_info(year)
        new_year = date(value.year - 1, 3, march_day)
    elapsed = (value - new_year).days
    if elapsed < 186:
        month, day_index = divmod(elapsed, 31)
        month += 1
    else:
        month, day_index = divmod(elapsed - 186, 30)
        month += 7
    return f"{year:04d}-{month:02d}-{day_index + 1:02d}"


def tehran_today(*, now: datetime | None = None) -> str:
    """Return current Tehran civil date as canonical Jalali text."""
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("current instant must be timezone-aware")
    return _gregorian_to_jalali(instant.astimezone(TEHRAN).date())


def assert_mutable_business_date(
    value: object,
    *,
    finalized_months: Container[str] | object,
    today: str | None = None,
) -> str:
    """Normalize a date and reject future or finalized-month mutations."""
    normalized = parse_jalali_date(value)
    current = parse_jalali_date(today) if today is not None else tehran_today()
    month = normalized[:7]
    contains = getattr(finalized_months, "contains", None)
    is_finalized = bool(contains(month)) if callable(contains) else month in finalized_months
    if normalized > current or is_finalized:
        raise DateLockedError("Jalali business date is locked")
    return normalized
