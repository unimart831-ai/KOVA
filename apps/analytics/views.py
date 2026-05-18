from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from apps.utils import fire_task
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.analytics.models import (
    Competitor,
    CompetitorAnalysis,
    CompetitorInsight,
    Conversion,
    PostMetric,
)


@login_required
def insights(request):
    """Analytics dashboard with real metrics."""
    platform = request.GET.get("platform", "")
    cache_key = f"insights:{request.user.id}:{platform}"
    cached = cache.get(cache_key)

    if cached:
        return render(request, "analytics/insights.html", cached)

    metrics = PostMetric.objects.filter(
        post__user=request.user,
        post__status="published",
    ).select_related("post__social_account", "post__user", "post__seed")

    if platform:
        metrics = metrics.filter(post__social_account__platform=platform)

    totals = metrics.aggregate(
        total_impressions=Sum("impressions"),
        total_reach=Sum("reach"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        total_shares=Sum("shares"),
        total_saves=Sum("saves"),
        total_clicks=Sum("clicks"),
        avg_engagement=Avg("engagement_rate"),
    )

    top_posts = list(metrics.order_by("-engagement_rate")[:5])

    published_count = request.user.posts.filter(status="published")
    if platform:
        published_count = published_count.filter(social_account__platform=platform)
    published_count = published_count.count()

    connected_platforms = list(
        request.user.social_accounts.filter(is_active=True)
        .values_list("platform", flat=True)
        .distinct()
    )

    # P4.4 — plain-English insights, not just numbers
    try:
        from apps.analytics.plain_english import get_plain_english_insights
        plain_insights = get_plain_english_insights(request.user)
    except Exception:
        plain_insights = []

    # Proof stats — "Kova got you X leads and Y bookings this month"
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        from apps.leads.models import Lead
        leads_this_month = Lead.objects.filter(
            user=request.user,
            first_seen_at__gte=month_start,
        ).count()
        hot_leads = Lead.objects.filter(
            user=request.user,
            temperature="hot",
        ).count()
    except Exception:
        leads_this_month = 0
        hot_leads = 0

    try:
        from apps.bookings.models import Booking
        bookings_this_month = Booking.objects.filter(
            booking_link__user=request.user,
            created_at__gte=month_start,
        ).count()
    except Exception:
        bookings_this_month = 0

    ctx = {
        "page_title": "Insights & Analytics",
        "totals": totals,
        "top_posts": top_posts,
        "published_count": published_count,
        "has_data": bool(top_posts),
        "connected_platforms": connected_platforms,
        "current_platform": platform,
        "plain_insights": plain_insights,
        "leads_this_month": leads_this_month,
        "bookings_this_month": bookings_this_month,
        "hot_leads": hot_leads,
    }
    cache.set(cache_key, ctx, 300)  # 5 min

    return render(request, "analytics/insights.html", ctx)


# ─── Competitor Tracking ─────────────────────────────────────────────────────


@login_required
def competitor_dashboard(request):
    """Competitor intelligence command center."""
    competitors = Competitor.objects.filter(
        user=request.user, is_active=True,
    ).order_by("-updated_at")

    # Recent insights (unacted, across all competitors)
    recent_insights = CompetitorInsight.objects.filter(
        user=request.user,
        is_acted_on=False,
        is_dismissed=False,
    ).select_related("competitor").order_by("-created_at")[:10]

    # Stats (use unsliced queries — Django can't filter after slicing)
    unacted_insights = CompetitorInsight.objects.filter(
        user=request.user, is_acted_on=False, is_dismissed=False,
    )
    high_priority_count = unacted_insights.filter(priority="high").count()
    total_insights = unacted_insights.count()
    content_gaps = CompetitorInsight.objects.filter(
        user=request.user,
        insight_type=CompetitorInsight.InsightType.CONTENT_GAP,
        is_acted_on=False, is_dismissed=False,
    ).count()

    return render(request, "analytics/competitors.html", {
        "page_title": "Competitor Intelligence",
        "competitors": competitors,
        "recent_insights": recent_insights,
        "high_priority_count": high_priority_count,
        "total_insights": total_insights,
        "content_gaps": content_gaps,
    })


@login_required
def competitor_add(request):
    """Add a new competitor to track."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Competitor name is required.")
            return redirect("analytics:competitors")

        # Check limit (max 10 competitors per user)
        if Competitor.objects.filter(user=request.user, is_active=True).count() >= 10:
            messages.warning(request, "You can track up to 10 competitors. Remove one to add another.")
            return redirect("analytics:competitors")

        # Check duplicate
        if Competitor.objects.filter(user=request.user, name__iexact=name).exists():
            messages.warning(request, f"You're already tracking '{name}'.")
            return redirect("analytics:competitors")

        competitor = Competitor.objects.create(
            user=request.user,
            name=name,
            website=request.POST.get("website", "").strip(),
            industry=request.POST.get("industry", "").strip(),
            notes=request.POST.get("notes", "").strip(),
            twitter_handle=request.POST.get("twitter_handle", "").strip().lstrip("@"),
            instagram_handle=request.POST.get("instagram_handle", "").strip().lstrip("@"),
            facebook_handle=request.POST.get("facebook_handle", "").strip(),
            linkedin_handle=request.POST.get("linkedin_handle", "").strip(),
            tiktok_handle=request.POST.get("tiktok_handle", "").strip().lstrip("@"),
            youtube_handle=request.POST.get("youtube_handle", "").strip(),
            threads_handle=request.POST.get("threads_handle", "").strip().lstrip("@"),
        )

        messages.success(request, f"Now tracking {name}. Running first analysis...")

        # Trigger initial analysis
        from apps.analytics.tasks import analyze_competitor_task
        fire_task(analyze_competitor_task, str(request.user.id), str(competitor.id))

        return redirect("analytics:competitor_detail", pk=competitor.pk)

    return render(request, "analytics/competitor_add.html", {
        "page_title": "Track New Competitor",
    })


@login_required
def competitor_detail(request, pk):
    """Detailed view of a single competitor with full analysis."""
    competitor = get_object_or_404(
        Competitor, pk=pk, user=request.user,
    )

    analyses = competitor.analyses.order_by("-created_at")[:5]
    latest_analysis = analyses.first()

    insight_base = CompetitorInsight.objects.filter(
        user=request.user,
        competitor=competitor,
        is_dismissed=False,
    ).order_by("-created_at")

    active_insights = insight_base.filter(is_acted_on=False)[:15]
    acted_insights = insight_base.filter(is_acted_on=True)[:15]

    return render(request, "analytics/competitor_detail.html", {
        "page_title": f"Intel: {competitor.name}",
        "competitor": competitor,
        "latest_analysis": latest_analysis,
        "analyses": analyses,
        "active_insights": active_insights,
        "acted_insights": acted_insights,
    })


@login_required
def competitor_edit(request, pk):
    """Edit a tracked competitor's details and handles."""
    competitor = get_object_or_404(
        Competitor, pk=pk, user=request.user,
    )

    if request.method == "POST":
        competitor.name = request.POST.get("name", competitor.name).strip()
        competitor.website = request.POST.get("website", "").strip()
        competitor.industry = request.POST.get("industry", "").strip()
        competitor.notes = request.POST.get("notes", "").strip()
        competitor.twitter_handle = request.POST.get("twitter_handle", "").strip().lstrip("@")
        competitor.instagram_handle = request.POST.get("instagram_handle", "").strip().lstrip("@")
        competitor.facebook_handle = request.POST.get("facebook_handle", "").strip()
        competitor.linkedin_handle = request.POST.get("linkedin_handle", "").strip()
        competitor.tiktok_handle = request.POST.get("tiktok_handle", "").strip().lstrip("@")
        competitor.youtube_handle = request.POST.get("youtube_handle", "").strip()
        competitor.threads_handle = request.POST.get("threads_handle", "").strip().lstrip("@")
        competitor.save()

        messages.success(request, f"Updated {competitor.name}.")
        return redirect("analytics:competitor_detail", pk=competitor.pk)

    return render(request, "analytics/competitor_edit.html", {
        "page_title": f"Edit {competitor.name}",
        "competitor": competitor,
    })


@login_required
def competitor_analyze(request, pk):
    """Trigger a new analysis for a competitor."""
    competitor = get_object_or_404(
        Competitor, pk=pk, user=request.user,
    )

    from apps.analytics.tasks import analyze_competitor_task
    fire_task(analyze_competitor_task, str(request.user.id), str(competitor.id))

    messages.info(request, f"Analyzing {competitor.name}... This takes a moment.")
    return redirect("analytics:competitor_detail", pk=pk)


@login_required
def competitor_delete(request, pk):
    """Soft-delete a competitor (deactivate)."""
    if request.method == "POST":
        competitor = get_object_or_404(
            Competitor, pk=pk, user=request.user,
        )
        competitor.is_active = False
        competitor.save(update_fields=["is_active"])
        messages.success(request, f"Stopped tracking {competitor.name}.")
    return redirect("analytics:competitors")


@login_required
def competitor_landscape(request):
    """Generate competitive landscape overview."""
    from apps.analytics.competitor_intel import generate_landscape_report

    competitors = Competitor.objects.filter(user=request.user, is_active=True)
    if not competitors.exists():
        return render(request, "analytics/competitor_landscape.html", {
            "page_title": "Competitive Landscape",
            "landscape": None,
            "competitors": [],
        })

    try:
        report = generate_landscape_report(request.user)
    except Exception:
        report = None
        messages.warning(request, "Could not generate landscape report right now. Try again shortly.")

    # Annotate competitors with insight counts for the table
    from django.db.models import Count
    competitors = competitors.annotate(
        insight_count=Count("insights", filter=~Q(insights__is_dismissed=True)),
    )

    return render(request, "analytics/competitor_landscape.html", {
        "page_title": "Competitive Landscape",
        "landscape": report,
        "competitors": competitors,
    })


@login_required
def insight_action(request, pk):
    """Mark an insight as acted on or dismissed (HTMX)."""
    if request.method == "POST":
        insight = get_object_or_404(
            CompetitorInsight, pk=pk, user=request.user,
        )
        action = request.POST.get("action")

        if action == "act":
            insight.is_acted_on = True
            insight.save(update_fields=["is_acted_on"])
        elif action == "dismiss":
            insight.is_dismissed = True
            insight.save(update_fields=["is_dismissed"])
        elif action == "create_seed":
            # Turn insight's content idea into a ContentSeed
            if insight.suggested_content_idea:
                from apps.content.models import ContentSeed
                seed = ContentSeed.objects.create(
                    user=request.user,
                    idea=insight.suggested_content_idea,
                    notes=f"[Competitor Intel] Inspired by {insight.competitor.name}: {insight.title}",
                )
                insight.is_acted_on = True
                insight.save(update_fields=["is_acted_on"])

                from apps.content.tasks import generate_from_seed
                fire_task(generate_from_seed, str(seed.id))

                return render(request, "analytics/_insight_acted.html", {
                    "insight": insight,
                    "action": "create_seed",
                })

        return render(request, "analytics/_insight_acted.html", {
            "insight": insight,
            "action": action,
        })

    return redirect("analytics:competitors")


@login_required
def revenue_dashboard(request):
    """Revenue attribution dashboard — enhanced with ROI, trends, funnel, product attribution."""
    from apps.analytics.revenue import get_revenue_summary, get_revenue_headline_insight
    from apps.analytics.models import ShopifyStore

    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30

    summary = get_revenue_summary(request.user, days=days)
    # Headline insight — the single-sentence "what should we tell the owner?"
    # surface at the top of the dashboard. Computed from the same summary so
    # no extra queries.
    insight = get_revenue_headline_insight(request.user, days=days, summary=summary)

    # Recent conversions for the feed
    conversions = Conversion.objects.filter(
        user=request.user,
    ).select_related("post__social_account", "social_account", "product").order_by("-created_at")[:50]

    # Shopify stores
    shopify_stores = ShopifyStore.objects.filter(user=request.user, is_active=True)

    return render(request, "analytics/revenue.html", {
        "conversions": conversions,
        "summary": summary,
        "totals": summary["totals"],
        "platform_revenue": summary["platform_revenue"],
        "top_posts": summary["top_posts"],
        "content_type_revenue": summary["content_type_revenue"],
        "cta_type_revenue": summary["cta_type_revenue"],
        "product_revenue": summary["product_revenue"],
        "daily_trend": summary["daily_trend"],
        "roi": summary["roi"],
        "funnel": summary["funnel"],
        "shopify_stores": shopify_stores,
        "days": days,
        "insight": insight,
    })


@login_required
def shopify_connect(request):
    """Connect a Shopify store for revenue attribution."""
    from apps.analytics.models import ShopifyStore

    if request.method != "POST":
        return redirect("analytics:revenue")

    shop_domain = request.POST.get("shop_domain", "").strip().lower()
    access_token = request.POST.get("access_token", "").strip()
    webhook_secret = request.POST.get("webhook_secret", "").strip()

    if not shop_domain or not access_token:
        messages.error(request, "Shop domain and access token are required.")
        return redirect("analytics:revenue")

    # Normalize domain
    if not shop_domain.endswith(".myshopify.com"):
        shop_domain = f"{shop_domain}.myshopify.com"

    store, created = ShopifyStore.objects.get_or_create(
        user=request.user,
        shop_domain=shop_domain,
        defaults={
            "access_token": access_token,
            "webhook_secret": webhook_secret,
            "is_active": True,
        },
    )
    if not created:
        store.access_token = access_token
        store.webhook_secret = webhook_secret
        store.is_active = True
        store.save(update_fields=["access_token", "webhook_secret", "is_active", "updated_at"])

    messages.success(request, f"Connected {shop_domain} for revenue tracking.")
    return redirect("analytics:revenue")


@login_required
def shopify_disconnect(request, pk):
    """Disconnect a Shopify store."""
    from apps.analytics.models import ShopifyStore

    if request.method != "POST":
        return redirect("analytics:revenue")

    store = get_object_or_404(ShopifyStore, pk=pk, user=request.user)
    store.is_active = False
    store.save(update_fields=["is_active", "updated_at"])

    messages.success(request, f"Disconnected {store.shop_domain}.")
    return redirect("analytics:revenue")


# ─── Pixel JS Serve ──────────────────────────────────────────────────────────

def serve_pixel_js(request):
    """
    Serve the Kova Pixel JavaScript with proper caching headers.
    Served from a URL path so it works regardless of staticfiles setup.
    """
    from django.contrib.staticfiles import finders
    from django.http import HttpResponse

    js_path = finders.find("js/kova-pixel.js")
    if js_path:
        with open(js_path) as f:
            response = HttpResponse(f.read(), content_type="application/javascript")
            response["Cache-Control"] = "public, max-age=86400"  # 24h cache
            response["Access-Control-Allow-Origin"] = "*"
            return response
    return HttpResponse("", status=404, content_type="application/javascript")


# ─── Attribution Dashboard ───────────────────────────────────────────────────


@login_required
def attribution_dashboard(request):
    """
    The single answer to: "How many customers came from social media this month?"

    Combines: reach → engagement → clicks → leads → sales → revenue
    Per-platform breakdown. Response time metrics. Month-over-month comparison.
    """
    from datetime import timedelta
    from decimal import Decimal

    from django.db.models import Avg, F
    from django.db.models.functions import TruncDate

    from apps.engage.models import Interaction
    from apps.leads.models import Lead
    from apps.links.models import LinkClick

    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30

    now = timezone.now()
    cutoff = now - timedelta(days=days)
    prev_cutoff = cutoff - timedelta(days=days)  # Previous period for comparison

    # ── 1. Reach & Engagement (from PostMetric) ──────────────────────────────
    published_posts = request.user.posts.filter(status="published", published_at__gte=cutoff)
    post_ids = list(published_posts.values_list("id", flat=True))

    metrics_qs = PostMetric.objects.filter(post_id__in=post_ids)
    engagement = metrics_qs.aggregate(
        total_impressions=Sum("impressions"),
        total_reach=Sum("reach"),
        total_likes=Sum("likes"),
        total_comments=Sum("comments"),
        total_shares=Sum("shares"),
        total_saves=Sum("saves"),
        total_clicks=Sum("clicks"),
        avg_engagement_rate=Avg("engagement_rate"),
    )
    engagement = {k: v or 0 for k, v in engagement.items()}
    engagement["total_engagements"] = (
        engagement["total_likes"] + engagement["total_comments"]
        + engagement["total_shares"] + engagement["total_saves"]
    )

    # Previous period for comparison
    prev_posts = request.user.posts.filter(
        status="published", published_at__gte=prev_cutoff, published_at__lt=cutoff,
    )
    prev_ids = list(prev_posts.values_list("id", flat=True))
    prev_metrics = PostMetric.objects.filter(post_id__in=prev_ids).aggregate(
        total_reach=Sum("reach"),
        total_engagements=Sum(F("likes") + F("comments") + F("shares") + F("saves")),
    )

    # ── 2. Link Clicks ───────────────────────────────────────────────────────
    link_clicks = LinkClick.objects.filter(
        link__page__user=request.user, clicked_at__gte=cutoff,
    ).count()

    # ── 3. Leads ─────────────────────────────────────────────────────────────
    leads_qs = Lead.objects.filter(user=request.user, first_seen_at__gte=cutoff)
    leads_total = leads_qs.count()
    leads_by_source = list(
        leads_qs.values("source_type").annotate(count=Count("id")).order_by("-count")
    )
    leads_by_platform = list(
        leads_qs.exclude(source_platform="").values("source_platform")
        .annotate(count=Count("id")).order_by("-count")
    )

    prev_leads = Lead.objects.filter(
        user=request.user, first_seen_at__gte=prev_cutoff, first_seen_at__lt=cutoff,
    ).count()

    # ── 4. Conversions & Revenue ─────────────────────────────────────────────
    conversions = Conversion.objects.filter(user=request.user, created_at__gte=cutoff)
    conv_totals = conversions.aggregate(
        total_revenue=Sum("revenue"),
        total_sales=Count("id", filter=Q(conversion_type="sale")),
        total_leads=Count("id", filter=Q(conversion_type="lead")),
        total_clicks=Count("id", filter=Q(conversion_type="click")),
        total_all=Count("id"),
    )
    conv_totals = {k: v or (Decimal("0") if "revenue" in k else 0) for k, v in conv_totals.items()}

    prev_conv = Conversion.objects.filter(
        user=request.user, created_at__gte=prev_cutoff, created_at__lt=cutoff,
    ).aggregate(
        total_revenue=Sum("revenue"),
        total_sales=Count("id", filter=Q(conversion_type="sale")),
    )

    # Per-platform revenue
    platform_breakdown = list(
        conversions.filter(social_account__isnull=False)
        .values("social_account__platform")
        .annotate(
            revenue=Sum("revenue"),
            sales=Count("id", filter=Q(conversion_type="sale")),
            leads=Count("id", filter=Q(conversion_type="lead")),
            clicks=Count("id", filter=Q(conversion_type="click")),
        )
        .order_by("-revenue")
    )

    # Daily revenue trend
    daily_revenue = list(
        conversions.filter(revenue__gt=0)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Sum("revenue"), count=Count("id"))
        .order_by("date")
    )

    # ── 5. Response Time Metrics ─────────────────────────────────────────────
    responded = Interaction.objects.filter(
        user=request.user,
        responded_at__isnull=False,
        created_at__gte=cutoff,
    )
    response_stats = responded.aggregate(
        count=Count("id"),
        avg_seconds=Avg(F("responded_at") - F("created_at")),
    )
    total_interactions = Interaction.objects.filter(
        user=request.user, created_at__gte=cutoff,
    ).count()
    replied_interactions = Interaction.objects.filter(
        user=request.user, created_at__gte=cutoff,
        status__in=["ai_replied", "user_replied"],
    ).count()

    # Convert avg timedelta to minutes
    avg_response_minutes = None
    if response_stats["avg_seconds"]:
        avg_response_minutes = round(response_stats["avg_seconds"].total_seconds() / 60, 1)

    response_metrics = {
        "total_interactions": total_interactions,
        "replied": replied_interactions,
        "reply_rate": round(replied_interactions / total_interactions * 100, 1) if total_interactions else 0,
        "avg_response_minutes": avg_response_minutes,
        "responded_count": response_stats["count"] or 0,
    }

    # ── 6. The Answer ────────────────────────────────────────────────────────
    customers_from_social = conv_totals["total_sales"]
    revenue_from_social = conv_totals["total_revenue"]

    # Deltas vs previous period
    prev_revenue = prev_conv.get("total_revenue") or Decimal("0")
    prev_sales = prev_conv.get("total_sales") or 0
    prev_reach_val = prev_metrics.get("total_reach") or 0

    deltas = {
        "revenue": float(revenue_from_social - prev_revenue) if prev_revenue else None,
        "sales": customers_from_social - prev_sales if prev_sales else None,
        "reach": (engagement["total_reach"] - prev_reach_val) if prev_reach_val else None,
        "leads": leads_total - prev_leads if prev_leads else None,
    }

    # ── 7. Funnel ────────────────────────────────────────────────────────────
    funnel = {
        "reach": engagement["total_reach"],
        "engagements": engagement["total_engagements"],
        "clicks": conv_totals["total_clicks"] + link_clicks,
        "leads": leads_total,
        "sales": customers_from_social,
        "revenue": conv_totals["total_revenue"],
    }
    # Conversion rates between stages
    funnel["reach_to_engage"] = (
        round(funnel["engagements"] / funnel["reach"] * 100, 2)
        if funnel["reach"] else 0
    )
    funnel["engage_to_click"] = (
        round(funnel["clicks"] / funnel["engagements"] * 100, 2)
        if funnel["engagements"] else 0
    )
    funnel["click_to_lead"] = (
        round(funnel["leads"] / funnel["clicks"] * 100, 2)
        if funnel["clicks"] else 0
    )
    funnel["lead_to_sale"] = (
        round(funnel["sales"] / funnel["leads"] * 100, 2)
        if funnel["leads"] else 0
    )

    # ── 8. Posts published count ─────────────────────────────────────────────
    posts_published = published_posts.count()

    return render(request, "analytics/attribution.html", {
        "page_title": "Social Media Attribution",
        "days": days,
        "customers_from_social": customers_from_social,
        "revenue_from_social": revenue_from_social,
        "engagement": engagement,
        "leads_total": leads_total,
        "leads_by_source": leads_by_source,
        "leads_by_platform": leads_by_platform,
        "conv_totals": conv_totals,
        "platform_breakdown": platform_breakdown,
        "daily_revenue": daily_revenue,
        "response_metrics": response_metrics,
        "funnel": funnel,
        "deltas": deltas,
        "posts_published": posts_published,
        "link_clicks": link_clicks,
    })


