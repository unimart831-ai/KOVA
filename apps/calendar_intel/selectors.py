"""
Query selectors for the calendar_intel app.

Encapsulates "what does the user see?" logic so views/tasks/templates
don't reach into the ORM directly. Per KOVA_HOLIDAY_AWARENESS.md §10.2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from django.db.models import Q
from django.utils import timezone

from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayOccurrence,
)
from apps.calendar_intel.relevance import (
    ELIGIBLE_FOR_BRIEF,
    compute_score,
)


@dataclass
class ScoredMoment:
    """A scored upcoming moment ready for display in the brief or preferences page."""
    name: str
    date: date
    days_until: int
    score: int
    holiday_id: int | None = None
    holiday_slug: str | None = None
    custom_event_id: int | None = None
    category: str = ""
    sensitivity_level: str = "safe"
    source: str = "holiday"   # "holiday" | "custom"


# ──────────────────────────────────────────────────────────────────────────
# Holiday filtering
# ──────────────────────────────────────────────────────────────────────────
def applicable_holidays_for(user) -> list[Holiday]:
    """
    All Holiday rows that could possibly apply to the user based on their
    primary country + secondary markets. Does NOT apply preference filters
    or relevance scoring — caller does that.

    Country matching is done in Python rather than via JSONField queries
    because SQLite (used in tests) doesn't support `__contains` on JSONField
    arrays. The Holiday table is bounded (~100-300 rows) so this is fast.
    """
    profile = getattr(user, "profile", None)
    primary = (getattr(profile, "country", "") or "").upper()
    markets = [m.upper() for m in (getattr(profile, "secondary_markets", []) or [])]
    user_countries = ([primary] if primary else []) + markets

    all_active = Holiday.objects.filter(is_active=True)

    if not user_countries:
        # No country set — only global holidays apply
        return [h for h in all_active if not h.countries]

    return [h for h in all_active if _holiday_applies(h, primary, user_countries)]


def _holiday_applies(holiday: Holiday, primary: str, user_countries: list[str]) -> bool:
    """In-Python country-match logic mirroring relevance.country_multiplier."""
    excluded = [c.upper() for c in (holiday.excluded_countries or [])]
    if primary and primary in excluded:
        return False
    countries = [c.upper() for c in (holiday.countries or [])]
    if not countries:
        return True   # global
    return any(c in countries for c in user_countries)


# ──────────────────────────────────────────────────────────────────────────
# Upcoming-moments query
# ──────────────────────────────────────────────────────────────────────────
def upcoming_for_user(
    user,
    days_ahead: int = 30,
    min_score: int = ELIGIBLE_FOR_BRIEF,
    limit: int | None = None,
    today: date | None = None,
) -> list[ScoredMoment]:
    """
    Return scored upcoming moments (holidays + custom events) for the user,
    sorted by score (desc), then date (asc).

    Pass min_score=0 to include everything that applies (used by preferences page).
    """
    today = today or timezone.now().date()
    horizon = today + timedelta(days=days_ahead)

    moments: list[ScoredMoment] = []

    # --- Holidays ---
    applicable_holiday_ids = [h.id for h in applicable_holidays_for(user)]
    occurrences = (
        HolidayOccurrence.objects
        .filter(date__range=(today, horizon), holiday_id__in=applicable_holiday_ids)
        .select_related("holiday")
        .order_by("date")
    )
    for occ in occurrences:
        score = compute_score(occ.holiday, user, occ.date, today=today)
        if score < min_score:
            continue
        moments.append(ScoredMoment(
            name=occ.holiday.name,
            date=occ.date,
            days_until=(occ.date - today).days,
            score=score,
            holiday_id=occ.holiday_id,
            holiday_slug=occ.holiday.slug,
            category=occ.holiday.category,
            sensitivity_level=occ.holiday.sensitivity_level,
            source="holiday",
        ))

    # --- Custom events ---
    for ce in (
        CustomEvent.objects
        .filter(user=user, is_active=True, date__range=(today, horizon))
        .order_by("date")
    ):
        moments.append(ScoredMoment(
            name=ce.name,
            date=ce.date,
            days_until=(ce.date - today).days,
            score=100,  # custom events are user-curated — always relevant
            custom_event_id=ce.id,
            category="personal",
            sensitivity_level="safe",
            source="custom",
        ))

    # Sort: highest score first, then closest date
    moments.sort(key=lambda m: (-m.score, m.days_until))
    if limit:
        moments = moments[:limit]
    return moments


def top_upcoming_for_brief(user, count: int = 3) -> list[ScoredMoment]:
    """Convenience: top N upcoming moments at brief-eligible score, 30-day horizon.
    Used by the Daily Brief calendar widget."""
    return upcoming_for_user(
        user,
        days_ahead=30,
        min_score=ELIGIBLE_FOR_BRIEF,
        limit=count,
    )


def all_for_preferences(user, days_ahead: int = 365) -> list[ScoredMoment]:
    """All applicable upcoming moments at any score — for the preferences page.
    Includes opt-in holidays even when they currently score 0."""
    return upcoming_for_user(
        user,
        days_ahead=days_ahead,
        min_score=0,
    )
