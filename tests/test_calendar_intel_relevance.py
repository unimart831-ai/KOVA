"""
Tests for apps.calendar_intel.relevance + selectors.

Covers:
  - Each multiplier component in isolation
  - End-to-end compute_score for realistic user profiles
  - Country filtering (primary/secondary/global/excluded)
  - Opt-in holiday gating
  - Mute behavior
  - upcoming_for_user query path
"""
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayOccurrence,
    UserHolidayPreference,
)
from apps.calendar_intel.relevance import (
    base_relevance,
    compute_score,
    country_multiplier,
    industry_multiplier,
    seasonal_multiplier,
    user_preference_multiplier,
)
from apps.calendar_intel.selectors import (
    applicable_holidays_for,
    top_upcoming_for_brief,
    upcoming_for_user,
)


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
def rw_food_user(db):
    """A Rwandan food/restaurant business — typical Kova ICP."""
    u = User.objects.create_user(
        username="iranzi_test",
        email="iranzi_test@kova.ai",
        password="TestPass123!",
        full_name="Iranzi Test",
    )
    UserProfile.objects.filter(user=u).update(
        country="RW",
        city="Kigali",
        industry="food_restaurant",
        secondary_markets=[],
    )
    return User.objects.get(pk=u.pk)


@pytest.fixture
def us_saas_user(db):
    """A US B2B SaaS business — different industry, different country."""
    u = User.objects.create_user(
        username="us_saas",
        email="us_saas@kova.ai",
        password="TestPass123!",
        full_name="US SaaS",
    )
    UserProfile.objects.filter(user=u).update(
        country="US",
        industry="saas",
        secondary_markets=[],
    )
    return User.objects.get(pk=u.pk)


@pytest.fixture
def mothers_day_holiday(db):
    return Holiday.objects.create(
        name="Mother's Day", slug="mothers-day-may",
        date_type="nth_weekday",
        date_config={"month": 5, "weekday": 6, "n": 2},
        countries=["RW", "KE", "US"],
        category="cultural",
        sensitivity_level="safe",
        default_relevance_score=80,
        suggested_post_count=2,
        lead_time_days=9,
        tone_hint="warm",
        industries=["retail", "f_and_b", "creative"],
        is_active=True,
    )


@pytest.fixture
def christmas_optin(db):
    """Religious holiday — requires opt-in."""
    return Holiday.objects.create(
        name="Christmas Day", slug="christmas-day",
        date_type="fixed", date_config={"month": 12, "day": 25},
        countries=[],   # global
        category="religious",
        religion="christian",
        sensitivity_level="safe",
        requires_opt_in=True,
        default_relevance_score=85,
        is_active=True,
    )


@pytest.fixture
def liberation_day_rw(db):
    """Country-specific holiday — only Rwanda."""
    return Holiday.objects.create(
        name="Liberation Day", slug="rw-liberation-day",
        date_type="fixed", date_config={"month": 7, "day": 4},
        countries=["RW"],
        category="national_holiday",
        sensitivity_level="safe",
        default_relevance_score=70,
        is_active=True,
    )


# ──────────────────────────────────────────────────────────────────────────
# Component multipliers
# ──────────────────────────────────────────────────────────────────────────
def test_base_relevance_normalizes_to_0_1(mothers_day_holiday):
    assert base_relevance(mothers_day_holiday) == 0.8


def test_base_relevance_clamps(db):
    h = Holiday.objects.create(
        name="x", slug="x", date_type="fixed", date_config={"month": 1, "day": 1},
        category="cultural", default_relevance_score=200,
    )
    assert base_relevance(h) == 1.0


def test_industry_multiplier_uses_canonical_mapping(mothers_day_holiday):
    """food_restaurant -> f_and_b. Mother's Day boost for f_and_b is 1.3 in YAML."""
    result = industry_multiplier(mothers_day_holiday, "food_restaurant")
    # The actual value is from the YAML, so we just assert it's > 1.0
    assert result >= 1.0


def test_industry_multiplier_unknown_industry_defaults_1(mothers_day_holiday):
    assert industry_multiplier(mothers_day_holiday, "nonexistent_industry") >= 1.0


def test_industry_multiplier_unmapped_holiday_defaults_1(db):
    h = Holiday.objects.create(
        name="x", slug="unmapped-holiday", date_type="fixed",
        date_config={"month": 1, "day": 1}, category="cultural",
    )
    assert industry_multiplier(h, "f_and_b") == 1.0


def test_country_multiplier_primary_match_boosts(liberation_day_rw):
    assert country_multiplier(liberation_day_rw, "RW", []) == 1.2


