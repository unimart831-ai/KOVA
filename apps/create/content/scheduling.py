"""
Intent-Based Scheduling Engine for Kova Agent.

Instead of a date picker, scheduling is driven by intent:
- post_now: Publish immediately
- next_best: AI picks optimal time for platform + audience
- smart_queue: Slot into queue based on posting frequency
- quick: Predefined offsets (30min, 1hr, 3hr, tomorrow_am, tomorrow_pm)
- exact: User picks a specific datetime
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

# Peak engagement windows per platform (hours in UTC, adjust for user TZ)
# Based on general social media research — will be refined by analytics agent later.
PLATFORM_PEAK_HOURS = {
    "twitter": [
        (8, 10),   # Morning check-in
        (12, 14),  # Lunch scroll
        (17, 19),  # Evening wind-down
    ],
    "linkedin": [
        (7, 9),    # Pre-work
        (11, 13),  # Lunch break
        (17, 18),  # End of workday
    ],
    "instagram": [
        (7, 9),    # Morning scroll
        (12, 14),  # Lunch break
        (19, 21),  # Evening prime time
    ],
    "tiktok": [
        (12, 15),  # Afternoon
        (19, 23),  # Evening / night (peak)
    ],
    "facebook": [
        (9, 11),   # Mid-morning
        (13, 15),  # Early afternoon
        (18, 20),  # Evening
    ],
}

# Minimum gap between posts on the same platform (hours)
MIN_PLATFORM_GAP_HOURS = 4

# Minimum gap between any posts (hours)
MIN_GLOBAL_GAP_HOURS = 1


def get_next_best_slot(user, platform, after=None):
    """
    Find the next optimal posting time for a platform.

    Logic:
    1. Get the platform's peak hours
    2. Find the next peak window that starts after `after`
    3. Ensure no conflict with already-scheduled posts (platform gap + global gap)
    4. Return the best datetime
    """
    from apps.create.content.models import Post

    now = after or timezone.now()
    peaks = PLATFORM_PEAK_HOURS.get(platform, [(9, 11), (14, 16), (18, 20)])

    # Gather already-scheduled times for this user (next 7 days)
    scheduled = set(
        Post.objects.filter(
            user=user,
            scheduled_at__isnull=False,
            scheduled_at__gte=now,
            scheduled_at__lte=now + timedelta(days=7),
        ).values_list("scheduled_at", flat=True)
    )

    # Same-platform scheduled times
    platform_scheduled = set(
        Post.objects.filter(
            user=user,
            social_account__platform=platform,
            scheduled_at__isnull=False,
            scheduled_at__gte=now,
            scheduled_at__lte=now + timedelta(days=7),
        ).values_list("scheduled_at", flat=True)
    )

    # Try each peak window for the next 3 days
    for day_offset in range(4):
        candidate_date = (now + timedelta(days=day_offset)).date()

        for peak_start, peak_end in peaks:
            # Aim for the middle of the peak window
            candidate = timezone.make_aware(
                datetime.combine(candidate_date, time(hour=(peak_start + peak_end) // 2)),
                timezone.get_current_timezone(),
            )

            # Must be in the future
            if candidate <= now:
                continue

            # Check global gap — no post within MIN_GLOBAL_GAP_HOURS
            if _has_conflict(candidate, scheduled, MIN_GLOBAL_GAP_HOURS):
                # Try start of window instead
                candidate = timezone.make_aware(
                    datetime.combine(candidate_date, time(hour=peak_start)),
                    timezone.get_current_timezone(),
                )
                if candidate <= now or _has_conflict(candidate, scheduled, MIN_GLOBAL_GAP_HOURS):
                    continue

            # Check platform gap
            if _has_conflict(candidate, platform_scheduled, MIN_PLATFORM_GAP_HOURS):
                continue

            return candidate

    # Fallback: 3 hours from now
    return now + timedelta(hours=3)


def get_smart_queue_slot(user):
    """
    Find the next queue slot based on the user's posting frequency.

    Logic:
    - posting_frequency = posts per week
    - Calculate ideal gap = 7 days / frequency
    - Find the next slot after the last scheduled post (or now)
    - Snap to the nearest peak hour for any platform
    """
    from apps.create.content.models import Post

    now = timezone.now()
    profile = getattr(user, "profile", None)
    frequency = getattr(profile, "posting_frequency", 5)

    # Ideal gap between posts
    gap_hours = max(4, (7 * 24) // max(frequency, 1))

    # Find the last scheduled post
    last_scheduled = (
        Post.objects.filter(
            user=user,
            scheduled_at__isnull=False,
            scheduled_at__gte=now,
        )
        .order_by("-scheduled_at")
        .values_list("scheduled_at", flat=True)
        .first()
    )

    base = last_scheduled if last_scheduled else now
    candidate = base + timedelta(hours=gap_hours)

    # Snap to nearest peak hour (any platform)
    candidate = _snap_to_nearest_peak(candidate)

    # Make sure it's in the future
    if candidate <= now:
        candidate = now + timedelta(hours=gap_hours)

    return candidate


def get_quick_schedule_time(option):
    """
    Return a datetime for a quick-pick option.

    Options: 30min, 1hr, 3hr, tomorrow_am, tomorrow_pm
    """
    now = timezone.now()

    options = {
        "30min": now + timedelta(minutes=30),
        "1hr": now + timedelta(hours=1),
        "3hr": now + timedelta(hours=3),
        "tomorrow_am": timezone.make_aware(
            datetime.combine(now.date() + timedelta(days=1), time(hour=9)),
            timezone.get_current_timezone(),
        ),
        "tomorrow_pm": timezone.make_aware(
            datetime.combine(now.date() + timedelta(days=1), time(hour=18)),
            timezone.get_current_timezone(),
        ),
    }

    return options.get(option, now + timedelta(hours=1))


def _has_conflict(candidate, scheduled_times, min_gap_hours):
    """Check if a candidate time conflicts with any scheduled time."""
    gap = timedelta(hours=min_gap_hours)
    for st in scheduled_times:
        if abs(candidate - st) < gap:
            return True
    return False


def _snap_to_nearest_peak(dt):
    """Snap a datetime to the nearest peak hour across all platforms."""
    all_peaks = set()
    for peaks in PLATFORM_PEAK_HOURS.values():
        for start, end in peaks:
            all_peaks.add((start + end) // 2)

    hour = dt.hour
    nearest = min(all_peaks, key=lambda p: abs(p - hour))

    return dt.replace(hour=nearest, minute=0, second=0, microsecond=0)