# ─── PDF Report Download ────────────────────────────────────────────────────


@login_required
def download_report(request):
    """Generate and download a PDF performance report."""
    from django.http import HttpResponse

    from apps.analytics.reports import generate_report_pdf

    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30

    pdf_bytes = generate_report_pdf(request.user, days)
    if not pdf_bytes:
        messages.error(request, "Could not generate report. Try again.")
        return redirect("analytics:attribution")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"kova-report-{days}d-{timezone.now().strftime('%Y%m%d')}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ─── Content Intelligence ────────────────────────────────────────────────────


@login_required
def content_intelligence(request):
    """Content Intelligence — what's working, what to post next, and when."""
    from collections import defaultdict
    from datetime import timedelta

    from apps.content.models import Post

    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30

    cutoff = timezone.now() - timedelta(days=days)

    posts = (
        Post.objects.filter(
            user=request.user,
            status="published",
            published_at__gte=cutoff,
        )
        .select_related("metrics", "social_account")
        .exclude(content_dna={})
    )

    # 1. Best formats
    format_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0, "total_reach": 0})
    # 2. Best posting times
    hour_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0})
    # 3. Best themes
    topic_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0, "total_reach": 0})
    # 4. Attribute correlation
    attribute_stats = defaultdict(lambda: {"with": [], "without": []})
    # 5. Platform stats
    plat_stats = defaultdict(lambda: {"count": 0, "total_engagement": 0})

    for post in posts:
        try:
            m = post.metrics
        except PostMetric.DoesNotExist:
            continue

        engagement = m.likes + m.comments + m.shares + m.saves
        dna = post.content_dna or {}

        # Format
        fmt = dna.get("format", "unknown")
        format_stats[fmt]["count"] += 1
        format_stats[fmt]["total_engagement"] += engagement
        format_stats[fmt]["total_reach"] += m.reach

        # Hour
        if post.published_at:
            hour = post.published_at.hour
            hour_stats[hour]["count"] += 1
            hour_stats[hour]["total_engagement"] += engagement

        # Topic
        topic = dna.get("topic", "")
        if topic:
            topic_stats[topic]["count"] += 1
            topic_stats[topic]["total_engagement"] += engagement
            topic_stats[topic]["total_reach"] += m.reach

        # Boolean attributes
        for attr in ["has_cta", "has_question", "has_stats", "has_emoji", "has_hashtags", "has_image"]:
            if dna.get(attr):
                attribute_stats[attr]["with"].append(engagement)
            else:
                attribute_stats[attr]["without"].append(engagement)

        # Platform
        platform = post.social_account.platform if post.social_account else "unknown"
        plat_stats[platform]["count"] += 1
        plat_stats[platform]["total_engagement"] += engagement

    # Process format stats
    best_formats = []
    for fmt, stats in format_stats.items():
        if stats["count"] >= 2:
            best_formats.append({
                "format": fmt,
                "count": stats["count"],
                "avg_engagement": round(stats["total_engagement"] / stats["count"], 1),
                "avg_reach": round(stats["total_reach"] / stats["count"]),
            })
    best_formats.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # Process hour stats
    best_hours = []
    for hour, stats in hour_stats.items():
        if stats["count"] >= 2:
            best_hours.append({
                "hour": hour,
                "label": f"{hour:02d}:00",
                "count": stats["count"],
                "avg_engagement": round(stats["total_engagement"] / stats["count"], 1),
            })
    best_hours.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # Process topic stats
    best_topics = []
    for topic, stats in topic_stats.items():
        if stats["count"] >= 2:
            best_topics.append({
                "topic": topic,
                "count": stats["count"],
                "avg_engagement": round(stats["total_engagement"] / stats["count"], 1),
            })
    best_topics.sort(key=lambda x: x["avg_engagement"], reverse=True)

    # Process attribute impact
    attribute_impact = []
    for attr, stats in attribute_stats.items():
        with_list = stats["with"]
        without_list = stats["without"]
        if len(with_list) >= 2 and len(without_list) >= 2:
            avg_with = sum(with_list) / len(with_list)
            avg_without = sum(without_list) / len(without_list)
            multiplier = round(avg_with / avg_without, 1) if avg_without > 0 else 0
            attribute_impact.append({
                "attribute": attr.replace("has_", "").replace("_", " ").title(),
                "with_avg": round(avg_with, 1),
                "without_avg": round(avg_without, 1),
                "multiplier": multiplier,
                "positive": avg_with > avg_without,
            })
    attribute_impact.sort(key=lambda x: x["multiplier"], reverse=True)

    # Process platform stats
    platform_display = {}
    for plat, stats in plat_stats.items():
        platform_display[plat] = {
            "count": stats["count"],
            "avg_engagement": round(stats["total_engagement"] / stats["count"], 1) if stats["count"] else 0,
        }

    # Build recommendations
    recommendations = []
    if best_formats:
        top = best_formats[0]
        recommendations.append(
            f"Your {top['format']} posts get the most engagement ({top['avg_engagement']:.0f} avg) — post more of them."
        )
    if best_hours:
        top = best_hours[0]
        recommendations.append(
            f"Your best posting time is {top['label']} — schedule content around this hour."
        )
    for attr in attribute_impact[:2]:
        if attr["positive"] and attr["multiplier"] >= 1.3:
            recommendations.append(
                f"Posts with {attr['attribute'].lower()} get {attr['multiplier']}x more engagement."
            )
    if best_topics:
        top = best_topics[0]
        recommendations.append(
            f"'{top['topic']}' is your top theme ({top['avg_engagement']:.0f} avg engagement) — create more content around it."
        )

    return render(request, "analytics/content_intelligence.html", {
        "page_title": "Content Intelligence",
        "days": days,
        "total_posts": posts.count(),
        "best_formats": best_formats[:8],
        "best_hours": best_hours[:6],
        "best_topics": best_topics[:8],
        "attribute_impact": attribute_impact,
        "recommendations": recommendations,
        "platform_stats": platform_display,
        "has_data": posts.count() >= 5,
    })


