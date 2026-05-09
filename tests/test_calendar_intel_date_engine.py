"""
Unit tests for apps.calendar_intel.date_engine.

Verifies:
  - Fixed dates (Christmas, Liberation Day)
  - Nth-weekday (Mother's Day, Father's Day, Thanksgiving)
  - Easter computation (known historical years)
  - Easter-relative offsets (Good Friday, Easter Monday)
  - Custom functions (Black Friday, Cyber Monday)
  - Hijri (skipped if hijri-converter not installed)
  - Error handling for malformed configs
"""
from datetime import date

import pytest

from apps.calendar_intel.date_engine import (
    DateComputationError,
    compute_easter,
    compute_occurrences,
)


# ──────────────────────────────────────────────────────────────────────────
# Fixed dates
# ──────────────────────────────────────────────────────────────────────────
def test_fixed_christmas_day():
    assert compute_occurrences("fixed", {"month": 12, "day": 25}, 2026) == [date(2026, 12, 25)]


def test_fixed_new_years_day():
    assert compute_occurrences("fixed", {"month": 1, "day": 1}, 2027) == [date(2027, 1, 1)]


def test_fixed_rwanda_liberation_day():
    assert compute_occurrences("fixed", {"month": 7, "day": 4}, 2026) == [date(2026, 7, 4)]


def test_fixed_invalid_date_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("fixed", {"month": 13, "day": 1}, 2026)


def test_fixed_missing_keys_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("fixed", {"month": 12}, 2026)


# ──────────────────────────────────────────────────────────────────────────
# Nth weekday of a month
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("year,expected", [
    (2024, date(2024, 5, 12)),   # 2nd Sunday of May 2024
    (2025, date(2025, 5, 11)),
    (2026, date(2026, 5, 10)),
    (2027, date(2027, 5, 9)),
])
def test_mothers_day_us(year, expected):
    """Mother's Day = 2nd Sunday of May. weekday=6 (Sunday), n=2."""
    result = compute_occurrences("nth_weekday", {"month": 5, "weekday": 6, "n": 2}, year)
    assert result == [expected]


@pytest.mark.parametrize("year,expected", [
    (2024, date(2024, 6, 16)),   # 3rd Sunday of June
    (2025, date(2025, 6, 15)),
    (2026, date(2026, 6, 21)),
])
def test_fathers_day_us(year, expected):
    result = compute_occurrences("nth_weekday", {"month": 6, "weekday": 6, "n": 3}, year)
    assert result == [expected]


@pytest.mark.parametrize("year,expected", [
    (2024, date(2024, 11, 28)),  # 4th Thursday of November
    (2025, date(2025, 11, 27)),
    (2026, date(2026, 11, 26)),
])
def test_us_thanksgiving(year, expected):
    """Thanksgiving = 4th Thursday of November. weekday=3 (Thursday)."""
    result = compute_occurrences("nth_weekday", {"month": 11, "weekday": 3, "n": 4}, year)
    assert result == [expected]


def test_last_friday_of_month():
    """n=-1 means last weekday of the month."""
    # Last Friday of November 2026 = 27th
    result = compute_occurrences("nth_weekday", {"month": 11, "weekday": 4, "n": -1}, 2026)
    assert result == [date(2026, 11, 27)]


def test_nth_weekday_invalid_weekday_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("nth_weekday", {"month": 5, "weekday": 7, "n": 2}, 2026)


def test_nth_weekday_n_zero_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("nth_weekday", {"month": 5, "weekday": 6, "n": 0}, 2026)


# ──────────────────────────────────────────────────────────────────────────
# Easter (Computus algorithm)
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("year,expected", [
    # Known historical Western Easter dates
    (2024, date(2024, 3, 31)),
    (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)),
    (2027, date(2027, 3, 28)),
    (2028, date(2028, 4, 16)),
    (2030, date(2030, 4, 21)),
])
def test_easter_known_dates(year, expected):
    assert compute_easter(year) == expected


def test_good_friday_is_two_days_before_easter():
    """Good Friday = Easter - 2."""
    result = compute_occurrences("computed_easter", {"offset_days": -2}, 2026)
    assert result == [date(2026, 4, 3)]   # 2026 Easter is Apr 5


def test_easter_monday_is_one_day_after():
    result = compute_occurrences("computed_easter", {"offset_days": 1}, 2026)
    assert result == [date(2026, 4, 6)]


def test_easter_sunday_zero_offset():
    result = compute_occurrences("computed_easter", {"offset_days": 0}, 2026)
    assert result == [date(2026, 4, 5)]


def test_ash_wednesday_offset():
    """Ash Wednesday = Easter - 46 (start of Lent)."""
    result = compute_occurrences("computed_easter", {"offset_days": -46}, 2026)
    # 2026 Easter Apr 5 - 46 days = Feb 18
    assert result == [date(2026, 2, 18)]


# ──────────────────────────────────────────────────────────────────────────
# Custom functions
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("year,expected", [
    (2024, date(2024, 11, 29)),   # day after 2024 Thanksgiving (Nov 28)
    (2025, date(2025, 11, 28)),
    (2026, date(2026, 11, 27)),
])
def test_black_friday(year, expected):
    result = compute_occurrences(
        "custom_function", {"function_name": "friday_after_thanksgiving"}, year,
    )
    assert result == [expected]


@pytest.mark.parametrize("year,expected", [
    (2024, date(2024, 12, 2)),    # Monday after Black Friday
    (2025, date(2025, 12, 1)),
    (2026, date(2026, 11, 30)),
])
def test_cyber_monday(year, expected):
    result = compute_occurrences(
        "custom_function",
        {"function_name": "monday_after_friday_after_thanksgiving"},
        year,
    )
    assert result == [expected]


def test_unknown_custom_function_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences(
            "custom_function", {"function_name": "nonexistent_function"}, 2026,
        )


def test_custom_function_missing_name_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("custom_function", {}, 2026)


# ──────────────────────────────────────────────────────────────────────────
# Hijri (Islamic) — only run if library installed
# ──────────────────────────────────────────────────────────────────────────
hijri_converter = pytest.importorskip("hijri_converter")


def test_eid_al_fitr_returns_dates():
    """Eid al-Fitr (1 Shawwal). Don't assert exact dates — they shift by region."""
    result = compute_occurrences(
        "lunar_islamic", {"hijri_month": 10, "hijri_day": 1}, 2026,
    )
    assert len(result) >= 1
    assert all(isinstance(d, date) and d.year == 2026 for d in result)


def test_eid_al_adha_returns_dates():
    result = compute_occurrences(
        "lunar_islamic", {"hijri_month": 12, "hijri_day": 10}, 2026,
    )
    assert len(result) >= 1
    assert all(d.year == 2026 for d in result)


def test_hijri_invalid_config_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("lunar_islamic", {"hijri_month": "bad"}, 2026)


# ──────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────
def test_unknown_date_type_raises():
    with pytest.raises(DateComputationError):
        compute_occurrences("flubberbustle", {}, 2026)


def test_lunar_chinese_returns_empty_for_now():
    """Phase 4 feature — placeholder returns empty list, not error."""
    assert compute_occurrences("lunar_chinese", {}, 2026) == []
