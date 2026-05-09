"""
Date computation engine for Holidays.

Given a Holiday's `date_type` and `date_config`, returns one or more
Gregorian dates for any year. See KOVA_HOLIDAY_AWARENESS.md §8.

Date types supported:
  - fixed: same Gregorian date every year (Christmas, Liberation Day)
  - nth_weekday: e.g., 2nd Sunday of May (Mother's Day US)
  - computed_easter: Easter + offset (Good Friday, Easter Monday)
  - lunar_islamic: Hijri calendar (Eid al-Fitr, Eid al-Adha)
  - lunar_chinese: Chinese lunar (Lunar New Year) — Phase 4
  - custom_function: registered named functions for special cases

The output is always a list of `date` objects to handle holidays that
straddle the Gregorian year (Hijri shifts ~11 days/year, so a holiday
can fall twice in one Gregorian year).
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from typing import Callable

logger = logging.getLogger(__name__)


class DateComputationError(Exception):
    """Raised when a holiday's date_config is malformed or computation fails."""


# ──────────────────────────────────────────────────────────────────────────
# Fixed dates
# ──────────────────────────────────────────────────────────────────────────
def compute_fixed(config: dict, year: int) -> list[date]:
    """{'month': 12, 'day': 25} → Christmas Day."""
    try:
        return [date(year, int(config["month"]), int(config["day"]))]
    except (KeyError, ValueError, TypeError) as exc:
        raise DateComputationError(f"Invalid fixed date config {config}: {exc}") from exc


# ──────────────────────────────────────────────────────────────────────────
# Nth weekday of a month
# ──────────────────────────────────────────────────────────────────────────
def compute_nth_weekday(config: dict, year: int) -> list[date]:
    """
    {'month': 5, 'weekday': 6, 'n': 2} → 2nd Sunday of May.

    weekday: 0=Monday … 6=Sunday (calendar module convention)
    n: 1=first, 2=second, … -1=last
    """
    try:
        month = int(config["month"])
        weekday = int(config["weekday"])
        n = int(config["n"])
    except (KeyError, ValueError, TypeError) as exc:
        raise DateComputationError(f"Invalid nth_weekday config {config}: {exc}") from exc

    if not (0 <= weekday <= 6):
        raise DateComputationError(f"weekday must be 0-6, got {weekday}")
    if not (1 <= month <= 12):
        raise DateComputationError(f"month must be 1-12, got {month}")
    if n == 0:
        raise DateComputationError("n must be non-zero")

    matching_days = [
        week[weekday]
        for week in calendar.monthcalendar(year, month)
        if week[weekday] != 0
    ]
    if not matching_days:
        raise DateComputationError(
            f"No weekday={weekday} occurrences in {year}-{month:02d}"
        )

    try:
        day = matching_days[n - 1] if n > 0 else matching_days[n]
    except IndexError as exc:
        raise DateComputationError(
            f"n={n} out of range; only {len(matching_days)} {weekday}s in {year}-{month:02d}"
        ) from exc

    return [date(year, month, day)]


