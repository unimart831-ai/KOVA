"""
Admin-adjustable monthly content seed quotas (Studio "Drop your idea").

Used for internal testing and promotional grants without changing plan tier.
"""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def get_seed_period_start(user, month_start=None):
    """Count seeds created on or after this timestamp (within calendar month)."""
    now = timezone.now()
    if month_start is None:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    profile = getattr(user, "profile", None)
    reset_at = getattr(profile, "seed_quota_reset_at", None) if profile else None
    if reset_at:
        return max(month_start, reset_at)
    return month_start


def get_effective_seed_max(user, limits: dict | None = None) -> int:
    """Plan max + bonus, or admin override when set."""
    from apps.core.billing.models import get_user_plan_limits

    if limits is None:
        limits = get_user_plan_limits(user)
    profile = getattr(user, "profile", None)
    if profile and profile.seed_monthly_limit_override is not None:
        base = int(profile.seed_monthly_limit_override)
    else:
        base = int(limits.get("max_seeds_per_month", 5))
    bonus = int(getattr(profile, "seed_monthly_bonus", 0) or 0) if profile else 0
    return base + bonus


def count_seeds_in_period(user) -> int:
    """Count campaign activations (MarketingCampaign rows) in the billing period."""
    from apps.create.content.models import ContentSeed, MarketingCampaign

    period_start = get_seed_period_start(user)
    activated = MarketingCampaign.objects.filter(
        user=user,
        created_at__gte=period_start,
    ).count()

    # Seeds that entered generation before campaign row existed (edge cases)
    orphan = (
        ContentSeed.objects.filter(
            user=user,
            created_at__gte=period_start,
            status__in=(
                ContentSeed.SeedStatus.PROCESSING,
                ContentSeed.SeedStatus.COMPLETED,
                ContentSeed.SeedStatus.FAILED,
            ),
        )
        .filter(marketing_campaign__isnull=True)
        .count()
    )
    return activated + orphan


def _log_action(user, admin, action: str, reason: str, *, snapshot: dict | None = None):
    from apps.core.billing.models import ContentSeedQuotaLog

    usage_before = snapshot or {}
    ContentSeedQuotaLog.objects.create(
        user=user,
        admin=admin,
        action=action,
        reason=reason.strip(),
        used_before=usage_before.get("used", 0),
        max_before=usage_before.get("max", 0),
        remaining_before=usage_before.get("remaining", 0),
        plan_label=usage_before.get("plan_label", ""),
        metadata=usage_before.get("metadata", {}),
    )


def reset_seed_usage(user, admin, reason: str) -> dict:
    """Zero out this month's counted usage (testing / promo refresh)."""
    from apps.core.billing.enforcement import get_seed_usage

    before = get_seed_usage(user)
    profile = user.profile
    profile.seed_quota_reset_at = timezone.now()
    profile.save(update_fields=["seed_quota_reset_at"])
    _log_action(
        user,
        admin,
        "reset_usage",
        reason,
        snapshot={
            **before,
            "metadata": {"reset_at": profile.seed_quota_reset_at.isoformat()},
        },
    )
    from apps.core.billing.enforcement import get_seed_usage as usage_after

    after = usage_after(user)
    logger.info("Seed quota reset for user %s by %s", user.pk, admin.pk)
    return after


def set_seed_limit_override(user, admin, limit: int | None, reason: str) -> dict:
    """Replace plan max with a fixed cap (None clears override)."""
    from apps.core.billing.enforcement import get_seed_usage

    before = get_seed_usage(user)
    profile = user.profile
    profile.seed_monthly_limit_override = limit
    profile.save(update_fields=["seed_monthly_limit_override"])
    _log_action(
        user,
        admin,
        "set_limit_override" if limit is not None else "clear_limit_override",
        reason,
        snapshot={**before, "metadata": {"limit_override": limit}},
    )
    from apps.core.billing.enforcement import get_seed_usage as usage_after

    return usage_after(user)


def set_seed_bonus(user, admin, bonus: int, reason: str) -> dict:
    """Add extra seeds on top of plan max (promotions)."""
    from apps.core.billing.enforcement import get_seed_usage

    before = get_seed_usage(user)
    profile = user.profile
    profile.seed_monthly_bonus = max(0, int(bonus))
    profile.save(update_fields=["seed_monthly_bonus"])
    _log_action(
        user,
        admin,
        "set_bonus",
        reason,
        snapshot={**before, "metadata": {"bonus": profile.seed_monthly_bonus}},
    )
    from apps.core.billing.enforcement import get_seed_usage as usage_after

    return usage_after(user)


def clear_seed_quota_overrides(user, admin, reason: str) -> dict:
    """Remove reset, override, and bonus — back to pure plan limits."""
    from apps.core.billing.enforcement import get_seed_usage

    before = get_seed_usage(user)
    profile = user.profile
    profile.seed_quota_reset_at = None
    profile.seed_monthly_limit_override = None
    profile.seed_monthly_bonus = 0
    profile.save(
        update_fields=[
            "seed_quota_reset_at",
            "seed_monthly_limit_override",
            "seed_monthly_bonus",
        ],
    )
    _log_action(user, admin, "clear_all", reason, snapshot=before)
    from apps.core.billing.enforcement import get_seed_usage as usage_after

    return usage_after(user)
