"""
Admin dashboard views for the 5 innovation features:
1. Voice to Campaign
2. Screenshot to Compete
3. Receipt to Restock
4. Trend Ride
5. Performance to Email
"""
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


# ══════════════════════════════════════════════════════════════════════════════
# INNOVATIONS OVERVIEW (single dashboard for all 5)
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def innovations_overview(request):
    """Central dashboard for all innovation features."""
    from apps.content.models import VoiceBrief
    from apps.analytics.models import CompetitorScreenshot, PerformanceRecycle
    from apps.products.models import RestockScan
    from apps.memes.models import TrendAlert

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # Voice to Campaign stats
    voice_total = VoiceBrief.objects.count()
    voice_completed = VoiceBrief.objects.filter(status="completed").count()
    voice_7d = VoiceBrief.objects.filter(created_at__gte=week_ago).count()

    # Screenshot to Compete stats
    screenshot_total = CompetitorScreenshot.objects.count()
    screenshot_completed = CompetitorScreenshot.objects.filter(status="completed").count()
    screenshot_7d = CompetitorScreenshot.objects.filter(created_at__gte=week_ago).count()

    # Receipt to Restock stats
    restock_total = RestockScan.objects.count()
    restock_completed = RestockScan.objects.filter(status="completed").count()
    restock_7d = RestockScan.objects.filter(created_at__gte=week_ago).count()
    restock_products_updated = RestockScan.objects.filter(
        status="completed"
    ).aggregate(total=Count("products_updated"))["total"] or 0

    # Trend Ride stats
    trend_total = TrendAlert.objects.count()
    trend_ready = TrendAlert.objects.filter(status="ready").count()
    trend_approved = TrendAlert.objects.filter(status="approved").count()
    trend_7d = TrendAlert.objects.filter(detected_at__gte=week_ago).count()

    # Performance to Email stats
    recycle_total = PerformanceRecycle.objects.count()
    recycle_ready = PerformanceRecycle.objects.filter(status="ready").count()
    recycle_sent = PerformanceRecycle.objects.filter(status="sent").count()
    recycle_7d = PerformanceRecycle.objects.filter(detected_at__gte=week_ago).count()
    avg_multiplier = PerformanceRecycle.objects.aggregate(
        avg=Avg("performance_multiplier")
    )["avg"]

    # Recent activity across all features
    recent_voice = VoiceBrief.objects.select_related("user").order_by("-created_at")[:5]
    recent_screenshots = CompetitorScreenshot.objects.select_related("user").order_by("-created_at")[:5]
    recent_restocks = RestockScan.objects.select_related("user").order_by("-created_at")[:5]
    recent_trends = TrendAlert.objects.select_related("user").order_by("-detected_at")[:5]
    recent_recycles = PerformanceRecycle.objects.select_related("user", "source_post").order_by("-detected_at")[:5]

    return render(request, "admin_dashboard/innovations/overview.html", {
        # Voice to Campaign
        "voice_total": voice_total,
        "voice_completed": voice_completed,
        "voice_7d": voice_7d,
        "voice_success_rate": round(voice_completed / voice_total * 100) if voice_total else 0,
        # Screenshot to Compete
        "screenshot_total": screenshot_total,
        "screenshot_completed": screenshot_completed,
        "screenshot_7d": screenshot_7d,
        # Receipt to Restock
        "restock_total": restock_total,
        "restock_completed": restock_completed,
        "restock_7d": restock_7d,
        "restock_products_updated": restock_products_updated,
        # Trend Ride
        "trend_total": trend_total,
        "trend_ready": trend_ready,
        "trend_approved": trend_approved,
        "trend_7d": trend_7d,
        # Performance to Email
        "recycle_total": recycle_total,
        "recycle_ready": recycle_ready,
        "recycle_sent": recycle_sent,
        "recycle_7d": recycle_7d,
        "avg_multiplier": round(float(avg_multiplier), 1) if avg_multiplier else 0,
        # Recent activity
        "recent_voice": recent_voice,
        "recent_screenshots": recent_screenshots,
        "recent_restocks": recent_restocks,
        "recent_trends": recent_trends,
        "recent_recycles": recent_recycles,
    })


