"""
Report generation — PDF reports from attribution data.

Usage:
    from apps.analytics.reports import generate_report_pdf
    pdf_bytes = generate_report_pdf(user, days=30)
"""

import io
import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.template.loader import render_to_string
from django.utils import timezone

from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


def gather_report_data(user, days=30):
    """Build the full attribution report data for a user."""
    from apps.analytics.models import Conversion, PostMetric
    from apps.engage.models import Interaction
    from apps.leads.models import Lead
    from apps.links.models import LinkClick

    now = timezone.now()
    cutoff = now - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)

    # Posts & engagement
    published = user.posts.filter(status="published", published_at__gte=cutoff)
    post_ids = list(published.values_list("id", flat=True))
    metrics = PostMetric.objects.filter(post_id__in=post_ids)
    eng = metrics.aggregate(
        impressions=Sum("impressions"),
        reach=Sum("reach"),
        likes=Sum("likes"),
        comments=Sum("comments"),
        shares=Sum("shares"),
        saves=Sum("saves"),
        clicks=Sum("clicks"),
        avg_rate=Avg("engagement_rate"),
    )
    eng = {k: v or 0 for k, v in eng.items()}
    eng["engagements"] = eng["likes"] + eng["comments"] + eng["shares"] + eng["saves"]

    # Link clicks
    link_clicks = LinkClick.objects.filter(
        link__page__user=user, clicked_at__gte=cutoff,
    ).count()

    # Leads
    leads_qs = Lead.objects.filter(user=user, first_seen_at__gte=cutoff)
    leads_total = leads_qs.count()
    leads_by_source = list(
        leads_qs.values("source_type").annotate(count=Count("id")).order_by("-count")
    )

    # Conversions & revenue
    conv = Conversion.objects.filter(user=user, created_at__gte=cutoff)
    conv_agg = conv.aggregate(
        revenue=Sum("revenue"),
        sales=Count("id", filter=Q(conversion_type="sale")),
        total=Count("id"),
    )
    revenue = conv_agg["revenue"] or Decimal("0")
    sales = conv_agg["sales"] or 0

    # Previous period
    prev_conv = Conversion.objects.filter(
        user=user, created_at__gte=prev_cutoff, created_at__lt=cutoff,
    ).aggregate(revenue=Sum("revenue"), sales=Count("id", filter=Q(conversion_type="sale")))
    prev_revenue = prev_conv["revenue"] or Decimal("0")
    prev_sales = prev_conv["sales"] or 0

    # Per-platform
    platform_breakdown = list(
        conv.filter(social_account__isnull=False)
        .values("social_account__platform")
        .annotate(
            revenue=Sum("revenue"),
            sales=Count("id", filter=Q(conversion_type="sale")),
            leads=Count("id", filter=Q(conversion_type="lead")),
        )
        .order_by("-revenue")
    )

    # Response time
    responded = Interaction.objects.filter(
        user=user, responded_at__isnull=False, created_at__gte=cutoff,
    )
    resp_agg = responded.aggregate(count=Count("id"), avg_seconds=Avg(F("responded_at") - F("created_at")))
    total_interactions = Interaction.objects.filter(user=user, created_at__gte=cutoff).count()
    replied = Interaction.objects.filter(
        user=user, created_at__gte=cutoff, status__in=["ai_replied", "user_replied"],
    ).count()
    avg_resp_min = None
    if resp_agg["avg_seconds"]:
        avg_resp_min = round(resp_agg["avg_seconds"].total_seconds() / 60, 1)

    # Funnel
    total_clicks = link_clicks + (conv.filter(conversion_type="click").count())

    return {
        "user": user,
        "days": days,
        "generated_at": now,
        "period_start": cutoff,
        "period_end": now,
        # Engagement
        "posts_published": published.count(),
        "impressions": eng["impressions"],
        "reach": eng["reach"],
        "engagements": eng["engagements"],
        "likes": eng["likes"],
        "comments": eng["comments"],
        "shares": eng["shares"],
        "saves": eng["saves"],
        "avg_engagement_rate": eng["avg_rate"],
        # Conversions
        "link_clicks": link_clicks,
        "total_clicks": total_clicks,
        "leads_total": leads_total,
        "leads_by_source": leads_by_source,
        "sales": sales,
        "revenue": revenue,
        # Comparison
        "prev_revenue": prev_revenue,
        "prev_sales": prev_sales,
        "revenue_delta": float(revenue - prev_revenue),
        "sales_delta": sales - prev_sales,
        # Platform
        "platform_breakdown": platform_breakdown,
        # Response
        "total_interactions": total_interactions,
        "replied_interactions": replied,
        "reply_rate": round(replied / total_interactions * 100, 1) if total_interactions else 0,
        "avg_response_minutes": avg_resp_min,
        # Funnel rates
        "reach_to_engage": round(eng["engagements"] / eng["reach"] * 100, 2) if eng["reach"] else 0,
        "click_to_lead": round(leads_total / total_clicks * 100, 2) if total_clicks else 0,
        "lead_to_sale": round(sales / leads_total * 100, 2) if leads_total else 0,
    }


def generate_report_pdf(user, days=30):
    """Generate a PDF report and return bytes."""
    data = gather_report_data(user, days)

    # Add display helpers
    data["business_name"] = ""
    profile = getattr(user, "profile", None)
    if profile:
        data["business_name"] = getattr(profile, "company_name", "") or ""

    html = render_to_string("analytics/report_pdf.html", data)

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html), dest=buffer, encoding="utf-8")

    if pisa_status.err:
        logger.error("PDF generation failed for user %s: %s errors", user.email, pisa_status.err)
        return None

    return buffer.getvalue()
