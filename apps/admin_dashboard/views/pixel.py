"""
Admin dashboard views for Kova Pixel — platform-wide tracking management.

Provides admin visibility into:
- Global pixel usage stats (events, visitors, active pixels)
- Per-user pixel status and event counts
- Event feed with filtering
- Top tracked pages across all users
"""

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Max, Sum, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.accounts.models import UserProfile
from apps.analytics.models import WebsiteEvent


@staff_required
def pixel_overview(request):
    """Platform-wide Kova Pixel dashboard for admins."""
    now = timezone.now()
    days = int(request.GET.get("days", 7))
    if days not in (1, 7, 14, 30):
        days = 7
    cutoff = now - timedelta(days=days)

    # ── Global pixel stats ────────────────────────────────────────────
    events_qs = WebsiteEvent.objects.filter(created_at__gte=cutoff)

    totals = events_qs.aggregate(
        total_events=Count("id"),
        unique_visitors=Count("visitor_id", distinct=True),
        total_revenue=Sum("revenue"),
        page_views=Count("id", filter=Q(event_type="page_view")),
        form_submits=Count("id", filter=Q(event_type="form_submit")),
        purchases=Count("id", filter=Q(event_type="purchase")),
        sign_ups=Count("id", filter=Q(event_type="sign_up")),
        button_clicks=Count("id", filter=Q(event_type="button_click")),
        custom_events=Count("id", filter=Q(event_type="custom")),
    )
    totals = {k: v or 0 for k, v in totals.items()}

    # ── Active pixels (users with a token and events in period) ───────
    active_pixel_users = (
        events_qs.values("user__id").distinct().count()
    )
    total_pixel_tokens = UserProfile.objects.exclude(
        pixel_token__isnull=True
    ).exclude(pixel_token="").count()

    # ── Events by type breakdown ──────────────────────────────────────
    events_by_type = list(
        events_qs.values("event_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Daily trend ───────────────────────────────────────────────────
    daily_trend = list(
        events_qs.annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(events=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("date")
    )

    # ── Top users by event count ──────────────────────────────────────
    top_users = list(
        events_qs.values("user__email", "user__full_name", "user__id")
        .annotate(
            event_count=Count("id"),
            visitor_count=Count("visitor_id", distinct=True),
            revenue=Sum("revenue"),
        )
        .order_by("-event_count")[:20]
    )

    # ── Top pages (across all users) ──────────────────────────────────
    top_pages = list(
        events_qs.filter(event_type="page_view")
        .values("page_url")
        .annotate(count=Count("id"))
        .order_by("-count")[:15]
    )

    # ── Top UTM sources ───────────────────────────────────────────────
    top_sources = list(
        events_qs.exclude(utm_source="")
        .values("utm_source")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # ── Device breakdown ──────────────────────────────────────────────
    device_breakdown = list(
        events_qs.exclude(device_type="")
        .values("device_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return render(request, "admin_dashboard/pixel/overview.html", {
        "page_title": "Kova Pixel",
        "days": days,
        "totals": totals,
        "active_pixel_users": active_pixel_users,
        "total_pixel_tokens": total_pixel_tokens,
        "events_by_type": events_by_type,
        "daily_trend": daily_trend,
        "top_users": top_users,
        "top_pages": top_pages,
        "top_sources": top_sources,
        "device_breakdown": device_breakdown,
    })


@staff_required
def pixel_events(request):
    """Browse all pixel events across all users — filterable, paginated."""
    qs = (
        WebsiteEvent.objects
        .select_related("user", "post")
        .order_by("-created_at")
    )

    # Filters
    event_type = request.GET.get("type")
    if event_type and event_type in {c[0] for c in WebsiteEvent.EventType.choices}:
        qs = qs.filter(event_type=event_type)

    user_email = request.GET.get("email")
    if user_email:
        qs = qs.filter(user__email__icontains=user_email)

    has_revenue = request.GET.get("revenue")
    if has_revenue == "1":
        qs = qs.filter(revenue__gt=0)

    utm_source = request.GET.get("utm_source")
    if utm_source:
        qs = qs.filter(utm_source__icontains=utm_source)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/pixel/events.html", {
        "page_title": "Pixel Events",
        "page_obj": page,
        "current_type": event_type,
        "current_email": user_email or "",
        "current_revenue": has_revenue,
        "current_utm": utm_source or "",
    })


@staff_required
def pixel_users(request):
    """List all users with pixel tokens and their usage stats."""
    profiles = (
        UserProfile.objects
        .exclude(pixel_token__isnull=True)
        .exclude(pixel_token="")
        .select_related("user")
        .annotate(
            event_count=Count(
                "user__website_events",
                filter=Q(user__website_events__created_at__gte=timezone.now() - timedelta(days=30)),
            ),
            latest_event=Max("user__website_events__created_at"),
            total_revenue=Sum(
                "user__website_events__revenue",
                filter=Q(user__website_events__created_at__gte=timezone.now() - timedelta(days=30)),
            ),
        )
        .order_by("-event_count")
    )

    paginator = Paginator(profiles, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_dashboard/pixel/users.html", {
        "page_title": "Pixel Users",
        "page_obj": page,
    })
