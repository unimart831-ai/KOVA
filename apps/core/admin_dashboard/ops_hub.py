"""Aggregated operational snapshot for admin dashboard overview hub."""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

OPS_HUB_CACHE_KEY = "admin:ops_hub:snapshot:v1"
OPS_HUB_CACHE_TTL = 90


def get_cached_ops_hub_snapshot(*, force_refresh: bool = False) -> dict:
    if not force_refresh:
        cached = cache.get(OPS_HUB_CACHE_KEY)
        if cached is not None:
            return cached
    snapshot = build_ops_hub_snapshot()
    cache.set(OPS_HUB_CACHE_KEY, snapshot, OPS_HUB_CACHE_TTL)
    return snapshot


def build_ops_hub_snapshot() -> dict:
    """High-value platform metrics with links to existing admin pages — bulk queries only."""
    from apps.core.accounts.models import UserProfile
    from apps.core.billing.models import AgencySalesInquiry
    from apps.core.billing.visual_credits import get_platform_photoroom_usage
    from apps.create.content.models import ContentSafetyIncident, Post, SystemSafetyConfig
    from apps.core.platforms.models import SocialAccount

    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    plan_counts = {
        row["plan"]: row["count"]
        for row in UserProfile.objects.values("plan").annotate(count=Count("id"))
    }
    status_counts = {
        row["subscription_status"]: row["count"]
        for row in UserProfile.objects.values("subscription_status").annotate(count=Count("id"))
    }

    profile_agg = UserProfile.objects.aggregate(
        trialing=Count("id", filter=Q(subscription_status="trialing")),
        active_paid=Count("id", filter=Q(subscription_status="active")),
        agency_pending=Count(
            "id",
            filter=Q(plan="agency", is_agency_approved=False),
        ),
        free_users=Count(
            "id",
            filter=Q(subscription_status__in=["none", "canceled", "incomplete"])
            & ~Q(subscription_status="trialing"),
        ),
        stripe_customers=Count("id", filter=~Q(stripe_customer_id="")),
        mpesa_users=Count("id", filter=Q(payment_provider="mpesa")),
        snap_blocked=Count(
            "id",
            filter=Q(snap_blocked_until__gt=now) | Q(auto_publish_paused=True),
        ),
    )

    platform_counts = {
        row["platform"]: row["count"]
        for row in SocialAccount.objects.filter(is_active=True).values("platform").annotate(count=Count("id"))
    }

    post_agg = Post.objects.aggregate(
        failed_7d=Count("id", filter=Q(status="failed", updated_at__gte=seven_days_ago)),
        failed_open=Count("id", filter=Q(status="failed")),
    )

    from apps.create.content.safety import (
        content_safety_checks_running,
        content_safety_enabled,
        content_safety_staff_paused,
    )

    safety_config = SystemSafetyConfig.load()
    safety_agg = ContentSafetyIncident.objects.aggregate(
        pending=Count(
            "id",
            filter=Q(review_status=ContentSafetyIncident.ReviewStatus.PENDING),
        ),
        today=Count("id", filter=Q(created_at__date=now.date())),
    )

    agency_sales_new = AgencySalesInquiry.objects.filter(
        status=AgencySalesInquiry.Status.NEW,
    ).count()

    active_marketplaces = 0
    unimart = None
    unimart_sellers = 0
    webhook_failed_7d = 0

    photoroom = get_platform_photoroom_usage()
    photoroom["pool_pct_display"] = round(photoroom.get("pool_pct", 0) * 100, 1)

    return {
        "plan_counts": plan_counts,
        "status_counts": status_counts,
        "trialing_users": profile_agg["trialing"],
        "active_paid_users": profile_agg["active_paid"],
        "free_users": profile_agg["free_users"],
        "agency_pending": profile_agg["agency_pending"],
        "stripe_customers": profile_agg["stripe_customers"],
        "mpesa_users": profile_agg["mpesa_users"],
        "platform_counts": platform_counts,
        "platform_total": sum(platform_counts.values()),
        "failed_posts_7d": post_agg["failed_7d"],
        "failed_posts_open": post_agg["failed_open"],
        "safety_pending": safety_agg["pending"],
        "safety_today": safety_agg["today"],
        "auto_publish_paused": safety_config.auto_publish_paused,
        "content_safety_env_enabled": content_safety_enabled(),
        "content_safety_staff_paused": content_safety_staff_paused(),
        "content_safety_checks_running": content_safety_checks_running(),
        "content_safety_paused_by": safety_config.content_safety_paused_by,
        "content_safety_paused_at": safety_config.content_safety_paused_at,
        "snap_blocked_users": profile_agg["snap_blocked"],
        "agency_sales_new": agency_sales_new,
        "active_marketplaces": active_marketplaces,
        "unimart": unimart,
        "unimart_sellers": unimart_sellers,
        "webhook_failed_7d": webhook_failed_7d,
        "photoroom": photoroom,
        "month_start": month_start,
    }