# ─── SCREENSHOT TO COMPETE ──────────────────────────────────────────────────


@login_required
def screenshot_compete(request):
    """Upload a competitor screenshot for AI analysis."""
    from apps.analytics.models import CompetitorScreenshot
    from apps.analytics.tasks import process_competitor_screenshot

    if request.method == "POST":
        image = request.FILES.get("screenshot")
        if not image:
            messages.error(request, "Please upload a screenshot.")
            return redirect("analytics:screenshot_compete")

        if image.size > 10 * 1024 * 1024:
            messages.error(request, "Image too large. Maximum 10 MB.")
            return redirect("analytics:screenshot_compete")

        user_notes = request.POST.get("notes", "").strip()
        ss = CompetitorScreenshot.objects.create(
            user=request.user,
            image=image,
            user_notes=user_notes,
        )
        fire_task(process_competitor_screenshot, str(ss.pk))
        messages.success(
            request,
            "Screenshot uploaded! AI is analyzing the competitor's strategy — "
            "counter-content will be generated automatically."
        )
        return redirect("analytics:screenshot_compete")

    screenshots = (
        CompetitorScreenshot.objects
        .filter(user=request.user)
        .select_related("competitor", "counter_seed")
        .order_by("-created_at")[:30]
    )

    return render(request, "analytics/screenshot_compete.html", {
        "screenshots": screenshots,
    })