# ──────────────────────────────────────────────────────────────────────────
# Easter (Anonymous Gregorian / Computus algorithm)
# ──────────────────────────────────────────────────────────────────────────
def compute_easter(year: int) -> date:
    """Return Western (Gregorian) Easter Sunday for the given year.
    Anonymous Gregorian algorithm — pure integer math, no library needed."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def compute_easter_offset(config: dict, year: int) -> list[date]:
    """{'offset_days': -2} → Good Friday (Easter - 2 days)."""
    try:
        offset = int(config.get("offset_days", 0))
    except (ValueError, TypeError) as exc:
        raise DateComputationError(f"Invalid offset_days in {config}: {exc}") from exc
    return [compute_easter(year) + timedelta(days=offset)]


# ──────────────────────────────────────────────────────────────────────────
# Hijri (Islamic) calendar
# ──────────────────────────────────────────────────────────────────────────
def compute_hijri(config: dict, year: int) -> list[date]:
    """
    {'hijri_month': 10, 'hijri_day': 1} → Eid al-Fitr.

    The Hijri year is ~11 days shorter than Gregorian, so a Hijri holiday
    can fall twice in one Gregorian year. We try multiple Hijri years and
    return all occurrences within the target Gregorian year.

    NOTE: Hijri dates depend on lunar sighting in some traditions; published
    dates are best-estimate. Surface the caveat in the UI.
    """
    try:
        from hijri_converter import Hijri, Gregorian
    except ImportError:
        logger.warning("hijri-converter not installed; skipping Hijri computation")
        return []

    try:
        h_month = int(config["hijri_month"])
        h_day = int(config["hijri_day"])
    except (KeyError, ValueError, TypeError) as exc:
        raise DateComputationError(f"Invalid lunar_islamic config {config}: {exc}") from exc

    # Determine candidate Hijri years that overlap with the Gregorian target year.
    # The Hijri year corresponding to a given Gregorian year can be approximated
    # by converting Jan 1 and Dec 31 of that year, then trying both years.
    try:
        h_start = Gregorian(year, 1, 1).to_hijri().year
        h_end = Gregorian(year, 12, 31).to_hijri().year
    except Exception as exc:
        logger.warning("Hijri year resolution failed for %s: %s", year, exc)
        return []

    candidates = list(range(h_start, h_end + 1))
    occurrences: list[date] = []
    for h_year in candidates:
        try:
            g = Hijri(h_year, h_month, h_day).to_gregorian()
            d = date(g.year, g.month, g.day)
            if d.year == year:
                occurrences.append(d)
        except Exception as exc:
            # Some Hijri month/day combos are invalid in some years (e.g., 30th day
            # of a 29-day month). Skip silently.
            logger.debug("Hijri %s-%s-%s skipped: %s", h_year, h_month, h_day, exc)
            continue

    return sorted(occurrences)


# ──────────────────────────────────────────────────────────────────────────
# Custom functions (registered by name)
# ──────────────────────────────────────────────────────────────────────────
_CUSTOM_FUNCTIONS: dict[str, Callable[[int], list[date]]] = {}


def register_custom_function(name: str):
    """Decorator to register a custom date function by name.
    Usage:
        @register_custom_function("friday_after_thanksgiving")
        def black_friday(year: int) -> list[date]: ...
    """
    def wrap(fn: Callable[[int], list[date]]):
        _CUSTOM_FUNCTIONS[name] = fn
        return fn
    return wrap


@register_custom_function("friday_after_thanksgiving")
def _friday_after_thanksgiving(year: int) -> list[date]:
    """Black Friday — day after US Thanksgiving (4th Thursday of November)."""
    thanksgiving = compute_nth_weekday({"month": 11, "weekday": 3, "n": 4}, year)[0]
    return [thanksgiving + timedelta(days=1)]


@register_custom_function("monday_after_friday_after_thanksgiving")
def _cyber_monday(year: int) -> list[date]:
    """Cyber Monday — Monday after Black Friday."""
    return [_friday_after_thanksgiving(year)[0] + timedelta(days=3)]


def compute_custom(config: dict, year: int) -> list[date]:
    """{'function_name': 'friday_after_thanksgiving'}"""
    name = config.get("function_name")
    if not name:
        raise DateComputationError(f"custom_function requires 'function_name': {config}")
    fn = _CUSTOM_FUNCTIONS.get(name)
    if not fn:
        raise DateComputationError(f"Unknown custom function: {name!r}")
    return fn(year)


# ──────────────────────────────────────────────────────────────────────────
# Public dispatcher
# ──────────────────────────────────────────────────────────────────────────
_DISPATCH = {
    "fixed": compute_fixed,
    "nth_weekday": compute_nth_weekday,
    "computed_easter": compute_easter_offset,
    "lunar_islamic": compute_hijri,
    "custom_function": compute_custom,
}


def compute_occurrences(date_type: str, date_config: dict, year: int) -> list[date]:
    """
    Public entry point. Returns 0+ Gregorian dates for a holiday in `year`.

    Returns an empty list rather than raising for known limitations
    (e.g., Hijri converter not installed) so callers can continue
    seeding other holidays. Raises DateComputationError only on
    malformed config.
    """
    fn = _DISPATCH.get(date_type)
    if not fn:
        # lunar_chinese is reserved but not implemented in Phase 1
        if date_type == "lunar_chinese":
            logger.info("lunar_chinese not yet implemented; skipping")
            return []
        raise DateComputationError(f"Unknown date_type: {date_type!r}")
    return fn(date_config, year)
