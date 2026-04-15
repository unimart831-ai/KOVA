from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from apps.utils import fire_task
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

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

    ctx = {
        "page_title": "Insights & Analytics",
        "totals": totals,
        "top_posts": top_posts,
        "published_count": published_count,
        "has_data": bool(top_posts),
        "connected_platforms": connected_platforms,
        "current_platform": platform,
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
    from apps.analytics.revenue import get_revenue_summary
    from apps.analytics.models import ShopifyStore

    days = int(request.GET.get("days", 30))
    if days not in (7, 14, 30, 90):
        days = 30

    summary = get_revenue_summary(request.user, days=days)

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
