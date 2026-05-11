"""
Relevance scoring for Holiday × User pairs.

Implements the formula in KOVA_HOLIDAY_AWARENESS.md §13:

    score = base_relevance(H)
          x industry_multiplier(H, U.industry)
          x country_multiplier(H, U.country, U.markets)
          x user_preference_multiplier(H, U)
          x engagement_history_multiplier(H, U)
          x seasonal_multiplier(date_proximity)

Score thresholds:
    >= 60  -> eligible for draft generation (Phase 2)
    >= 40  -> surface in Brief calendar widget
    < 40   -> ignore

The function `compute_score()` returns a value 0-100 (clamped). It expects
a Holiday and User instance plus the holiday's target_date.
"""
from __future__ import annotations

import logging
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from django.utils import timezone

from apps.calendar_intel.industry_map import canonical_industry_for

logger = logging.getLogger(__name__)

# Score thresholds
ELIGIBLE_FOR_DRAFT = 60
ELIGIBLE_FOR_BRIEF = 40

BOOSTS_YAML = Path(__file__).resolve().parent / "seeds" / "industry_holiday_boosts.yaml"


@lru_cache(maxsize=1)
def _industry_boosts() -> dict[str, dict[str, float]]:
    """Load and cache the boost matrix YAML. Cached at process level."""
    if not BOOSTS_YAML.exists():
        logger.warning("industry_holiday_boosts.yaml not found at %s", BOOSTS_YAML)
        return {}
    with BOOSTS_YAML.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _clear_boost_cache():
    """For tests — clear the cached YAML lookup."""
    _industry_boosts.cache_clear()


# ──────────────────────────────────────────────────────────────────────────
# Component multipliers
# ──────────────────────────────────────────────────────────────────────────
def base_relevance(holiday) -> float:
    """Default relevance from the Holiday row, normalized to 0-1."""
    return max(0, min(100, holiday.default_relevance_score)) / 100


def industry_multiplier(holiday, profile_industry: str | None) -> float:
    """Lookup the boost matrix for this (holiday, industry). Default 1.0."""
    canonical = canonical_industry_for(profile_industry)
    boosts = _industry_boosts().get(holiday.slug, {})
    return float(boosts.get(canonical, 1.0))


def country_multiplier(
    holiday,
    primary_country: str | None,
    secondary_markets: list[str] | None,
) -> float:
    """
    1.2 for primary country match, 1.0 for secondary, 1.0 for global,
    0.0 if not applicable to user's markets at all.
    """
    primary = (primary_country or "").upper()
    markets = [m.upper() for m in (secondary_markets or [])]

    excluded = [c.upper() for c in (holiday.excluded_countries or [])]
    if primary and primary in excluded:
        return 0.0

    countries = [c.upper() for c in (holiday.countries or [])]

    # Global holiday — applies to everyone (subject to excluded_countries above)
    if not countries:
        return 1.0

    if primary and primary in countries:
        return 1.2
    if any(m in countries for m in markets):
        return 1.0
    return 0.0


def user_preference_multiplier(holiday, user) -> float:
    """Honor per-user UserHolidayPreference: muting, custom score, opt-in.
    Returns 0.0 if disabled/muted; otherwise 1.0 (or the custom score normalized)."""
    pref = user.holiday_preferences.filter(holiday=holiday).first()

    if pref is None:
        # No explicit preference. Default behavior:
        # - opt-in holidays default to 0 (user must opt in)
        # - everything else defaults to 1.0
        if holiday.requires_opt_in:
            return 0.0
        return 1.0

    if not pref.is_enabled:
        return 0.0
    if pref.muted_until and pref.muted_until > timezone.now().date():
        return 0.0
    if pref.custom_relevance_score is not None:
        return max(0, min(100, pref.custom_relevance_score)) / 100
    return 1.0


def engagement_history_multiplier(holiday, user) -> float:
    """
    Past holiday post performance for THIS holiday × user. Boosts wins,
    dampens flops, neutral if no signal.

    Looks at posts created from prior HolidayDraft cycles for the same holiday
    slug, joins to PostMetric.actual_score (0-100), and compares the average
    to the user's overall published-post average:

      - past avg >= user_avg + 15 -> 1.3x  (clear win)
      - past avg <= user_avg - 15 -> 0.7x  (clear flop)
      - otherwise                 -> 1.0x  (no strong signal)

    Returns 1.0 when there's no past data, no metrics, or fewer than 1
    completed cycle.
    """
    try:
        from django.db.models import Avg

        # Past published posts from holiday-watcher cycles for THIS holiday
        past_qs = user.posts.filter(
            generated_by_agent="holiday_watcher",
            status="published",
            holiday_drafts__holiday_occurrence__holiday=holiday,
        ).distinct()

        past_avg = past_qs.aggregate(avg=Avg("metrics__actual_score"))["avg"]
        if past_avg is None:
            return 1.0

        # Baseline: user's overall published-post average
        baseline = user.posts.filter(
            status="published",
        ).aggregate(avg=Avg("metrics__actual_score"))["avg"]
        if baseline is None:
            baseline = 50.0   # neutral fallback when no baseline yet

        delta = past_avg - baseline
        if delta >= 15:
            return 1.3
        if delta <= -15:
            return 0.7
        return 1.0
    except Exception:
        # Never let scoring break on a metrics edge case
        logger.exception("engagement_history_multiplier failed; falling back to 1.0")
        return 1.0


def seasonal_multiplier(days_until: int) -> float:
    """Closer dates get a slight boost; distant ones get dampened."""
    if days_until < 0:
        return 0.5    # past — we're late, dampen
    if days_until <= 3:
        return 1.2
    if days_until <= 7:
        return 1.1
    if days_until <= 14:
        return 1.0
    if days_until <= 30:
        return 0.8
    return 0.5


# ──────────────────────────────────────────────────────────────────────────
# Public scoring API
# ──────────────────────────────────────────────────────────────────────────
def compute_score(
    holiday,
    user,
    target_date: date,
    today: date | None = None,
) -> int:
    """
    Combined score 0-100 for a (holiday, user, date) tuple.
    Returns an integer for stable sorting and for storing on HolidayDraft.
    """
    today = today or timezone.now().date()
    profile = getattr(user, "profile", None)

    base = base_relevance(holiday)
    if base == 0:
        return 0

    country_mult = country_multiplier(
        holiday,
        getattr(profile, "country", None),
        getattr(profile, "secondary_markets", None),
    )
    if country_mult == 0:
        return 0

    pref_mult = user_preference_multiplier(holiday, user)
    if pref_mult == 0:
        return 0

    industry_mult = industry_multiplier(holiday, getattr(profile, "industry", None))
    history_mult = engagement_history_multiplier(holiday, user)
    seasonal_mult = seasonal_multiplier((target_date - today).days)

    raw = (
        base
        * industry_mult
        * country_mult
        * pref_mult
        * history_mult
        * seasonal_mult
    )
    return max(0, min(100, int(round(raw * 100))))


def is_eligible_for_draft(score: int) -> bool:
    return score >= ELIGIBLE_FOR_DRAFT


def is_eligible_for_brief(score: int) -> bool:
    return score >= ELIGIBLE_FOR_BRIEF
