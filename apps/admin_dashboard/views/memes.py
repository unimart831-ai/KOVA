from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.memes.models import KenyanEvent, MemeAdaptation, MemePreferences, TrendingMeme


@staff_required
def memes_overview(request):
    """Meme Intelligence Engine overview — trends, adaptations, usage."""
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Trending meme stats ──────────────────────────────────────────
    total_memes = TrendingMeme.objects.count()
    active_memes = TrendingMeme.objects.filter(
        lifecycle__in=["emerging", "trending", "peaked"],
    ).count()

    lifecycle_breakdown = dict(
        TrendingMeme.objects.values_list("lifecycle")
        .annotate(c=Count("id"))
        .values_list("lifecycle", "c")
    )
    emerging = lifecycle_breakdown.get("emerging", 0)
    trending = lifecycle_breakdown.get("trending", 0)
    peaked = lifecycle_breakdown.get("peaked", 0)
    fading = lifecycle_breakdown.get("fading", 0)
    dead = lifecycle_breakdown.get("dead", 0)

    # Category breakdown
    category_breakdown = list(
        TrendingMeme.objects.filter(
            lifecycle__in=["emerging", "trending", "peaked"],
        )
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Average scores
    avg_scores = TrendingMeme.objects.filter(
        lifecycle__in=["emerging", "trending", "peaked"],
    ).aggregate(
        avg_virality=Avg("virality_score"),
        avg_safety=Avg("brand_safety_score"),
        avg_cultural=Avg("cultural_relevance_score"),
        avg_adaptability=Avg("adaptability_score"),
    )

    # ── Adaptation stats ─────────────────────────────────────────────
    total_adaptations = MemeAdaptation.objects.count()
    adaptations_7d = MemeAdaptation.objects.filter(created_at__gte=week_ago).count()

    adaptation_status = dict(
        MemeAdaptation.objects.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )
    adapt_draft = adaptation_status.get("draft", 0)
    adapt_approved = adaptation_status.get("approved", 0)
    adapt_published = adaptation_status.get("published", 0)
    adapt_rejected = adaptation_status.get("rejected", 0)

    # Avg adaptation quality
    avg_quality = MemeAdaptation.objects.aggregate(
        avg_brand_fit=Avg("brand_relevance_score"),
        avg_humor=Avg("humor_preserved_score"),
    )

    # Adaptations per day (7d)
    adaptations_daily = list(
        MemeAdaptation.objects.filter(created_at__gte=week_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # ── User engagement ──────────────────────────────────────────────
    total_users_with_prefs = MemePreferences.objects.count()
    active_users = MemePreferences.objects.filter(is_active=True).count()

    # Top users by adaptations
    top_users = list(
        MemeAdaptation.objects.values("user__email", "user__full_name", "user__id")
        .annotate(
            adaptation_count=Count("id"),
            published=Count("id", filter=Q(status="published")),
            avg_brand_fit=Avg("brand_relevance_score"),
        )
        .order_by("-adaptation_count")[:10]
    )

    # Risk tolerance distribution
    risk_distribution = dict(
        MemePreferences.objects.values_list("risk_tolerance")
        .annotate(c=Count("id"))
        .values_list("risk_tolerance", "c")
    )

    # ── Top performing memes ─────────────────────────────────────────
    top_memes = (
        TrendingMeme.objects
        .filter(lifecycle__in=["emerging", "trending", "peaked"])
        .order_by("-adaptation_count", "-virality_score")[:10]
    )

    # ── Recent discoveries ───────────────────────────────────────────
    recent_memes = (
        TrendingMeme.objects
        .order_by("-detected_at")[:15]
    )

    # ── Recent adaptations ───────────────────────────────────────────
    recent_adaptations = (
        MemeAdaptation.objects
        .select_related("user", "trending_meme")
        .order_by("-created_at")[:15]
    )

    # ── Upcoming events ──────────────────────────────────────────────
    upcoming_events = KenyanEvent.objects.filter(
        date__gte=today,
        date__lte=today + timedelta(days=30),
    ).order_by("date")[:10]

    # ── Discovery trend (7d) ─────────────────────────────────────────
    discoveries_daily = list(
        TrendingMeme.objects.filter(detected_at__gte=week_ago)
        .annotate(date=TruncDate("detected_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # ── Source platform distribution ─────────────────────────────────
    source_breakdown = list(
        TrendingMeme.objects.filter(
            lifecycle__in=["emerging", "trending", "peaked"],
        )
        .values("source_platform")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return render(request, "admin_dashboard/memes/overview.html", {
        "page_title": "Meme Intelligence",
        # Trending meme stats
        "total_memes": total_memes,
        "active_memes": active_memes,
        "emerging": emerging,
        "trending": trending,
        "peaked": peaked,
        "fading": fading,
        "dead": dead,
        "category_breakdown": category_breakdown,
        "avg_scores": avg_scores,
        "source_breakdown": source_breakdown,
        # Adaptation stats
        "total_adaptations": total_adaptations,
        "adaptations_7d": adaptations_7d,
        "adapt_draft": adapt_draft,
        "adapt_approved": adapt_approved,
        "adapt_published": adapt_published,
        "adapt_rejected": adapt_rejected,
        "avg_quality": avg_quality,
        "adaptations_daily": adaptations_daily,
        # User engagement
        "total_users_with_prefs": total_users_with_prefs,
        "active_users": active_users,
        "top_users": top_users,
        "risk_distribution": risk_distribution,
        # Content
        "top_memes": top_memes,
        "recent_memes": recent_memes,
        "recent_adaptations": recent_adaptations,
        "upcoming_events": upcoming_events,
        "discoveries_daily": discoveries_daily,
    })


@staff_required
def meme_list_admin(request):
    """Paginated list of all trending memes."""
    lifecycle = request.GET.get("lifecycle", "")
    category = request.GET.get("category", "")

    qs = TrendingMeme.objects.order_by("-detected_at")
    if lifecycle:
        qs = qs.filter(lifecycle=lifecycle)
    if category:
        qs = qs.filter(category=category)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/memes/meme_list.html", {
        "page_title": "All Trending Memes",
        "page_obj": page_obj,
        "current_lifecycle": lifecycle,
        "current_category": category,
        "lifecycles": TrendingMeme.Lifecycle.choices,
        "categories": TrendingMeme.Category.choices,
    })


@staff_required
def adaptation_list_admin(request):
    """Paginated list of all meme adaptations."""
    status = request.GET.get("status", "")

    qs = (
        MemeAdaptation.objects
        .select_related("user", "trending_meme")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/memes/adaptation_list.html", {
        "page_title": "All Meme Adaptations",
        "page_obj": page_obj,
        "current_status": status,
        "statuses": MemeAdaptation.Status.choices,
    })
