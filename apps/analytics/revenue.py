"""
Revenue attribution utilities.

Provides data aggregation for:
- ROI calculation
- Revenue trends (30-day)
- Revenue by content type / CTA type
- Product-level attribution (links 6H to 6G)
- Brief data injection
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_revenue_summary(user, days=30):
    """
    Comprehensive revenue attribution summary.
    Returns data for the enhanced revenue dashboard.
    """
    from apps.analytics.models import Conversion
    from apps.billing.models import get_plan_limits
    from apps.accounts.models import UserProfile

    cutoff = timezone.now() - timedelta(days=days)

    conversions = Conversion.objects.filter(user=user, created_at__gte=cutoff)

    # Core totals
    totals = conversions.aggregate(
        total_revenue=Sum("revenue"),
        total_conversions=Count("id"),
        total_sales=Count("id", filter=Q(conversion_type="sale")),
        total_leads=Count("id", filter=Q(conversion_type="lead")),
        total_clicks=Count("id", filter=Q(conversion_type="click")),
    )
    totals = {k: v or (Decimal("0") if "revenue" in k else 0) for k, v in totals.items()}

    # Revenue by platform
    platform_revenue = list(
        conversions
        .filter(social_account__isnull=False)
        .values("social_account__platform")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # Revenue by content type (from associated posts)
    content_type_revenue = list(
        conversions
        .filter(post__isnull=False)
        .values("post__content_type")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # Revenue by CTA type
    cta_type_revenue = list(
        conversions
        .filter(post__isnull=False)
        .values("post__cta_type")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # Revenue by product (6H integration)
    product_revenue = list(
        conversions
        .filter(product__isnull=False)
        .values("product__name", "product__pk")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")[:10]
    )

    # Top posts by revenue
    top_posts = list(
        conversions
        .filter(post__isnull=False)
        .values("post__id", "post__content_text", "post__social_account__platform")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")[:10]
    )

    # Revenue by source (shopify, mpesa, manual, etc.)
    source_revenue = list(
        conversions
        .filter(revenue__gt=0)
        .values("event_name")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")[:10]
    )

    # Daily revenue trend (last N days)
    from django.db.models.functions import TruncDate
    daily_trend = list(
        conversions
        .filter(revenue__gt=0)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("date")
    )

    # ROI calculation
    profile = getattr(user, "profile", None)
    plan = getattr(profile, "plan", "starter") if profile else "starter"
    plan_limits = get_plan_limits(plan)
    monthly_cost = Decimal(str(plan_limits.get("price_kes", 299)))
    total_rev = totals["total_revenue"]
    roi_percentage = ((total_rev - monthly_cost) / monthly_cost * 100) if monthly_cost > 0 else Decimal("0")

    # Funnel metrics
    funnel = {
        "clicks": totals["total_clicks"],
        "leads": totals["total_leads"],
        "sales": totals["total_sales"],
        "click_to_lead": (
            round(totals["total_leads"] / totals["total_clicks"] * 100, 1)
            if totals["total_clicks"] > 0 else 0
        ),
        "lead_to_sale": (
            round(totals["total_sales"] / totals["total_leads"] * 100, 1)
            if totals["total_leads"] > 0 else 0
        ),
        "click_to_sale": (
            round(totals["total_sales"] / totals["total_clicks"] * 100, 1)
            if totals["total_clicks"] > 0 else 0
        ),
    }

    return {
        "totals": totals,
        "platform_revenue": platform_revenue,
        "content_type_revenue": content_type_revenue,
        "cta_type_revenue": cta_type_revenue,
        "product_revenue": product_revenue,
        "top_posts": top_posts,
        "source_revenue": source_revenue,
        "daily_trend": daily_trend,
        "roi": {
            "monthly_cost_kes": monthly_cost,
            "revenue_kes": total_rev,
            "roi_percentage": round(roi_percentage, 1),
            "plan": plan,
        },
        "funnel": funnel,
        "days": days,
    }


def get_revenue_brief_data(user, days=7):
    """
    Revenue data for Daily Brief injection.
    Returns a concise dict the LLM can summarize.
    """
    from apps.analytics.models import Conversion

    cutoff = timezone.now() - timedelta(days=days)
    conversions = Conversion.objects.filter(user=user, created_at__gte=cutoff)

    totals = conversions.aggregate(
        revenue=Sum("revenue"),
        sales=Count("id", filter=Q(conversion_type="sale")),
        leads=Count("id", filter=Q(conversion_type="lead")),
        clicks=Count("id", filter=Q(conversion_type="click")),
    )

    # Best performing post this week
    best_post = (
        conversions
        .filter(post__isnull=False, revenue__gt=0)
        .values("post__content_text", "post__social_account__platform")
        .annotate(revenue=Sum("revenue"))
        .order_by("-revenue")
        .first()
    )

    return {
        "period_days": days,
        "total_revenue": float(totals["revenue"] or 0),
        "total_sales": totals["sales"] or 0,
        "total_leads": totals["leads"] or 0,
        "total_clicks": totals["clicks"] or 0,
        "best_post": {
            "content_preview": best_post["post__content_text"][:80] if best_post else "",
            "platform": best_post["post__social_account__platform"] if best_post else "",
            "revenue": float(best_post["revenue"]) if best_post else 0,
        } if best_post else None,
    }


def record_touchpoint(user, visitor_id, touch_type, utm_source="", utm_medium="",
                       utm_campaign="", utm_content="", post=None, referrer="",
                       landing_page="", device_type=""):
    """
    Record a touchpoint in a visitor's conversion journey.
    Creates or retrieves the active journey for this visitor.
    """
    from apps.analytics.models import ConversionJourney, ConversionTouchpoint

    # Get or create active (unconverted) journey for this visitor
    journey, created = ConversionJourney.objects.get_or_create(
        user=user,
        visitor_id=visitor_id,
        is_converted=False,
        defaults={"first_touch_at": timezone.now()},
    )

    touchpoint = ConversionTouchpoint.objects.create(
        journey=journey,
        post=post,
        touch_type=touch_type,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        referrer=referrer,
        landing_page=landing_page,
        device_type=device_type,
    )

    journey.touchpoint_count = journey.touchpoints.count()
    journey.last_touch_at = timezone.now()
    journey.save(update_fields=["touchpoint_count", "last_touch_at"])

    return touchpoint


def complete_journey(user, visitor_id, conversion):
    """
    Mark a journey as converted when a sale/conversion happens.
    Links the journey to the Conversion record.
    """
    from apps.analytics.models import ConversionJourney

    journey = ConversionJourney.objects.filter(
        user=user, visitor_id=visitor_id, is_converted=False,
    ).first()

    if not journey:
        return None

    journey.is_converted = True
    journey.conversion = conversion
    journey.total_revenue = conversion.revenue
    journey.converted_at = timezone.now()
    journey.save(update_fields=["is_converted", "conversion", "total_revenue", "converted_at"])
    return journey
