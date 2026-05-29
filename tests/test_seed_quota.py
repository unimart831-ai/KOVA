"""Tests for content seed quota overrides."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from apps.billing.seed_quota import get_effective_seed_max, get_seed_period_start


def test_effective_max_with_override_and_bonus():
    user = MagicMock()
    profile = MagicMock()
    profile.seed_monthly_limit_override = 50
    profile.seed_monthly_bonus = 10
    user.profile = profile
    limits = {"max_seeds_per_month": 30}
    assert get_effective_seed_max(user, limits) == 60


def test_effective_max_plan_only():
    user = MagicMock()
    profile = MagicMock()
    profile.seed_monthly_limit_override = None
    profile.seed_monthly_bonus = 0
    user.profile = profile
    assert get_effective_seed_max(user, {"max_seeds_per_month": 30}) == 30


@patch("apps.billing.seed_quota.timezone")
def test_period_start_uses_reset_at(mock_tz):
    from django.utils import timezone as dj_tz

    mock_tz.now.return_value = dj_tz.datetime(2026, 5, 15, 12, 0, tzinfo=dj_tz.utc)
    month_start = dj_tz.datetime(2026, 5, 1, 0, 0, tzinfo=dj_tz.utc)
    user = MagicMock()
    profile = MagicMock()
    profile.seed_quota_reset_at = dj_tz.datetime(2026, 5, 10, 0, 0, tzinfo=dj_tz.utc)
    user.profile = profile
    start = get_seed_period_start(user, month_start)
    assert start == profile.seed_quota_reset_at
