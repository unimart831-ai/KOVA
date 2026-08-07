"""
Plan enforcement utilities — reusable limit checks for API, Celery tasks, and views.

Use these instead of middleware when you need plan checks outside the HTTP request cycle.
Trialing users receive Kova limits (5 campaigns) via get_user_plan_limits().
"""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.core.billing.models import PLAN_LIMITS, get_effective_plan_tier, get_plan_limits, get_user_plan_limits

logger = logging.getLogger(__name__)


def get_daily_llm_token_cap(plan: str) -> int:
    """Daily LLM cap — LLMConfig override when set, else PLAN_LIMITS."""
    try:
        from apps.create.agents.models import LLMConfig

        config = LLMConfig.load()
        if config.pk:
            custom = (config.plan_rate_limits or {}).get(plan, {})
            custom_cap = custom.get("max_tokens_per_day")
            if custom_cap is not None and int(custom_cap) > 0:
                return int(custom_cap)
    except Exception:
        logger.debug("LLMConfig rate limit lookup failed for plan=%s", plan, exc_info=True)

    limits = get_plan_limits(plan)
    return int(limits.get("daily_llm_tokens", PLAN_LIMITS["starter"]["daily_llm_tokens"]))


def get_user_daily_llm_token_cap(user) -> int:
    """Daily LLM cap for a user (respects active trial → Kova limits)."""
    profile = getattr(user, "profile", None)
    tier = get_effective_plan_tier(profile) if profile else "starter"
    return get_daily_llm_token_cap(tier)


def get_user_monthly_llm_token_cap(user) -> int:
    """Monthly LLM cap for a user (respects active trial → Kova limits)."""
    limits = get_user_plan_limits(user)
    return int(limits.get("monthly_llm_tokens", PLAN_LIMITS["starter"]["monthly_llm_tokens"]))


def check_plan_feature(user, feature_key: str, feature_label: str | None = None) -> tuple[bool, str]:
    """Check a boolean flag on the user's effective plan."""
    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_user_plan_limits(user)
    if limits.get(feature_key):
        return True, ""

    label = feature_label or feature_key.replace("_", " ")
    plan_label = limits.get("label", profile.plan)
    return False, f"{label} is not included in your {plan_label} plan."


def check_seed_limit(user):
    """
    Check if user can create another content seed this month.

    Returns:
        (allowed: bool, message: str)
    """
    usage = get_seed_usage(user)
    if usage["unlimited"] or not usage["at_limit"]:
        return True, ""
    return False, (
        f"You've used all {usage['max']} marketing campaigns for this month "
        f"on your {usage['plan_label']} plan."
    )


def get_seed_usage(user) -> dict:
    """Monthly seed quota for Studio UI and enforcement."""
    from apps.core.billing.seed_quota import count_seeds_in_period, get_effective_seed_max

    profile = getattr(user, "profile", None)
    limits = get_user_plan_limits(user) if profile else get_plan_limits("starter")
    plan_max = int(limits["max_seeds_per_month"])
    effective_max = get_effective_seed_max(user, limits)
    unlimited = effective_max >= 999999

    if unlimited:
        return {
            "used": 0,
            "max": effective_max,
            "remaining": effective_max,
            "at_limit": False,
            "unlimited": True,
            "plan_label": limits.get("label", "Starter"),
            "plan_max": plan_max,
            "bonus": int(getattr(profile, "seed_monthly_bonus", 0) or 0) if profile else 0,
            "limit_override": getattr(profile, "seed_monthly_limit_override", None) if profile else None,
            "reset_at": getattr(profile, "seed_quota_reset_at", None) if profile else None,
        }

    used = count_seeds_in_period(user)

    return {
        "used": used,
        "max": effective_max,
        "remaining": max(0, effective_max - used),
        "at_limit": used >= effective_max,
        "unlimited": False,
        "plan_label": limits.get("label", "Starter"),
        "plan_max": plan_max,
        "bonus": int(getattr(profile, "seed_monthly_bonus", 0) or 0) if profile else 0,
        "limit_override": getattr(profile, "seed_monthly_limit_override", None) if profile else None,
        "reset_at": getattr(profile, "seed_quota_reset_at", None) if profile else None,
        "campaigns_left_label": (
            f"{max(0, effective_max - used)} campaigns left this month"
            if effective_max - used != 1
            else "1 campaign left this month"
        ),
    }


DEFAULT_SEED_LIMIT_MESSAGE = "Monthly campaign limit reached."


