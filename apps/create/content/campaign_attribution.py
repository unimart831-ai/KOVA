"""
Campaign-level revenue attribution — tie conversions to MarketingCampaign.

Funnel: campaign page view → click → WhatsApp lead → M-Pesa sale.
Powers brief lines, Studio revenue strips, and seed proposal ranking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class CampaignFunnelStats:
    campaign_id: str
    title: str
    slug: str
    views: int = 0
    clicks: int = 0
    leads: int = 0
    sales: int = 0
    revenue: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "title": self.title,
            "slug": self.slug,
            "views": self.views,
            "clicks": self.clicks,
            "leads": self.leads,
            "sales": self.sales,
            "revenue": float(self.revenue),
        }


def resolve_marketing_campaign(
    user,
    *,
    campaign_id: str | None = None,
    campaign_slug: str | None = None,
    utm_campaign: str = "",
    post=None,
    product=None,
    metadata: dict | None = None,
):
    """Best-effort campaign resolution for attribution."""
    from apps.create.content.models import MarketingCampaign

    meta = metadata or {}
    cid = campaign_id or meta.get("campaign_id")
    slug = campaign_slug or meta.get("campaign_slug") or (utm_campaign or "").strip()

    if cid:
        campaign = MarketingCampaign.objects.filter(user=user, pk=cid).first()
        if campaign:
            return campaign

    if slug:
        campaign = MarketingCampaign.objects.filter(user=user, slug=slug).first()
        if campaign:
            return campaign

    if post and getattr(post, "seed_id", None):
        try:
            campaign = post.seed.marketing_campaign
            if campaign:
                return campaign
        except Exception:
            pass

    if product:
        campaign = (
            MarketingCampaign.objects.filter(user=user)
            .filter(
                Q(content_seed__product_id=product.pk)
                | Q(business_asset__product_id=product.pk)
            )
            .order_by("-created_at")
            .first()
        )
        if campaign:
            return campaign

    return None


def create_attributed_conversion(
    user,
    conversion_type,
    *,
    revenue=0,
    event_name: str = "",
    post=None,
    product=None,
    campaign=None,
    social_account=None,
    utm_source: str = "",
    utm_medium: str = "",
    utm_campaign: str = "",
    utm_content: str = "",
    metadata: dict | None = None,
):
    """Create Conversion with marketing_campaign FK + metadata campaign_id."""
    from apps.insight.analytics.models import Conversion

    meta = dict(metadata or {})
    resolved = campaign or resolve_marketing_campaign(
        user,
        campaign_id=meta.get("campaign_id"),
        campaign_slug=meta.get("campaign_slug"),
        utm_campaign=utm_campaign or meta.get("utm_campaign", ""),
        post=post,
        product=product,
        metadata=meta,
    )

    if resolved:
        meta.setdefault("campaign_id", str(resolved.pk))
        meta.setdefault("campaign_slug", resolved.slug)
        if not utm_campaign:
            utm_campaign = resolved.slug[:255]

    conv = Conversion.objects.create(
        user=user,
        post=post,
        product=product,
        marketing_campaign=resolved,
        social_account=social_account or (post.social_account if post else None),
        conversion_type=conversion_type,
        revenue=revenue,
        event_name=event_name,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign[:255] if utm_campaign else "",
        utm_content=utm_content,
        metadata=meta,
    )

    if resolved and conversion_type == Conversion.ConversionType.SALE:
        try:
            sync_campaign_revenue_totals(resolved)
        except Exception:
            logger.exception("sync_campaign_revenue_totals failed for %s", resolved.pk)

    return conv


def _conversion_qs_for_campaign(campaign, *, cutoff=None):
    from apps.insight.analytics.models import Conversion

    cid = str(campaign.pk)
    slug = campaign.slug
    qs = Conversion.objects.filter(user=campaign.user).filter(
        Q(marketing_campaign_id=campaign.pk)
        | Q(metadata__campaign_id=cid)
        | Q(utm_campaign=slug)
    )
    if cutoff:
        qs = qs.filter(created_at__gte=cutoff)
    return qs


def campaign_funnel_stats(campaign, *, days: int = 30) -> CampaignFunnelStats:
    """Aggregate funnel metrics for one campaign."""
    cutoff = timezone.now() - timedelta(days=days)
    qs = _conversion_qs_for_campaign(campaign, cutoff=cutoff)

    views = qs.filter(
        Q(event_name="campaign_page_view")
        | Q(metadata__source="campaign")
    ).count()
    clicks = qs.filter(conversion_type="click").count()
    leads = qs.filter(conversion_type="lead").count()
    sales = qs.filter(conversion_type="sale").count()
    revenue = qs.filter(conversion_type="sale").aggregate(t=Sum("revenue"))["t"] or Decimal("0")

    return CampaignFunnelStats(
        campaign_id=str(campaign.pk),
        title=campaign.title,
        slug=campaign.slug,
        views=views,
        clicks=clicks,
        leads=leads,
        sales=sales,
        revenue=revenue,
    )


def top_campaigns_by_revenue(user, *, days: int = 7, limit: int = 5) -> list[dict]:
    """Campaigns ranked by attributed revenue in the period."""
    from apps.insight.analytics.models import Conversion
    from apps.create.content.models import MarketingCampaign

    cutoff = timezone.now() - timedelta(days=days)
    rows = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__isnull=False,
        )
        .values("marketing_campaign_id")
        .annotate(
            revenue=Sum("revenue"),
            sales=Count("id", filter=Q(conversion_type="sale")),
            leads=Count("id", filter=Q(conversion_type="lead")),
        )
        .order_by("-revenue")[:limit]
    )

    campaign_ids = [r["marketing_campaign_id"] for r in rows if r["marketing_campaign_id"]]
    campaigns = {
        c.pk: c
        for c in MarketingCampaign.objects.filter(pk__in=campaign_ids).only("pk", "title", "slug")
    }

    result = []
    for row in rows:
        camp = campaigns.get(row["marketing_campaign_id"])
        if not camp:
            continue
        rev = float(row["revenue"] or 0)
        if rev <= 0 and (row["sales"] or 0) == 0 and (row["leads"] or 0) == 0:
            continue
        result.append({
            "campaign_id": str(camp.pk),
            "title": camp.title,
            "slug": camp.slug,
            "revenue": rev,
            "sales": row["sales"] or 0,
            "leads": row["leads"] or 0,
            "line": format_campaign_revenue_line(camp.title, rev),
        })
    return result


def format_campaign_revenue_line(title: str, revenue_kes: float) -> str:
    title = (title or "Campaign").strip()
    if revenue_kes <= 0:
        return f"{title} — no attributed sales yet"
    return f"{title} → KES {revenue_kes:,.0f}"


def campaign_revenue_brief_lines(user, *, days: int = 7, limit: int = 3) -> list[str]:
    """Daily brief lines: 'Weekend handbag campaign → KES 12,400'."""
    return [row["line"] for row in top_campaigns_by_revenue(user, days=days, limit=limit)]


def campaign_revenue_snapshot(campaign, user, *, days: int = 30) -> dict:
    """Studio campaign card revenue strip."""
    stats = campaign_funnel_stats(campaign, days=days)
    return {
        "revenue_kes": float(stats.revenue),
        "sales": stats.sales,
        "leads": stats.leads,
        "views": stats.views,
        "line": format_campaign_revenue_line(campaign.title, float(stats.revenue)),
        "has_revenue": stats.revenue > 0 or stats.sales > 0,
    }


def get_campaign_intent_performance(user, *, days: int = 90) -> dict:
    """
    Revenue by campaign objective for brain feedback.
    Returns {winning_objectives: [...], low_objectives: [...]}.
    """
    from apps.insight.analytics.models import Conversion
    from apps.create.content.models import MarketingCampaign

    cutoff = timezone.now() - timedelta(days=days)
    rows = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__isnull=False,
            conversion_type="sale",
        )
        .values("marketing_campaign__objective")
        .annotate(revenue=Sum("revenue"))
        .order_by("-revenue")
    )
    perf = [(r["marketing_campaign__objective"], float(r["revenue"] or 0)) for r in rows]
    if not perf:
        return {"winning_objectives": [], "low_objectives": [], "winning_angles": [], "low_angles": []}

    winning = [o for o, rev in perf if rev > 0][:2]
    low = [o for o, rev in reversed(perf) if rev == 0][:2]

    angle_rows = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__isnull=False,
            conversion_type="sale",
        )
        .values("marketing_campaign_id")
        .annotate(revenue=Sum("revenue"))
        .order_by("-revenue")[:10]
    )
    camp_ids = [r["marketing_campaign_id"] for r in angle_rows]
    camps = MarketingCampaign.objects.filter(pk__in=camp_ids).only("pk", "proposal_meta")
    angle_perf: list[tuple[str, float]] = []
    rev_by_id = {str(r["marketing_campaign_id"]): float(r["revenue"] or 0) for r in angle_rows}
    for camp in camps:
        proposal = camp.proposal_meta or {}
        angle = proposal.get("angle") or proposal.get("proposal", {}).get("angle") or ""
        if angle:
            angle_perf.append((angle, rev_by_id.get(str(camp.pk), 0)))

    angle_perf.sort(key=lambda x: -x[1])
    winning_angles = [a for a, r in angle_perf if r > 0][:3]
    low_angles = [a for a, r in angle_perf if r == 0][:3]

    return {
        "winning_objectives": winning,
        "low_objectives": low,
        "winning_angles": winning_angles,
        "low_angles": low_angles,
    }


def rank_proposals_by_revenue_history(user, proposals: list) -> list:
    """Boost seed proposals that match historically high-revenue campaign angles."""
    if not proposals:
        return proposals

    perf = get_campaign_intent_performance(user)
    winning_intents = set(perf.get("winning_objectives") or [])
    winning_angles = set(perf.get("winning_angles") or [])
    low_angles = set(perf.get("low_angles") or [])

    def score(p) -> int:
        s = 0
        if p.intent in winning_intents:
            s += 10
        if p.angle in winning_angles:
            s += 15
        if p.angle in low_angles:
            s -= 8
        return s

    return sorted(proposals, key=score, reverse=True)


def get_campaign_performance_rows(user, *, days: int = 30, limit: int = 15) -> list[dict]:
    """Campaign funnel rows for the revenue dashboard."""
    from apps.insight.analytics.models import Conversion
    from apps.create.content.models import MarketingCampaign

    cutoff = timezone.now() - timedelta(days=days)
    agg = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__isnull=False,
        )
        .values("marketing_campaign_id")
        .annotate(
            revenue=Sum("revenue", filter=Q(conversion_type="sale")),
            sales=Count("id", filter=Q(conversion_type="sale")),
            leads=Count("id", filter=Q(conversion_type="lead")),
            clicks=Count("id", filter=Q(conversion_type="click")),
            views=Count(
                "id",
                filter=Q(event_name="campaign_page_view") | Q(metadata__source="campaign"),
            ),
        )
        .order_by("-revenue", "-sales", "-leads")[:limit]
    )

    campaign_ids = [r["marketing_campaign_id"] for r in agg]
    campaigns = {
        c.pk: c
        for c in MarketingCampaign.objects.filter(pk__in=campaign_ids).only(
            "pk", "title", "slug", "objective", "status",
        )
    }

    plat_rows = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__in=campaign_ids,
            conversion_type="sale",
            revenue__gt=0,
        )
        .values("marketing_campaign_id", "social_account__platform")
        .annotate(revenue=Sum("revenue"), sales=Count("id"))
        .order_by("-revenue")
    )
    platforms_by_campaign: dict = {}
    for pr in plat_rows:
        cid = pr["marketing_campaign_id"]
        plat = pr["social_account__platform"] or "direct"
        platforms_by_campaign.setdefault(cid, []).append({
            "platform": plat,
            "revenue": float(pr["revenue"] or 0),
            "sales": pr["sales"] or 0,
        })

    rows = []
    for item in agg:
        camp = campaigns.get(item["marketing_campaign_id"])
        if not camp:
            continue
        rev = float(item["revenue"] or 0)
        rows.append({
            "campaign_id": str(camp.pk),
            "title": camp.title,
            "slug": camp.slug,
            "objective": camp.objective,
            "objective_label": camp.get_objective_display(),
            "status": camp.status,
            "revenue": rev,
            "sales": item["sales"] or 0,
            "leads": item["leads"] or 0,
            "clicks": item["clicks"] or 0,
            "views": item["views"] or 0,
            "platforms": platforms_by_campaign.get(camp.pk, []),
            "line": format_campaign_revenue_line(camp.title, rev),
        })
    return rows


def get_objective_platform_comparison(user, *, days: int = 30) -> list[dict]:
    """
    Revenue by social platform grouped by campaign objective.
    Powers "which platform works for sales vs leads campaigns" insight.
    """
    from apps.insight.analytics.models import Conversion
    from apps.create.content.models import MarketingCampaign

    cutoff = timezone.now() - timedelta(days=days)
    raw = (
        Conversion.objects.filter(
            user=user,
            created_at__gte=cutoff,
            marketing_campaign_id__isnull=False,
            conversion_type="sale",
        )
        .values("marketing_campaign__objective", "social_account__platform")
        .annotate(revenue=Sum("revenue"), sales=Count("id"))
        .order_by("marketing_campaign__objective", "-revenue")
    )

    objective_labels = dict(MarketingCampaign.Objective.choices)
    grouped: dict[str, dict] = {}
    for row in raw:
        objective = row["marketing_campaign__objective"] or "sales"
        plat = row["social_account__platform"] or "direct"
        rev = float(row["revenue"] or 0)
        if rev <= 0 and (row["sales"] or 0) == 0:
            continue
        bucket = grouped.setdefault(objective, {
            "objective": objective,
            "objective_label": objective_labels.get(objective, objective.title()),
            "platforms": [],
            "total_revenue": 0.0,
        })
        bucket["platforms"].append({
            "platform": plat,
            "revenue": rev,
            "sales": row["sales"] or 0,
        })
        bucket["total_revenue"] += rev

    return sorted(grouped.values(), key=lambda g: -g["total_revenue"])


def get_campaign_performance_detail(campaign, *, days: int = 30) -> dict:
    """Single-campaign drill-down for analytics."""
    stats = campaign_funnel_stats(campaign, days=days)
    cutoff = timezone.now() - timedelta(days=days)
    from apps.insight.analytics.models import Conversion

    platform_rows = (
        _conversion_qs_for_campaign(campaign, cutoff=cutoff)
        .filter(conversion_type="sale", revenue__gt=0)
        .values("social_account__platform", "post__social_account__platform")
        .annotate(revenue=Sum("revenue"), sales=Count("id"))
        .order_by("-revenue")
    )
    platforms = []
    for pr in platform_rows:
        plat = pr["social_account__platform"] or pr["post__social_account__platform"] or "direct"
        platforms.append({
            "platform": plat,
            "revenue": float(pr["revenue"] or 0),
            "sales": pr["sales"] or 0,
        })

    recent = (
        _conversion_qs_for_campaign(campaign, cutoff=cutoff)
        .select_related("product", "post__social_account")
        .order_by("-created_at")[:20]
    )

    return {
        "stats": stats.to_dict(),
        "platforms": platforms,
        "recent_conversions": recent,
        "objective_label": campaign.get_objective_display(),
    }


def sync_campaign_revenue_totals(campaign) -> None:
    """Persist lifetime revenue snapshot on campaign proposal_meta."""
    stats = campaign_funnel_stats(campaign, days=365)
    meta = dict(campaign.proposal_meta or {})
    meta["revenue_attribution"] = {
        "revenue_kes": float(stats.revenue),
        "sales": stats.sales,
        "leads": stats.leads,
        "views": stats.views,
        "updated_at": timezone.now().isoformat(),
    }
    campaign.proposal_meta = meta
    campaign.save(update_fields=["proposal_meta", "updated_at"])
