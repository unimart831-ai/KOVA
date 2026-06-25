"""Campaign quota renewal — sync recurring add-on bonuses at period boundaries."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def _active_burst_bonus(profile) -> int:
    expires = getattr(profile, "burst_campaign_expires_at", None)
    bonus = int(getattr(profile, "burst_campaign_bonus", 0) or 0)
    if bonus <= 0:
        return 0
    if expires and expires <= timezone.now():
        return 0
    return bonus


def sync_campaign_bonus_totals(profile, *, reason: str = "renewal") -> dict:
    """Set seed_monthly_bonus = recurring + active burst credits."""
    from apps.billing.enforcement import get_seed_usage
    from apps.billing.models import ContentSeedQuotaLog

    recurring = int(getattr(profile, "recurring_campaign_bonus", 0) or 0)
    burst = _active_burst_bonus(profile)
    target = recurring + burst
    before = int(profile.seed_monthly_bonus or 0)

    if burst <= 0 and getattr(profile, "burst_campaign_bonus", 0):
        profile.burst_campaign_bonus = 0
        profile.burst_campaign_expires_at = None

    if target != before or burst <= 0:
        usage_before = get_seed_usage(profile.user)
        profile.seed_monthly_bonus = target
        profile.save(update_fields=[
            "seed_monthly_bonus",
            "burst_campaign_bonus",
            "burst_campaign_expires_at",
        ])
        ContentSeedQuotaLog.objects.create(
            user=profile.user,
            admin=None,
            action=ContentSeedQuotaLog.Action.SET_BONUS,
            reason=f"Campaign bonus sync: {reason}",
            used_before=usage_before["used"],
            max_before=usage_before["max"],
            remaining_before=usage_before["remaining"],
            plan_label=usage_before["plan_label"],
            metadata={
                "recurring_bonus": recurring,
                "burst_bonus": burst,
                "before": before,
                "after": target,
            },
        )
        logger.info(
            "Campaign bonus sync user=%s recurring=%s burst=%s total=%s",
            profile.user_id, recurring, burst, target,
        )

    return {"recurring": recurring, "burst": burst, "bonus": target}


def apply_addon_purchase_bonus(profile, pack: dict) -> None:
    """Credit campaigns after purchase — recurring stacks; burst expires month-end."""
    campaigns = int(pack.get("campaigns") or 0)
    if pack.get("recurring"):
        profile.recurring_campaign_bonus = (
            int(getattr(profile, "recurring_campaign_bonus", 0) or 0) + campaigns
        )
        profile.save(update_fields=["recurring_campaign_bonus"])
    else:
        now = timezone.now()
        month_end = (now.replace(day=1) + timedelta(days=32)).replace(
            day=1, hour=23, minute=59, second=59, microsecond=0,
        ) - timedelta(days=1)
        current_burst = _active_burst_bonus(profile)
        profile.burst_campaign_bonus = current_burst + campaigns
        profile.burst_campaign_expires_at = month_end
        profile.save(update_fields=["burst_campaign_bonus", "burst_campaign_expires_at"])
    sync_campaign_bonus_totals(profile, reason=f"addon:{pack.get('id')}")


def maybe_grandfather_to_kova(profile, *, on_renewal: bool = False) -> bool:
    """Migrate legacy starter/growth/pro subscribers to kova at renewal."""
    legacy = {"starter", "growth", "pro"}
    if profile.plan not in legacy:
        return False
    if profile.subscription_status not in ("active", "trialing") and not on_renewal:
        return False

    old_plan = profile.plan
    profile.plan = "kova"
    goodwill = {"growth": 10, "pro": 20}.get(old_plan, 0)
    if goodwill and on_renewal:
        profile.recurring_campaign_bonus = (
            int(getattr(profile, "recurring_campaign_bonus", 0) or 0) + goodwill
        )
    profile.save(update_fields=["plan", "recurring_campaign_bonus"])
    sync_campaign_bonus_totals(profile, reason=f"grandfather:{old_plan}")
    logger.info("Grandfathered user %s from %s → kova", profile.user_id, old_plan)
    return True