def seed_limit_block_response(request, message: str = ""):
    """Stay on Studio with a compact inline warning — never dump the pricing page."""
    from apps.core.billing.plan_limit_ui import plan_limit_block_response

    return plan_limit_block_response(request, message or DEFAULT_SEED_LIMIT_MESSAGE, "content:studio")


def check_platform_limit(user):
    """
    Check if user can connect another social account.

    Returns:
        (allowed: bool, message: str)
    """
    from apps.core.platforms.models import SocialAccount

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_user_plan_limits(user)
    current_count = SocialAccount.objects.filter(user=user, is_active=True).count()

    if current_count >= limits["max_social_accounts"]:
        return False, (
            f"Social account limit reached ({limits['max_social_accounts']} "
            f"on {limits['label']} plan)."
        )
    return True, ""


def check_api_access(user):
    """
    Check if user's plan includes API access (Pro + Agency only).

    Returns:
        (allowed: bool, message: str)
    """
    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    tier = get_effective_plan_tier(profile)
    if tier in ("pro", "agency"):
        return True, ""

    return False, f"API access requires Pro or Agency plan. You're on {profile.get_plan_display()}."


def check_ab_testing(user) -> tuple[bool, str]:
    return check_plan_feature(user, "ab_testing", "A/B testing")


def check_auto_approve_plan(user) -> tuple[bool, str]:
    return check_plan_feature(user, "auto_approve", "Auto-approve publishing")


def check_shopify_integration(user) -> tuple[bool, str]:
    return check_plan_feature(user, "shopify_integration", "Shopify integration")


def check_mpesa_commerce(user) -> tuple[bool, str]:
    return check_plan_feature(user, "mpesa_commerce", "M-Pesa commerce checkout")


def check_leads_limit(user, creating: bool = True) -> tuple[bool, str]:
    """Check max_leads when creating a new lead."""
    if not creating:
        return True, ""

    from apps.commerce.leads.models import Lead

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_user_plan_limits(user)
    max_leads = limits.get("max_leads", 10)
    if max_leads >= 999999:
        return True, ""

    count = Lead.objects.filter(user=user).count()
    if count >= max_leads:
        return False, f"Lead limit reached ({max_leads} on {limits['label']} plan)."
    return True, ""


def check_leads_can_edit(user) -> tuple[bool, str]:
    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_user_plan_limits(user)
    if limits.get("leads_can_edit"):
        return True, ""
    return False, f"Editing leads requires Growth or higher on your {limits['label']} plan."


def check_email_sequences_limit(user) -> tuple[bool, str]:
    """Count manual sequences; welcome drip is excluded."""
    from apps.messaging.emails.automation import WELCOME_SEQUENCE_NAME
    from apps.messaging.emails.models import EmailSequence

    profile = getattr(user, "profile", None)
    if not profile:
        return False, "No user profile found."

    limits = get_user_plan_limits(user)
    max_seq = limits.get("email_sequences", 0)
    if max_seq >= 999999:
        return True, ""

    count = EmailSequence.objects.filter(user=user).exclude(name=WELCOME_SEQUENCE_NAME).count()
    if count >= max_seq:
        return False, (
            f"Email sequence limit reached ({max_seq} on {limits['label']} plan, "
            f"excluding the welcome drip)."
        )
    return True, ""


def enforce_or_redirect(request, allowed: bool, message: str, redirect_to: str = "brief:home", *args, **kwargs):
    """Helper for views — redirects with compact banner when blocked."""
    if allowed:
        return None
    from apps.core.billing.plan_limit_ui import plan_limit_redirect

    return plan_limit_redirect(request, message, redirect_to, *args, **kwargs)


def check_ai_image_limit(user) -> tuple[bool, str]:
    """Whether the user may generate another AI image this month."""
    from django.utils import timezone as tz

    from apps.create.content.models import Post

    limits = get_user_plan_limits(user)
    if not limits.get("ai_image_generation", False):
        return False, "Your plan doesn't include AI image generation."

    monthly_limit = int(limits.get("ai_images_per_month", 5) or 0)
    if monthly_limit <= 0:
        return False, "Your plan doesn't include AI image generation."

    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    images_this_month = Post.objects.filter(
        user=user,
        media_status="generated",
        created_at__gte=month_start,
    ).count()
    if images_this_month >= monthly_limit:
        return False, (
            f"Monthly image limit reached ({images_this_month}/{monthly_limit})."
        )
    return True, ""