# ══════════════════════════════════════════════════════════════════════════════
# VOICE TO CAMPAIGN
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def voice_brief_list(request):
    """List all voice briefs with filtering."""
    from apps.content.models import VoiceBrief

    status_filter = request.GET.get("status", "")
    qs = VoiceBrief.objects.select_related("user", "campaign").order_by("-created_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/innovations/voice_list.html", {
        "page": page,
        "status_filter": status_filter,
        "status_choices": VoiceBrief.Status.choices,
    })


@staff_required
def voice_brief_detail(request, pk):
    """Detail view for a single voice brief."""
    from apps.content.models import VoiceBrief
    vb = get_object_or_404(VoiceBrief.objects.select_related(
        "user", "campaign", "email_campaign",
    ), pk=pk)

    return render(request, "admin_dashboard/innovations/voice_detail.html", {"vb": vb})


# ══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT TO COMPETE
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def screenshot_list(request):
    """List all competitor screenshots."""
    from apps.analytics.models import CompetitorScreenshot

    status_filter = request.GET.get("status", "")
    qs = CompetitorScreenshot.objects.select_related("user", "competitor").order_by("-created_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/innovations/screenshot_list.html", {
        "page": page,
        "status_filter": status_filter,
        "status_choices": CompetitorScreenshot.Status.choices,
    })


@staff_required
def screenshot_detail(request, pk):
    """Detail view for a competitor screenshot analysis."""
    from apps.analytics.models import CompetitorScreenshot
    ss = get_object_or_404(CompetitorScreenshot.objects.select_related(
        "user", "competitor", "counter_seed",
    ), pk=pk)

    return render(request, "admin_dashboard/innovations/screenshot_detail.html", {"ss": ss})


# ══════════════════════════════════════════════════════════════════════════════
# RECEIPT TO RESTOCK
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def restock_scan_list(request):
    """List all restock scans."""
    from apps.products.models import RestockScan

    status_filter = request.GET.get("status", "")
    qs = RestockScan.objects.select_related("user").order_by("-created_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/innovations/restock_list.html", {
        "page": page,
        "status_filter": status_filter,
        "status_choices": RestockScan.Status.choices,
    })


@staff_required
def restock_scan_detail(request, pk):
    """Detail view for a restock scan."""
    from apps.products.models import RestockScan
    scan = get_object_or_404(RestockScan.objects.select_related(
        "user", "content_seed",
    ), pk=pk)

    return render(request, "admin_dashboard/innovations/restock_detail.html", {"scan": scan})


# ══════════════════════════════════════════════════════════════════════════════
# TREND RIDE
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def trend_alert_list(request):
    """List all trend alerts."""
    from apps.memes.models import TrendAlert

    status_filter = request.GET.get("status", "")
    qs = TrendAlert.objects.select_related("user", "trending_meme").order_by("-detected_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/innovations/trend_list.html", {
        "page": page,
        "status_filter": status_filter,
        "status_choices": TrendAlert.Status.choices,
    })


@staff_required
def trend_alert_detail(request, pk):
    """Detail view for a trend alert."""
    from apps.memes.models import TrendAlert
    alert = get_object_or_404(TrendAlert.objects.select_related(
        "user", "trending_meme", "kenyan_event", "content_seed",
    ), pk=pk)

    return render(request, "admin_dashboard/innovations/trend_detail.html", {"alert": alert})


# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE TO EMAIL
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def recycle_list(request):
    """List all performance recycle records."""
    from apps.analytics.models import PerformanceRecycle

    status_filter = request.GET.get("status", "")
    qs = PerformanceRecycle.objects.select_related(
        "user", "source_post", "email_campaign",
    ).order_by("-detected_at")

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/innovations/recycle_list.html", {
        "page": page,
        "status_filter": status_filter,
        "status_choices": PerformanceRecycle.Status.choices,
    })


@staff_required
def recycle_detail(request, pk):
    """Detail view for a performance recycle record."""
    from apps.analytics.models import PerformanceRecycle
    recycle = get_object_or_404(PerformanceRecycle.objects.select_related(
        "user", "source_post", "post_metric", "email_campaign",
    ), pk=pk)

    return render(request, "admin_dashboard/innovations/recycle_detail.html", {"recycle": recycle})
