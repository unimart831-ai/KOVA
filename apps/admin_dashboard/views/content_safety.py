"""Admin dashboard — Content Safety review and controls."""

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.content.models import ContentSafetyIncident, SystemSafetyConfig
from apps.content.safety import (
    clear_snap_block_for_dismissed_incident,
    content_safety_checks_running,
    content_safety_staff_paused,
    staff_incident_image_url,
)


def _safety_stats():
    today = timezone.now().date()
    pending = ContentSafetyIncident.objects.filter(
        review_status=ContentSafetyIncident.ReviewStatus.PENDING,
    ).count()
    today_count = ContentSafetyIncident.objects.filter(
        created_at__date=today,
    ).count()
    config = SystemSafetyConfig.load()
    return {
        "pending_review": pending,
        "incidents_today": today_count,
        "auto_publish_paused": config.auto_publish_paused,
        "paused_by": config.paused_by,
        "paused_at": config.paused_at,
        "content_safety_checks_enabled": config.content_safety_checks_enabled,
        "content_safety_paused_by": config.content_safety_paused_by,
        "content_safety_paused_at": config.content_safety_paused_at,
    }


@staff_required
def content_safety_overview(request):
    stats = _safety_stats()
    recent = (
        ContentSafetyIncident.objects.select_related("user", "post")
        .order_by("-created_at")[:10]
    )
    high_severity = ContentSafetyIncident.objects.filter(
        severity__gte=70,
        review_status=ContentSafetyIncident.ReviewStatus.PENDING,
    ).count()

    return render(request, "admin_dashboard/content_safety/overview.html", {
        "page_title": "Content Safety",
        "stats": stats,
        "recent_incidents": recent,
        "high_severity_pending": high_severity,
        "content_safety_enabled": getattr(settings, "CONTENT_SAFETY_ENABLED", False),
        "content_safety_model": getattr(
            settings, "CONTENT_SAFETY_MODEL", "google/gemini-2.0-flash-001",
        ),
    })


@staff_required
def content_safety_review(request):
    qs = ContentSafetyIncident.objects.select_related("user", "post", "reviewed_by")

    status = request.GET.get("status")
    if status in dict(ContentSafetyIncident.ReviewStatus.choices):
        qs = qs.filter(review_status=status)
    else:
        qs = qs.filter(review_status=ContentSafetyIncident.ReviewStatus.PENDING)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(user__email__icontains=q)
            | Q(reasons__icontains=q)
            | Q(categories__icontains=q),
        )

    qs = qs.order_by("-severity", "-created_at")
    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page"))

    status_counts = {
        row["review_status"]: row["count"]
        for row in ContentSafetyIncident.objects.values("review_status").annotate(
            count=Count("id"),
        )
    }

    return render(request, "admin_dashboard/content_safety/review.html", {
        "page_title": "Content Safety — Review Queue",
        "page_obj": page,
        "status_choices": ContentSafetyIncident.ReviewStatus.choices,
        "current_status": status or ContentSafetyIncident.ReviewStatus.PENDING,
        "current_q": q,
        "status_counts": status_counts,
    })


@staff_required
def content_safety_incident_detail(request, pk):
    incident = get_object_or_404(
        ContentSafetyIncident.objects.select_related("user", "post", "reviewed_by"),
        pk=pk,
    )
    profile = UserProfile.objects.filter(user=incident.user).first()

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        if action == "dismiss":
            incident.review_status = ContentSafetyIncident.ReviewStatus.DISMISSED
            incident.reviewed_at = timezone.now()
            incident.reviewed_by = request.user
            incident.action_taken = "dismissed_by_staff"
            incident.save(update_fields=[
                "review_status", "reviewed_at", "reviewed_by", "action_taken",
            ])
            clear_snap_block_for_dismissed_incident(incident)
            messages.success(request, "Incident dismissed as false positive.")

        elif action == "confirm":
            incident.review_status = ContentSafetyIncident.ReviewStatus.CONFIRMED
            incident.reviewed_at = timezone.now()
            incident.reviewed_by = request.user
            incident.action_taken = "violation_confirmed"
            incident.save(update_fields=[
                "review_status", "reviewed_at", "reviewed_by", "action_taken",
            ])
            if profile:
                profile.content_safety_strike_count = (
                    profile.content_safety_strike_count or 0
                ) + 1
                profile.save(update_fields=["content_safety_strike_count"])
            messages.success(request, "Violation confirmed — strike recorded.")

        elif action == "suspend_user" and profile:
            profile.suspended_for_policy = True
            profile.save(update_fields=["suspended_for_policy"])
            incident.action_taken = "user_suspended"
            incident.save(update_fields=["action_taken"])
            messages.warning(request, f"User {incident.user.email} suspended for policy.")

        elif action == "clear_strikes" and profile:
            profile.content_safety_strike_count = 0
            profile.suspended_for_policy = False
            profile.snap_blocked_until = None
            profile.snap_blocked_incident = None
            profile.save(update_fields=[
                "content_safety_strike_count", "suspended_for_policy",
                "snap_blocked_until", "snap_blocked_incident",
            ])
            messages.success(request, "Strikes cleared and suspension lifted.")

        elif action == "pause_user_autopublish" and profile:
            profile.auto_publish_paused = True
            profile.save(update_fields=["auto_publish_paused"])
            messages.warning(request, "User auto-publish paused.")

        elif action == "resume_user_autopublish" and profile:
            profile.auto_publish_paused = False
            profile.save(update_fields=["auto_publish_paused"])
            messages.success(request, "User auto-publish resumed.")

        return redirect("admin_dashboard:content_safety_incident_detail", pk=pk)

    return render(request, "admin_dashboard/content_safety/incident_detail.html", {
        "page_title": f"Incident — {incident.user.email}",
        "incident": incident,
        "profile": profile,
        "staff_image_url": staff_incident_image_url(incident),
    })


@senior_staff_required
def content_safety_global_toggle(request):
    if request.method != "POST":
        return redirect("admin_dashboard:content_safety_overview")

    config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
    config.auto_publish_paused = not config.auto_publish_paused
    if config.auto_publish_paused:
        config.paused_by = request.user
        config.paused_at = timezone.now()
    else:
        config.paused_by = None
        config.paused_at = None
    config.save()

    state = "paused" if config.auto_publish_paused else "resumed"
    messages.warning(request, f"Platform auto-publish {state}.")
    return redirect("admin_dashboard:content_safety_overview")


@senior_staff_required
def content_safety_checks_toggle(request):
    if request.method != "POST":
        return redirect("admin_dashboard:content_safety_overview")

    config, _ = SystemSafetyConfig.objects.get_or_create(pk=1)
    config.content_safety_checks_enabled = not config.content_safety_checks_enabled
    if config.content_safety_checks_enabled:
        config.content_safety_paused_by = None
        config.content_safety_paused_at = None
        messages.success(request, "Content safety checks resumed.")
    else:
        config.content_safety_paused_by = request.user
        config.content_safety_paused_at = timezone.now()
        messages.warning(request, "All content safety checks paused.")
    config.save()

    return redirect("admin_dashboard:content_safety_overview")
