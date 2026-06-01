"""Aggregated operational snapshot for admin dashboard overview hub."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone


def build_ops_hub_snapshot() -> dict:
    """High-value platform metrics with links to existing admin pages — bulk queries only."""
    from apps.accounts.models import UserProfile
    from apps.billing.models import AgencySalesInquiry
    from apps.billing.visual_credits import get_platform_photoroom_usage
    from apps.content.models import ContentSafetyIncident, Post, SystemSafetyConfig
    from apps.partners.models import MarketplacePartner, MarketplaceSellerAccount, WebhookDeliveryLog
    from apps.platforms.models import SocialAccount

    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    profiles = UserProfile.objects.all()
    plan_counts = {
        row["plan"]: row["count"]
        for row in profiles.values("plan").annotate(count=Count("id"))
    }
    status_counts = {
        row["subscription_status"]: row["count"]
        for row in profiles.values("subscription_status").annotate(count=Count("id"))
    }
    trialing = profiles.filter(subscription_status="trialing").count()
    active_paid = profiles.filter(subscription_status="active").count()
    agency_pending = profiles.filter(plan="agency", is_agency_approved=False).count()
    free_users = profiles.filter(
        subscription_status__in=["none", "canceled", "incomplete"],
    ).exclude(subscription_status="trialing").count()

    stripe_customers = profiles.exclude(stripe_customer_id="").count()
    mpesa_users = profiles.filter(payment_provider="mpesa").count()

    platform_counts = {
        row["platform"]: row["count"]
        for row in SocialAccount.objects.filter(is_active=True).values("platform").annotate(count=Count("id"))
    }

    failed_posts_7d = Post.objects.filter(status="failed", updated_at__gte=seven_days_ago).count()
    failed_posts_open = Post.objects.filter(status="failed").count()

    from apps.content.safety import (
        content_safety_checks_running,
        content_safety_enabled,
        content_safety_staff_paused,
    )

    safety_config = SystemSafetyConfig.load()
    safety_pending = ContentSafetyIncident.objects.filter(
        review_status=ContentSafetyIncident.ReviewStatus.PENDING,
    ).count()
    safety_today = ContentSafetyIncident.objects.filter(created_at__date=now.date()).count()
    snap_blocked_users = UserProfile.objects.filter(
        Q(snap_blocked_until__gt=now) | Q(auto_publish_paused=True),
    ).count()

    agency_sales_new = AgencySalesInquiry.objects.filter(
        status=AgencySalesInquiry.Status.NEW,
    ).count()

    active_marketplaces = MarketplacePartner.objects.filter(is_active=True).count()
    unimart = MarketplacePartner.objects.filter(slug__icontains="unimart").first()
    unimart_sellers = 0
    if unimart:
        unimart_sellers = MarketplaceSellerAccount.objects.filter(marketplace=unimart).count()
    webhook_failed_7d = WebhookDeliveryLog.objects.filter(
        created_at__gte=seven_days_ago,
        status=WebhookDeliveryLog.Status.FAILED,
    ).count()

    photoroom = get_platform_photoroom_usage()
    photoroom["pool_pct_display"] = round(photoroom.get("pool_pct", 0) * 100, 1)

    return {
        "plan_counts": plan_counts,
        "status_counts": status_counts,
        "trialing_users": trialing,
        "active_paid_users": active_paid,
        "free_users": free_users,
        "agency_pending": agency_pending,
        "stripe_customers": stripe_customers,
        "mpesa_users": mpesa_users,
        "platform_counts": platform_counts,
        "platform_total": sum(platform_counts.values()),
        "failed_posts_7d": failed_posts_7d,
        "failed_posts_open": failed_posts_open,
        "safety_pending": safety_pending,
        "safety_today": safety_today,
        "auto_publish_paused": safety_config.auto_publish_paused,
        "content_safety_env_enabled": content_safety_enabled(),
        "content_safety_staff_paused": content_safety_staff_paused(),
        "content_safety_checks_running": content_safety_checks_running(),
        "content_safety_paused_by": safety_config.content_safety_paused_by,
        "content_safety_paused_at": safety_config.content_safety_paused_at,
        "snap_blocked_users": snap_blocked_users,
        "agency_sales_new": agency_sales_new,
        "active_marketplaces": active_marketplaces,
        "unimart": unimart,
        "unimart_sellers": unimart_sellers,
        "webhook_failed_7d": webhook_failed_7d,
        "photoroom": photoroom,
        "month_start": month_start,
    }
