"""Starter Engage trial — limited auto-replies per week."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.billing.models import PLAN_LIMITS, get_effective_plan_tier, get_user_plan_limits


def _week_start():
    now = timezone.now()
    return (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )


def engage_inbox_allowed(user) -> bool:
    limits = get_user_plan_limits(user)
    if limits.get("engagement_agent"):
        return True
    return bool(limits.get("engage_trial_enabled"))


def engage_trial_weekly_cap(user) -> int:
    limits = get_user_plan_limits(user)
    if limits.get("engagement_agent"):
        return 0  # unlimited via full plan
    return int(limits.get("engage_trial_auto_replies_per_week", 0))


def get_engage_trial_usage(user) -> dict:
    """Return weekly auto-reply usage for Starter trial users."""
    cap = engage_trial_weekly_cap(user)
    if cap <= 0:
        return {"cap": 0, "used": 0, "remaining": 0, "active": False}

    profile = getattr(user, "profile", None)
    if not profile:
        return {"cap": cap, "used": 0, "remaining": cap, "active": True}

    week_start = _week_start()
    stored_week = profile.engage_trial_week_start
    used = profile.engage_trial_replies_this_week or 0
    if not stored_week or stored_week < week_start:
        used = 0

    return {
        "cap": cap,
        "used": used,
        "remaining": max(0, cap - used),
        "active": True,
        "week_start": week_start,
    }


def can_consume_engage_trial_reply(user) -> tuple[bool, str]:
    """Check if a Starter trial user may auto-send one more reply this week."""
    limits = get_user_plan_limits(user)
    if limits.get("engagement_agent"):
        return True, ""

    if not limits.get("engage_trial_enabled"):
        return False, "Engage inbox is not included in your plan."

    usage = get_engage_trial_usage(user)
    if usage["remaining"] <= 0:
        tier = get_effective_plan_tier(getattr(user, "profile", None))
        label = PLAN_LIMITS.get(tier, {}).get("label", "Starter")
        return False, (
            f"You've used all {usage['cap']} trial auto-replies this week "
            f"on {label}. Upgrade to Kazi for unlimited Engage."
        )
    return True, ""


def record_engage_trial_reply(user, *, count: int = 1) -> None:
    """Increment weekly auto-reply counter for Starter trial users."""
    limits = get_user_plan_limits(user)
    if limits.get("engagement_agent") or not limits.get("engage_trial_enabled"):
        return

    profile = user.profile
    week_start = _week_start()
    if not profile.engage_trial_week_start or profile.engage_trial_week_start < week_start:
        profile.engage_trial_replies_this_week = 0
        profile.engage_trial_week_start = week_start

    profile.engage_trial_replies_this_week = (
        (profile.engage_trial_replies_this_week or 0) + max(1, count)
    )
    profile.save(
        update_fields=["engage_trial_replies_this_week", "engage_trial_week_start"],
    )
