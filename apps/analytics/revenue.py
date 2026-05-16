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


def _get_walkins_queryset(user, cutoff):
    """Walk-ins in the active window. Falls back to empty if the app/table
    isn't installed yet (lets analytics run on instances that haven't migrated)."""
    try:
        from apps.qr_attribution.models import WalkInEvent
    except Exception:
        return _EmptyQS()
    try:
        return WalkInEvent.objects.filter(user=user, recorded_at__gte=cutoff)
    except Exception:
        return _EmptyQS()


class _EmptyQS:
    """Stub queryset for environments without qr_attribution installed."""
    def aggregate(self, **kwargs):
        return {k: None for k in kwargs}
    def values(self, *_a, **_kw):
        return self
    def annotate(self, **_kw):
        return self
    def order_by(self, *_a):
        return []
    def __iter__(self):
        return iter([])


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

    walkins = _get_walkins_queryset(user, cutoff)

    # Core totals
    totals = conversions.aggregate(
        total_revenue=Sum("revenue"),
        total_conversions=Count("id"),
        total_sales=Count("id", filter=Q(conversion_type="sale")),
        total_leads=Count("id", filter=Q(conversion_type="lead")),
        total_clicks=Count("id", filter=Q(conversion_type="click")),
    )
    totals = {k: v or (Decimal("0") if "revenue" in k else 0) for k, v in totals.items()}

    walkin_totals = walkins.aggregate(
        revenue=Sum("revenue"),
        count=Count("id"),
    )
    walkin_revenue = walkin_totals["revenue"] or Decimal("0")
    walkin_count = walkin_totals["count"] or 0
    totals["walkin_revenue"] = walkin_revenue
    totals["walkin_count"] = walkin_count
    totals["digital_revenue"] = totals["total_revenue"]
    totals["total_revenue"] = totals["total_revenue"] + walkin_revenue

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

    walkin_by_source = list(
        walkins
        .values("attribution_source")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("-revenue")
    )

    # Merge walk-in revenue into platform_revenue where attribution_source
    # maps to a digital platform. Walk-ins tied to instagram/facebook/etc.
    # are real revenue those channels drove — they belong in that bucket.
    _WALKIN_TO_PLATFORM = {
        "instagram": "instagram",
        "facebook": "facebook",
        "whatsapp": "whatsapp",
        "tiktok": "tiktok",
    }
    by_platform = {p["social_account__platform"]: p for p in platform_revenue}
    for row in walkin_by_source:
        plat = _WALKIN_TO_PLATFORM.get(row["attribution_source"])
        if not plat:
            continue
        bucket = by_platform.setdefault(plat, {
            "social_account__platform": plat, "revenue": Decimal("0"), "count": 0,
        })
        bucket["revenue"] = (bucket["revenue"] or Decimal("0")) + (row["revenue"] or Decimal("0"))
        bucket["count"] = (bucket["count"] or 0) + (row["count"] or 0)
    platform_revenue = sorted(
        by_platform.values(),
        key=lambda r: r["revenue"] or Decimal("0"),
        reverse=True,
    )

    return {
        "totals": totals,
        "platform_revenue": platform_revenue,
        "content_type_revenue": content_type_revenue,
        "cta_type_revenue": cta_type_revenue,
        "product_revenue": product_revenue,
        "top_posts": top_posts,
        "source_revenue": source_revenue,
        "walkin_by_source": walkin_by_source,
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


def get_revenue_headline_insight(user, days=7, summary=None):
    """The single-sentence "what should I tell the owner?" insight.

    Used at the top of the Revenue Dashboard and as the Daily Brief revenue
    line. Returns a small dict the template / LLM can render:

        {
            "kind": "top_post" | "no_revenue" | "no_pixel" | "no_pipeline",
            "headline": "Your IG post about silk-press drove KES 12,400…",
            "subline": "That's 67% of your total revenue this week.",
            "cta_url": "...",  # optional next-action link
            "cta_text": "...",
        }

    The template branches on `kind` for empty-state vs. data-state visuals.
    """
    from apps.analytics.models import Conversion, WebsiteEvent
    from apps.content.models import Post
    from django.db.models import Sum

    if summary is None:
        summary = get_revenue_summary(user, days=days)

    total_revenue = float(summary["totals"]["total_revenue"] or 0)
    top_posts = summary.get("top_posts") or []

    # ── Happy path: we have a winning post with attributed revenue ─────
    if total_revenue > 0 and top_posts:
        top = top_posts[0]
        post_revenue = float(top["revenue"])
        share = (post_revenue / total_revenue * 100) if total_revenue > 0 else 0
        # Take first 8 words as the "about" phrase — same trick the brief uses
        content_preview = " ".join(
            (top.get("post__content_text") or "").split()[:8]
        ).rstrip(".,!?")
        platform = (top.get("post__social_account__platform") or "social").title()
        headline = (
            f"Your {platform} post about \"{content_preview}\" drove "
            f"KES {post_revenue:,.0f} in the last {days} days."
        )
        subline = (
            f"That's {share:.0f}% of your total revenue across all channels."
            if share >= 5 else
            f"Across {len(top_posts)} earning posts, {summary['totals']['total_sales']} sale(s) attributed."
        )
        return {
            "kind": "top_post",
            "headline": headline,
            "subline": subline,
            "cta_url": "",
            "cta_text": "",
            "post_id": top.get("post__id"),
            "post_revenue": post_revenue,
            "platform": top.get("post__social_account__platform") or "",
        }

    # ── No revenue yet — check if data pipeline is wired at all ────────
    # Has the Pixel ever fired? Has any Conversion ever existed?
    pixel_events_count = WebsiteEvent.objects.filter(user=user).count()
    has_any_conversion = Conversion.objects.filter(user=user).exists()
    has_published_posts = Post.objects.filter(
        user=user, status="published",
    ).exists()

    if has_any_conversion:
        # Pipeline works, just nothing in the window
        return {
            "kind": "no_revenue_in_window",
            "headline": f"No revenue attributed in the last {days} days.",
            "subline": "Try a longer window — or check the Top Posts feed for what drove conversions earlier.",
            "cta_url": "?days=90",
            "cta_text": "View 90 days",
        }

    if pixel_events_count > 0:
        # Pixel firing but no Conversions — most likely UTM weren't tagging
        # before today. The W1.1 fix means new posts now will attribute.
        return {
            "kind": "pipeline_warming",
            "headline": "Your Pixel is firing — revenue attribution is warming up.",
            "subline": (
                f"{pixel_events_count} website events captured so far. "
                "New posts will tag clicks back to revenue automatically."
            ),
            "cta_url": "/analytics/pixel/",
            "cta_text": "Pixel settings",
        }

    if has_published_posts:
        # Posts are publishing but no Pixel installed — typical SME state
        return {
            "kind": "no_pixel",
            "headline": "Your posts are live — install the Kova Pixel to start tracking what makes money.",
            "subline": "One snippet on your site. We'll show you which post drove each sale.",
            "cta_url": "/analytics/pixel/",
            "cta_text": "Install Pixel →",
        }

    # Brand new account — no posts, no pixel, nothing
    return {
        "kind": "no_pipeline",
        "headline": "No data yet — start by publishing your first post.",
        "subline": "Once posts are live and the Pixel is installed, revenue will land here.",
        "cta_url": "/studio/",
        "cta_text": "Open Studio →",
    }


def get_revenue_stat_card(user):
    """Compact stat block for the Daily Brief home page (W1.4).

    Returns last-7-day attributed revenue + the WoW delta and direction, so
    the home page can glance the headline number without the user having to
    open the Revenue Dashboard:

        {
            "current_kes": 12400.00,
            "previous_kes": 4800.00,
            "delta_pct": 158.3,
            "direction": "up" | "down" | "flat",
            "has_data": True,
        }

    `has_data=False` means both windows are zero — the template should hide
    or show an install-Pixel hint instead of a misleading "—" card.
    """
    from apps.analytics.models import Conversion
    from django.db.models import Sum

    now = timezone.now()
    last_7_start = now - timedelta(days=7)
    prev_7_start = now - timedelta(days=14)

    current = Conversion.objects.filter(
        user=user, created_at__gte=last_7_start,
    ).aggregate(rev=Sum("revenue"))["rev"] or Decimal("0")

    previous = Conversion.objects.filter(
        user=user,
        created_at__gte=prev_7_start,
        created_at__lt=last_7_start,
    ).aggregate(rev=Sum("revenue"))["rev"] or Decimal("0")

    if previous > 0:
        delta_pct = float((current - previous) / previous * 100)
    elif current > 0:
        delta_pct = 100.0  # No baseline; show as +100% (a "new" win)
    else:
        delta_pct = 0.0

    if delta_pct > 5:
        direction = "up"
    elif delta_pct < -5:
        direction = "down"
    else:
        direction = "flat"

    return {
        "current_kes": float(current),
        "previous_kes": float(previous),
        "delta_pct": round(delta_pct, 1),
        "direction": direction,
        "has_data": bool(current > 0 or previous > 0),
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
