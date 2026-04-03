from collections import Counter, defaultdict
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.analytics.models import (
    Competitor,
    CompetitorAnalysis,
    CompetitorInsight,
    PostMetric,
)
from apps.content.models import Post
from apps.platforms.models import SocialAccount


@staff_required
def analytics_overview(request):
    """Analytics & intelligence dashboard — performance, content DNA, competitors."""
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    # ── Engagement overview cards (single query) ──────────────────────
    metrics_30d = PostMetric.objects.filter(post__published_at__gte=last_30d)
    metrics_agg = metrics_30d.aggregate(
        total_impressions=Sum("impressions"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        total_shares=Sum("shares"),
        avg_engagement=Avg("engagement_rate"),
        posts_with_metrics=Count("id"),
    )
    total_impressions = metrics_agg["total_impressions"] or 0
    total_likes = metrics_agg["total_likes"] or 0
    total_comments = metrics_agg["total_comments"] or 0
    total_shares = metrics_agg["total_shares"] or 0
    avg_engagement = metrics_agg["avg_engagement"] or 0
    posts_with_metrics = metrics_agg["posts_with_metrics"]

    # ── Engagement trend (30 days — single query) ────────────────────
    thirty_days_ago_date = (now - timedelta(days=29)).date()
    daily_engagement = {
        row["day"]: row
        for row in PostMetric.objects.filter(
            post__published_at__date__gte=thirty_days_ago_date,
        ).annotate(day=TruncDate("post__published_at"))
        .values("day").annotate(
            impressions=Sum("impressions"),
            likes=Sum("likes"),
            comments=Sum("comments"),
            shares=Sum("shares"),
        )
    }
    engagement_trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        row = daily_engagement.get(d, {})
        engagement_trend.append({
            "date": d.isoformat(),
            "impressions": row.get("impressions", 0) or 0,
            "likes": row.get("likes", 0) or 0,
            "comments": row.get("comments", 0) or 0,
            "shares": row.get("shares", 0) or 0,
        })

    # ── Avg engagement rate by platform ──────────────────────────────
    platform_engagement = list(
        PostMetric.objects.filter(engagement_rate__isnull=False)
        .values(platform=F("post__social_account__platform"))
        .annotate(avg_rate=Avg("engagement_rate"), count=Count("id"))
        .filter(count__gte=1)
        .order_by("-avg_rate")
    )

    # ── Content DNA leaderboard ──────────────────────────────────────
    # Aggregate the top performing content DNA combos across all posts
    dna_performance = []
    posts_with_dna = Post.objects.filter(
        content_dna__isnull=False,
        status="published",
        metrics__engagement_rate__isnull=False,
    ).select_related("metrics")

    dna_combos = defaultdict(list)
    for post in posts_with_dna[:2000]:  # Cap to avoid memory issues
        dna = post.content_dna
        if not isinstance(dna, dict):
            continue
        fmt = dna.get("format", "unknown")
        tone = dna.get("tone", "unknown")
        key = f"{fmt} + {tone}"
        dna_combos[key].append(post.metrics.engagement_rate)

    for combo, rates in dna_combos.items():
        if len(rates) >= 2:  # Need at least 2 posts for meaningful average
            dna_performance.append({
                "combo": combo,
                "avg_rate": round(sum(rates) / len(rates), 2),
                "count": len(rates),
                "best": round(max(rates), 2),
            })
    dna_performance.sort(key=lambda x: x["avg_rate"], reverse=True)
    dna_top10 = dna_performance[:10]

    # ── Predicted vs Actual scatter data ─────────────────────────────
    scatter_data = list(
        Post.objects.filter(
            predicted_engagement_score__isnull=False,
            metrics__engagement_rate__isnull=False,
            status="published",
        ).values_list(
            "predicted_engagement_score",
            "metrics__engagement_rate",
        )[:500]
    )
    scatter_json = [
        {"x": round(float(pred), 2), "y": round(float(actual), 2)}
        for pred, actual in scatter_data
    ]

    # ── Engagement rate distribution (histogram) ─────────────────────
    rate_buckets = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    rate_distribution = []
    for i in range(len(rate_buckets) - 1):
        low = rate_buckets[i]
        high = rate_buckets[i + 1]
        count = PostMetric.objects.filter(
            engagement_rate__gte=low,
            engagement_rate__lt=high,
        ).count()
        rate_distribution.append({
            "label": f"{low}-{high}%",
            "count": count,
        })
    # 10+ bucket
    rate_distribution.append({
        "label": "10%+",
        "count": PostMetric.objects.filter(engagement_rate__gte=10).count(),
    })

    # ── Competitor intelligence summary ──────────────────────────────
    total_competitors = Competitor.objects.filter(is_active=True).count()
    analyses_30d = CompetitorAnalysis.objects.filter(created_at__gte=last_30d).count()
    unacted_insights = CompetitorInsight.objects.filter(
        is_acted_on=False, is_dismissed=False,
    ).count()

    insight_types = list(
        CompetitorInsight.objects.filter(is_dismissed=False)
        .values("insight_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    insight_priority = list(
        CompetitorInsight.objects.filter(is_acted_on=False, is_dismissed=False)
        .values("priority")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "page_title": "Analytics & Intelligence",
        # Cards
        "total_impressions": total_impressions,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "avg_engagement": round(avg_engagement, 2),
        "posts_with_metrics": posts_with_metrics,
        # Charts
        "engagement_trend_json": engagement_trend,
        "platform_engagement": platform_engagement,
        "scatter_json": scatter_json,
        "rate_distribution_json": rate_distribution,
        # DNA
        "dna_top10": dna_top10,
        # Competitors
        "total_competitors": total_competitors,
        "analyses_30d": analyses_30d,
        "unacted_insights": unacted_insights,
        "insight_types": insight_types,
        "insight_priority": insight_priority,
    }
    return render(request, "admin_dashboard/analytics/overview.html", context)


@staff_required
def content_dna_analysis(request):
    """Deep dive into Content DNA patterns and performance."""
    posts_with_dna = Post.objects.filter(
        content_dna__isnull=False,
        status="published",
        metrics__engagement_rate__isnull=False,
    ).select_related("metrics", "social_account")

    # Build heatmap: format × tone → avg engagement
    heatmap = defaultdict(lambda: defaultdict(list))
    format_counter = Counter()
    tone_counter = Counter()

    for post in posts_with_dna[:3000]:
        dna = post.content_dna
        if not isinstance(dna, dict):
            continue
        fmt = dna.get("format", "unknown")
        tone = dna.get("tone", "unknown")
        rate = post.metrics.engagement_rate
        heatmap[fmt][tone].append(rate)
        format_counter[fmt] += 1
        tone_counter[tone] += 1

    # Build heatmap data for Chart.js matrix
    all_formats = [f for f, _ in format_counter.most_common(10)]
    all_tones = [t for t, _ in tone_counter.most_common(10)]

    heatmap_data = []
    for fi, fmt in enumerate(all_formats):
        for ti, tone in enumerate(all_tones):
            rates = heatmap[fmt][tone]
            if rates:
                avg = round(sum(rates) / len(rates), 2)
                heatmap_data.append({
                    "format": fmt,
                    "tone": tone,
                    "avg_rate": avg,
                    "count": len(rates),
                })

    # Sort by avg engagement for the table
    heatmap_data.sort(key=lambda x: x["avg_rate"], reverse=True)

    # Per-format stats
    format_stats = []
    for fmt in all_formats:
        all_rates = []
        for tone_rates in heatmap[fmt].values():
            all_rates.extend(tone_rates)
        if all_rates:
            format_stats.append({
                "format": fmt,
                "count": len(all_rates),
                "avg_rate": round(sum(all_rates) / len(all_rates), 2),
                "best": round(max(all_rates), 2),
            })
    format_stats.sort(key=lambda x: x["avg_rate"], reverse=True)

    # Per-tone stats
    tone_stats = []
    for tone in all_tones:
        all_rates = []
        for fmt_data in heatmap.values():
            all_rates.extend(fmt_data.get(tone, []))
        if all_rates:
            tone_stats.append({
                "tone": tone,
                "count": len(all_rates),
                "avg_rate": round(sum(all_rates) / len(all_rates), 2),
                "best": round(max(all_rates), 2),
            })
    tone_stats.sort(key=lambda x: x["avg_rate"], reverse=True)

    context = {
        "page_title": "Content DNA Analysis",
        "heatmap_data": heatmap_data,
        "format_stats": format_stats,
        "tone_stats": tone_stats,
        "all_formats": all_formats,
        "all_tones": all_tones,
        "total_posts": sum(format_counter.values()),
    }
    return render(request, "admin_dashboard/analytics/content_dna.html", context)


@staff_required
def competitor_overview(request):
    """Competitor intelligence dashboard."""
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    # Competitor list
    competitors = Competitor.objects.filter(is_active=True).select_related("user").order_by("-last_analyzed_at")

    search = request.GET.get("q", "").strip()
    if search:
        competitors = competitors.filter(
            Q(name__icontains=search)
            | Q(industry__icontains=search)
            | Q(user__email__icontains=search)
        )

    # Recent analyses
    recent_analyses = list(
        CompetitorAnalysis.objects.select_related("competitor", "user")
        .order_by("-created_at")[:20]
    )

    # Unacted insights
    pending_insights = list(
        CompetitorInsight.objects.filter(is_acted_on=False, is_dismissed=False)
        .select_related("competitor", "user")
        .order_by("-priority", "-created_at")[:30]
    )

    # Stats
    total_competitors = competitors.count()
    analyses_30d = CompetitorAnalysis.objects.filter(created_at__gte=last_30d).count()
    total_insights = CompetitorInsight.objects.filter(is_dismissed=False).count()
    high_priority = CompetitorInsight.objects.filter(
        priority="high", is_acted_on=False, is_dismissed=False,
    ).count()

    paginator = Paginator(competitors, 20)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Competitor Intelligence",
        "page_obj": page,
        "search": search,
        "total_competitors": total_competitors,
        "analyses_30d": analyses_30d,
        "total_insights": total_insights,
        "high_priority": high_priority,
        "recent_analyses": recent_analyses,
        "pending_insights": pending_insights,
    }
    return render(request, "admin_dashboard/analytics/competitors.html", context)
