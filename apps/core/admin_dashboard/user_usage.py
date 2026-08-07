"""Admin user usage summary — Plan v2 metering from existing models."""

from __future__ import annotations

from django.utils import timezone

from apps.create.agents.models import AgentAction, UserTokenBucket
from apps.core.billing.enforcement import get_seed_usage, get_user_daily_llm_token_cap, get_user_monthly_llm_token_cap
from apps.core.billing.models import get_effective_plan_tier, get_user_plan_limits, is_active_trial
from apps.core.billing.visual_credits import get_visual_credit_usage
from apps.core.billing.whatsapp_marketing import get_whatsapp_marketing_usage
from apps.create.content.models import Post


def _month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _posts_this_month(user) -> int:
    return Post.objects.filter(user=user, created_at__gte=_month_start()).count()


def _llm_tokens_today(user) -> int:
    today = timezone.now().date()
    bucket = UserTokenBucket.objects.filter(user=user, period_date=today).first()
    if not bucket:
        return 0
    return bucket.input_tokens + bucket.output_tokens


def _llm_tokens_this_month(user) -> int:
    month_start = timezone.now().replace(day=1).date()
    buckets = UserTokenBucket.objects.filter(user=user, period_date__gte=month_start)
    return sum(b.input_tokens + b.output_tokens for b in buckets)


def _last_activity(user):
    """Best-effort last activity from login, agent actions, or posts."""
    candidates = []
    if user.last_login:
        candidates.append(user.last_login)
    last_action = AgentAction.objects.filter(user=user).order_by("-created_at").values_list("created_at", flat=True).first()
    if last_action:
        candidates.append(last_action)
    last_post = Post.objects.filter(user=user).order_by("-created_at").values_list("created_at", flat=True).first()
    if last_post:
        candidates.append(last_post)
    return max(candidates) if candidates else None


def _plan_feature_flags(user, limits: dict) -> list[dict]:
    profile = user.profile
    flags = [
        ("WhatsApp Business", limits.get("whatsapp_enabled")),
        ("WhatsApp marketing", limits.get("whatsapp_marketing_conversations_per_month", 0) > 0),
        ("AI images", limits.get("ai_image_generation")),
        ("Studio polish", limits.get("visual_enhancements_per_month", 0) > 0),
        ("Engagement agent", limits.get("engagement_agent")),
        ("Adapt v2", limits.get("adapt_v2_enabled")),
        ("Memes", limits.get("memes_enabled")),
        ("A/B testing", limits.get("ab_testing")),
        ("Auto-approve (plan)", limits.get("auto_approve")),
        ("M-Pesa commerce", limits.get("mpesa_commerce")),
    ]
    if profile:
        flags.extend([
            ("Auto-approve (user pref)", profile.auto_approve_posts),
            ("Emergency pause", profile.emergency_pause),
            ("Agency approved", profile.is_agency_approved),
        ])
    return [{"label": label, "enabled": bool(on)} for label, on in flags]


def get_admin_user_usage(user) -> dict:
    """Monthly usage snapshot for admin user detail."""
    profile = user.profile
    limits = get_user_plan_limits(user)
    effective_tier = get_effective_plan_tier(profile) if profile else "starter"
    seed_usage = get_seed_usage(user)
    visual = get_visual_credit_usage(user)
    wa_marketing = get_whatsapp_marketing_usage(user)

    daily_used = _llm_tokens_today(user)
    daily_cap = get_user_daily_llm_token_cap(user)
    monthly_used = _llm_tokens_this_month(user)
    monthly_cap = get_user_monthly_llm_token_cap(user)
    posts_used = _posts_this_month(user)
    posts_cap = int(limits.get("max_posts_per_month", 0))

    platform = visual.get("platform") or {}
    user_polish_share = visual.get("used", 0)

    return {
        "effective_tier": effective_tier,
        "effective_label": limits.get("label", effective_tier),
        "billing_plan": profile.plan if profile else "—",
        "subscription_status": profile.subscription_status if profile else "none",
        "is_trialing": is_active_trial(profile) if profile else False,
        "trial_ends_at": profile.trial_ends_at if profile else None,
        "is_agency_approved": bool(profile and profile.is_agency_approved),
        "llm_daily": {"used": daily_used, "cap": daily_cap},
        "llm_monthly": {"used": monthly_used, "cap": monthly_cap},
        "posts": {"used": posts_used, "cap": posts_cap},
        "seeds": seed_usage,
        "studio_polish": visual,
        "whatsapp_marketing": wa_marketing,
        "platform_photoroom": platform,
        "user_photoroom_calls": user_polish_share,
        "feature_flags": _plan_feature_flags(user, limits),
        "last_activity": _last_activity(user),
        "last_login": user.last_login,
        "limits": limits,
    }
