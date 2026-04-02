from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.engage.models import Interaction, Superfan


@staff_required
def engagement_overview(request):
    """Engagement dashboard — interactions, sentiment, auto-reply rates."""
    now = timezone.now()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # ── Overview cards ───────────────────────────────────────────────
    total_7d = Interaction.objects.filter(created_at__gte=last_7d).count()

    # Sentiment breakdown (7d)
    sentiment_qs = Interaction.objects.filter(created_at__gte=last_7d).exclude(sentiment="")
    sentiment_total = sentiment_qs.count()
    positive = sentiment_qs.filter(sentiment="positive").count()
    neutral = sentiment_qs.filter(sentiment="neutral").count()
    negative = sentiment_qs.filter(sentiment="negative").count()
    pct = lambda v: round(v / sentiment_total * 100, 1) if sentiment_total else 0
    sentiment_pct = {
        "positive": pct(positive),
        "neutral": pct(neutral),
        "negative": pct(negative),
    }

    # Auto-reply rate
    ai_replied = Interaction.objects.filter(
        created_at__gte=last_7d, status="ai_replied",
    ).count()
    auto_reply_rate = round(ai_replied / total_7d * 100, 1) if total_7d else 0

    # Flagged
    flagged = Interaction.objects.filter(status="flagged").count()

    # Superfan counts by tier
    superfan_rising = Superfan.objects.filter(tier="rising").count()
    superfan_loyal = Superfan.objects.filter(tier="loyal").count()
    superfan_super = Superfan.objects.filter(tier="superfan").count()
    total_superfans = superfan_rising + superfan_loyal + superfan_super

    # ── Sentiment trend (30 days) ────────────────────────────────────
    sentiment_trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).date()
        day_qs = Interaction.objects.filter(created_at__date=d).exclude(sentiment="")
        day_total = day_qs.count()
        if day_total:
            sentiment_trend.append({
                "date": d.isoformat(),
                "positive": round(day_qs.filter(sentiment="positive").count() / day_total * 100, 1),
                "neutral": round(day_qs.filter(sentiment="neutral").count() / day_total * 100, 1),
                "negative": round(day_qs.filter(sentiment="negative").count() / day_total * 100, 1),
            })
        else:
            sentiment_trend.append({
                "date": d.isoformat(),
                "positive": None, "neutral": None, "negative": None,
            })

    # ── Interaction type breakdown (7d) ──────────────────────────────
    type_breakdown = list(
        Interaction.objects.filter(created_at__gte=last_7d)
        .values("interaction_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "page_title": "Engagement",
        "total_7d": total_7d,
        "sentiment_pct": sentiment_pct,
        "sentiment_chart_json": [positive, neutral, negative],
        "auto_reply_rate": auto_reply_rate,
        "ai_replied": ai_replied,
        "flagged": flagged,
        "total_superfans": total_superfans,
        "superfan_rising": superfan_rising,
        "superfan_loyal": superfan_loyal,
        "superfan_super": superfan_super,
        "sentiment_trend_json": sentiment_trend,
        "type_breakdown": type_breakdown,
    }
    return render(request, "admin_dashboard/engage/overview.html", context)


@staff_required
def interaction_feed(request):
    """All interactions across all users — search/filter/paginate."""
    qs = Interaction.objects.select_related("user", "social_account").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(author_name__icontains=search)
            | Q(author_username__icontains=search)
            | Q(content__icontains=search)
            | Q(user__email__icontains=search)
        )

    sentiment = request.GET.get("sentiment", "")
    if sentiment:
        qs = qs.filter(sentiment=sentiment)

    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    itype = request.GET.get("type", "")
    if itype:
        qs = qs.filter(interaction_type=itype)

    platform = request.GET.get("platform", "")
    if platform:
        qs = qs.filter(social_account__platform=platform)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Interaction Feed",
        "page_obj": page,
        "search": search,
        "current_sentiment": sentiment,
        "current_status": status_filter,
        "current_type": itype,
        "current_platform": platform,
        "total_count": paginator.count,
        "status_choices": Interaction.Status.choices,
        "type_choices": Interaction.InteractionType.choices,
        "sentiment_choices": [("positive", "Positive"), ("neutral", "Neutral"), ("negative", "Negative")],
    }
    return render(request, "admin_dashboard/engage/interactions.html", context)


@staff_required
def superfan_leaderboard(request):
    """Cross-user superfan view with tier filtering."""
    qs = Superfan.objects.select_related("user").all()

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(author_name__icontains=search)
            | Q(author_username__icontains=search)
            | Q(user__email__icontains=search)
        )

    tier = request.GET.get("tier", "")
    if tier:
        qs = qs.filter(tier=tier)

    sort = request.GET.get("sort", "-interaction_count")
    valid_sorts = {
        "interaction_count", "-interaction_count",
        "last_interaction_at", "-last_interaction_at",
        "first_seen", "-first_seen",
    }
    if sort not in valid_sorts:
        sort = "-interaction_count"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "Superfan Leaderboard",
        "page_obj": page,
        "search": search,
        "current_tier": tier,
        "current_sort": sort,
        "total_count": paginator.count,
        "tier_choices": Superfan.Tier.choices,
    }
    return render(request, "admin_dashboard/engage/superfans.html", context)
