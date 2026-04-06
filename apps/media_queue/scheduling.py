"""
Scheduling utilities for the Media Queue.

Calculates when each queued item should be published based on
the queue's rhythm settings (daily or weekly).
"""

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_tz

from .models import MediaQueue, QueueItem

logger = logging.getLogger(__name__)


def recalculate_schedule(queue: MediaQueue):
    """
    Assign scheduled_for to all QUEUED items based on the queue's rhythm.

    Called when:
    - Items are added, removed, or reordered
    - Rhythm settings change
    - An item is published (to advance the remainder)
    """
    items = list(
        queue.items
        .filter(status=QueueItem.Status.QUEUED)
        .order_by("order", "created_at")
    )
    if not items:
        return

    try:
        user_tz = ZoneInfo(queue.timezone)
    except (ZoneInfoNotFoundError, KeyError):
        user_tz = ZoneInfo("UTC")

    now = dj_tz.now().astimezone(user_tz)
    slots = _build_slot_iterator(queue, now, user_tz)

    for item in items:
        slot_dt = next(slots)
        item.scheduled_for = slot_dt
    QueueItem.objects.bulk_update(items, ["scheduled_for"])

    logger.info(
        "Recalculated schedule for queue %s: %d items, next at %s",
        queue.id, len(items), items[0].scheduled_for if items else "N/A",
    )


def _build_slot_iterator(queue: MediaQueue, start: datetime, user_tz):
    """
    Yield an infinite sequence of upcoming publish datetimes
    based on the queue's rhythm.
    """
    if queue.rhythm_type == MediaQueue.RhythmType.WEEKLY:
        yield from _weekly_slots(queue, start, user_tz)
    else:
        yield from _daily_slots(queue, start, user_tz)


def _daily_slots(queue: MediaQueue, start: datetime, user_tz):
    """
    Daily rhythm: post at each time_slot on each active_day.
    time_slots: ["09:00", "13:00", "18:00"]
    active_days: [0,1,2,3,4] (Mon-Fri). Empty = every day.
    """
    times = sorted(_parse_times(queue.time_slots))
    if not times:
        times = [time(9, 0)]  # Default: 9am

    active_days = set(queue.active_days) if queue.active_days else set(range(7))
    day = start.date()

    while True:
        if day.weekday() in active_days:
            for t in times:
                slot = datetime.combine(day, t, tzinfo=user_tz)
                if slot > start:
                    yield slot
        day += timedelta(days=1)


def _weekly_slots(queue: MediaQueue, start: datetime, user_tz):
    """
    Weekly rhythm: explicit (day, time) pairs.
    time_slots: [{"day": 0, "time": "09:00"}, {"day": 2, "time": "14:00"}]
    """
    raw = queue.time_slots or []
    week_slots = []
    for entry in raw:
        if isinstance(entry, dict):
            d = int(entry.get("day", 0))
            t = _parse_time_str(entry.get("time", "09:00"))
            week_slots.append((d, t))
    week_slots.sort()

    if not week_slots:
        week_slots = [(0, time(9, 0))]  # Default: Monday 9am

    # Start from current week's Monday
    monday = start.date() - timedelta(days=start.date().weekday())
    week_offset = 0

    while True:
        for day_num, t in week_slots:
            slot_date = monday + timedelta(days=day_num + week_offset * 7)
            slot = datetime.combine(slot_date, t, tzinfo=user_tz)
            if slot > start:
                yield slot
        week_offset += 1


def _parse_times(slots) -> list[time]:
    """Parse time strings from time_slots JSON."""
    result = []
    for s in (slots or []):
        if isinstance(s, str):
            result.append(_parse_time_str(s))
        elif isinstance(s, dict) and "time" in s:
            result.append(_parse_time_str(s["time"]))
    return result


def _parse_time_str(s: str) -> time:
    """Parse 'HH:MM' string to a time object."""
    try:
        parts = s.strip().split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (ValueError, IndexError):
        return time(9, 0)
