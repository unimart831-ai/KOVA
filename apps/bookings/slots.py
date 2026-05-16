"""Slot-availability engine for BookingLinks.

Given a BookingLink, a date, and a service duration, return the
list of free start times for that day.

Algorithm:
  1. Build the day's working windows from BookingLink.working_hours
  2. Apply advance_notice (drop slots starting before now + notice)
  3. Apply max_advance_days (refuse the day if too far out)
  4. Subtract intervals already booked (status in pending/confirmed)
  5. Emit slots at duration_minutes granularity that fit inside the
     remaining gaps

This is intentionally simple — no per-staff resource pool, no
overlap tolerance. One BookingLink, one calendar.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

from django.utils import timezone

from apps.bookings.models import Booking, BookingLink


_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_hhmm(s: str) -> time:
    """'09:30' → time(9, 30). Returns time(0,0) on bad input."""
    try:
        h, m = s.split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return time(0, 0)


def _windows_for_date(link: BookingLink, on_date: date) -> list[tuple[datetime, datetime]]:
    """Return list of (open, close) datetimes for the given date.

    Uses the user's TZ if available; falls back to default.
    """
    key = _WEEKDAY_KEYS[on_date.weekday()]
    raw = (link.working_hours or {}).get(key, [])
    if not raw:
        return []

    out: list[tuple[datetime, datetime]] = []
    tz = timezone.get_current_timezone()
    for w in raw:
        start = _parse_hhmm(w.get("start", "00:00"))
        end = _parse_hhmm(w.get("end", "00:00"))
        open_dt = timezone.make_aware(datetime.combine(on_date, start), tz)
        close_dt = timezone.make_aware(datetime.combine(on_date, end), tz)
        if close_dt > open_dt:
            out.append((open_dt, close_dt))
    return out


def _booked_intervals(link: BookingLink, on_date: date) -> list[tuple[datetime, datetime]]:
    """Existing bookings on this date — anything pending/confirmed blocks the slot."""
    day_start = timezone.make_aware(
        datetime.combine(on_date, time(0, 0)),
        timezone.get_current_timezone(),
    )
    day_end = day_start + timedelta(days=1)
    qs = Booking.objects.filter(
        booking_link=link,
        status__in=[Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        scheduled_at__gte=day_start,
        scheduled_at__lt=day_end,
    ).values_list("scheduled_at", "duration_minutes")
    return [(start, start + timedelta(minutes=dur or 0)) for start, dur in qs]


def _subtract_busy(
    windows: list[tuple[datetime, datetime]],
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Subtract a list of busy intervals from a list of open windows."""
    if not busy:
        return list(windows)
    busy_sorted = sorted(busy, key=lambda b: b[0])
    result: list[tuple[datetime, datetime]] = []
    for w_start, w_end in windows:
        cursor = w_start
        for b_start, b_end in busy_sorted:
            if b_end <= cursor or b_start >= w_end:
                continue
            if b_start > cursor:
                result.append((cursor, b_start))
            cursor = max(cursor, b_end)
            if cursor >= w_end:
                break
        if cursor < w_end:
            result.append((cursor, w_end))
    return result


def free_slots(
    link: BookingLink,
    on_date: date,
    duration_minutes: int,
    granularity_minutes: int = 30,
) -> list[datetime]:
    """Return the list of free start datetimes on `on_date` that fit
    a `duration_minutes` booking.

    Slots are emitted at `granularity_minutes` increments — so a 180-min
    booking on a 30-min-granularity day shows up as 09:00, 09:30, 10:00,…
    each as a candidate start, as long as the full block fits.
    """
    if not link.is_active:
        return []

    now = timezone.now()
    earliest = now + timedelta(minutes=link.advance_notice_minutes)
    latest = now + timedelta(days=link.max_advance_days)

    # Reject the whole day if outside the booking horizon
    day_start = timezone.make_aware(
        datetime.combine(on_date, time(0, 0)),
        timezone.get_current_timezone(),
    )
    if day_start.date() > latest.date():
        return []

    windows = _windows_for_date(link, on_date)
    if not windows:
        return []

    busy = _booked_intervals(link, on_date)
    free_windows = _subtract_busy(windows, busy)

    slots: list[datetime] = []
    step = timedelta(minutes=granularity_minutes)
    duration = timedelta(minutes=duration_minutes)
    for w_start, w_end in free_windows:
        # Snap to the granularity grid
        candidate = w_start
        while candidate + duration <= w_end:
            if candidate >= earliest:
                slots.append(candidate)
            candidate += step
    return slots