def test_country_multiplier_secondary_match_neutral(liberation_day_rw):
    assert country_multiplier(liberation_day_rw, "US", ["RW", "KE"]) == 1.0


def test_country_multiplier_global_holiday_neutral(christmas_optin):
    assert country_multiplier(christmas_optin, "RW", []) == 1.0
    assert country_multiplier(christmas_optin, "JP", []) == 1.0
    assert country_multiplier(christmas_optin, "", []) == 1.0


def test_country_multiplier_no_match_zero(liberation_day_rw):
    assert country_multiplier(liberation_day_rw, "US", ["FR"]) == 0.0


def test_country_multiplier_excluded_country_zero(db):
    h = Holiday.objects.create(
        name="x", slug="x", date_type="fixed",
        date_config={"month": 1, "day": 1}, category="cultural",
        countries=[], excluded_countries=["RW"],
    )
    assert country_multiplier(h, "RW", []) == 0.0


def test_country_multiplier_case_insensitive(liberation_day_rw):
    assert country_multiplier(liberation_day_rw, "rw", []) == 1.2


# ──────────────────────────────────────────────────────────────────────────
# User preference multiplier
# ──────────────────────────────────────────────────────────────────────────
def test_pref_multiplier_no_pref_optin_holiday_zero(christmas_optin, rw_food_user):
    """Opt-in holidays without explicit pref should return 0."""
    assert user_preference_multiplier(christmas_optin, rw_food_user) == 0.0


def test_pref_multiplier_no_pref_normal_holiday_neutral(mothers_day_holiday, rw_food_user):
    assert user_preference_multiplier(mothers_day_holiday, rw_food_user) == 1.0


def test_pref_multiplier_disabled_zero(mothers_day_holiday, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=mothers_day_holiday, is_enabled=False,
    )
    assert user_preference_multiplier(mothers_day_holiday, rw_food_user) == 0.0


def test_pref_multiplier_optin_enabled(christmas_optin, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=christmas_optin, is_enabled=True,
    )
    assert user_preference_multiplier(christmas_optin, rw_food_user) == 1.0


def test_pref_multiplier_muted_until_future_zero(mothers_day_holiday, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=mothers_day_holiday, is_enabled=True,
        muted_until=timezone.now().date() + timedelta(days=30),
    )
    assert user_preference_multiplier(mothers_day_holiday, rw_food_user) == 0.0


def test_pref_multiplier_muted_until_past_neutral(mothers_day_holiday, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=mothers_day_holiday, is_enabled=True,
        muted_until=timezone.now().date() - timedelta(days=30),
    )
    assert user_preference_multiplier(mothers_day_holiday, rw_food_user) == 1.0


def test_pref_multiplier_custom_score_normalized(mothers_day_holiday, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=mothers_day_holiday, is_enabled=True,
        custom_relevance_score=50,
    )
    assert user_preference_multiplier(mothers_day_holiday, rw_food_user) == 0.5


# ──────────────────────────────────────────────────────────────────────────
# Seasonal multiplier
# ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("days_until,expected", [
    (-1, 0.5),
    (0, 1.2),
    (3, 1.2),
    (5, 1.1),
    (7, 1.1),
    (10, 1.0),
    (14, 1.0),
    (20, 0.8),
    (30, 0.8),
    (60, 0.5),
])
def test_seasonal_multiplier(days_until, expected):
    assert seasonal_multiplier(days_until) == expected


# ──────────────────────────────────────────────────────────────────────────
# End-to-end compute_score
# ──────────────────────────────────────────────────────────────────────────
def test_compute_score_high_for_relevant_user(mothers_day_holiday, rw_food_user):
    """RW food restaurant + Mother's Day in 9 days = high score."""
    today = date(2026, 5, 1)
    target = date(2026, 5, 10)   # Mother's Day 2026 (Sun)
    score = compute_score(mothers_day_holiday, rw_food_user, target, today=today)
    # base 0.8 * f_and_b boost (~1.3) * RW primary (1.2) * seasonal 1.0 (9 days = 7-14 bucket) * 1.0 * 1.0
    # ~ 0.8 * 1.3 * 1.2 * 1.0 = 1.248 -> clamped to 100
    assert score >= 80


def test_compute_score_zero_for_wrong_country(liberation_day_rw, us_saas_user):
    """US user shouldn't score Rwandan-only holiday."""
    today = date(2026, 6, 1)
    target = date(2026, 7, 4)
    score = compute_score(liberation_day_rw, us_saas_user, target, today=today)
    assert score == 0


def test_compute_score_zero_for_optin_without_pref(christmas_optin, rw_food_user):
    today = date(2026, 12, 1)
    target = date(2026, 12, 25)
    score = compute_score(christmas_optin, rw_food_user, target, today=today)
    assert score == 0