# ─── PERFORMANCE TO EMAIL ───────────────────────────────────────────────────


@login_required
def performance_recycle(request):
    """View top-performing posts recycled into email campaigns."""
    from apps.analytics.models import PerformanceRecycle

    status_filter = request.GET.get("status", "")
    qs = (
        PerformanceRecycle.objects
        .filter(user=request.user)
        .select_related("source_post", "email_campaign")
        .order_by("-detected_at")
    )

    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "analytics/performance_recycle.html", {
        "recycles": qs[:50],
        "status_filter": status_filter,
        "status_choices": PerformanceRecycle.Status.choices,
    })


@login_required
@require_POST
def recycle_action(request, pk):
    """Dismiss or send a performance recycle."""
    from apps.analytics.models import PerformanceRecycle

    recycle = get_object_or_404(PerformanceRecycle, pk=pk, user=request.user)
    action = request.POST.get("action")

    if action == "dismiss" and recycle.status in ("detected", "ready"):
        recycle.status = "dismissed"
        recycle.save(update_fields=["status", "updated_at"])
        messages.info(request, "Recycle dismissed.")
    elif action == "send" and recycle.status == "ready":
        recycle.status = "sent"
        recycle.save(update_fields=["status", "updated_at"])
        messages.success(request, "Email marked as sent!")

    return redirect("analytics:performance_recycle")