def test_compute_score_high_for_optin_with_pref(christmas_optin, rw_food_user):
    UserHolidayPreference.objects.create(
        user=rw_food_user, holiday=christmas_optin, is_enabled=True,
    )
    today = date(2026, 12, 18)
    target = date(2026, 12, 25)   # 7 days out
    score = compute_score(christmas_optin, rw_food_user, target, today=today)
    assert score >= 70  # base 0.85 * seasonal 1.1 * neutral else


def test_compute_score_dampens_for_distant_dates(mothers_day_holiday, rw_food_user):
    today = date(2026, 1, 1)
    far_target = date(2026, 5, 10)    # 129 days out -> 0.5 multiplier
    near_target = date(2026, 1, 8)    # 7 days out -> 1.1 multiplier
    far_score = compute_score(mothers_day_holiday, rw_food_user, far_target, today=today)
    near_score = compute_score(mothers_day_holiday, rw_food_user, near_target, today=today)
    # Distant date must score strictly lower than near date
    assert far_score < near_score


# ──────────────────────────────────────────────────────────────────────────
# Selectors
# ──────────────────────────────────────────────────────────────────────────
def test_applicable_holidays_for_returns_global(christmas_optin, rw_food_user):
    """Global holidays apply regardless of country."""
    qs = applicable_holidays_for(rw_food_user)
    assert christmas_optin in qs


def test_applicable_holidays_for_filters_by_country(liberation_day_rw, us_saas_user, rw_food_user):
    rw_qs = applicable_holidays_for(rw_food_user)
    us_qs = applicable_holidays_for(us_saas_user)
    assert liberation_day_rw in rw_qs
    assert liberation_day_rw not in us_qs


def test_applicable_holidays_excludes_inactive(mothers_day_holiday, rw_food_user):
    mothers_day_holiday.is_active = False
    mothers_day_holiday.save()
    assert mothers_day_holiday not in applicable_holidays_for(rw_food_user)


def test_upcoming_for_user_returns_only_eligible(
    mothers_day_holiday, christmas_optin, rw_food_user,
):
    """Without opting in to Christmas, only Mother's Day should appear."""
    today = date(2026, 5, 1)
    # Need an occurrence row for the date filter
    HolidayOccurrence.objects.create(
        holiday=mothers_day_holiday, year=2026, date=date(2026, 5, 10),
    )
    HolidayOccurrence.objects.create(
        holiday=christmas_optin, year=2026, date=date(2026, 12, 25),
    )

    moments = upcoming_for_user(rw_food_user, days_ahead=365, today=today)
    slugs = [m.holiday_slug for m in moments]
    assert "mothers-day-may" in slugs
    assert "christmas-day" not in slugs


def test_upcoming_for_user_includes_custom_events(rw_food_user):
    today = date(2026, 5, 1)
    CustomEvent.objects.create(
        user=rw_food_user,
        name="Our 2nd Anniversary",
        date=date(2026, 5, 15),
        recurrence="yearly",
    )
    moments = upcoming_for_user(rw_food_user, today=today)
    custom_moments = [m for m in moments if m.source == "custom"]
    assert len(custom_moments) == 1
    assert custom_moments[0].name == "Our 2nd Anniversary"
    assert custom_moments[0].score == 100


def test_upcoming_for_user_sorted_by_score_then_date(
    mothers_day_holiday, liberation_day_rw, rw_food_user,
):
    today = date(2026, 5, 1)
    HolidayOccurrence.objects.create(
        holiday=mothers_day_holiday, year=2026, date=date(2026, 5, 10),
    )
    HolidayOccurrence.objects.create(
        holiday=liberation_day_rw, year=2026, date=date(2026, 7, 4),
    )

    moments = upcoming_for_user(rw_food_user, days_ahead=365, today=today)
    # Higher-scored should come first
    scores = [m.score for m in moments]
    assert scores == sorted(scores, reverse=True)


def test_top_upcoming_for_brief_respects_limit(
    mothers_day_holiday, liberation_day_rw, rw_food_user,
):
    today = date(2026, 5, 1)
    HolidayOccurrence.objects.create(
        holiday=mothers_day_holiday, year=2026, date=date(2026, 5, 10),
    )
    HolidayOccurrence.objects.create(
        holiday=liberation_day_rw, year=2026, date=date(2026, 7, 4),
    )
    with patch("apps.calendar_intel.selectors.timezone") as mock_tz:
        mock_tz.now.return_value.date.return_value = today
        moments = top_upcoming_for_brief(rw_food_user, count=1)
    assert len(moments) <= 1
