"""Admin dashboard views for the Calendar Intelligence (holiday awareness) app."""
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.admin_dashboard.decorators import staff_required
from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayDraft,
    HolidayOccurrence,
    UserHolidayPreference,
)


@staff_required
def calendar_overview(request):
    """Calendar intelligence overview — holidays seeded, drafts in flight,
    user opt-ins, watcher health."""
    now = timezone.now()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Holiday catalog stats ────────────────────────────────────────
    total_holidays = Holiday.objects.count()
    active_holidays = Holiday.objects.filter(is_active=True).count()

    category_breakdown = list(
        Holiday.objects.filter(is_active=True)
        .values("category")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    sensitivity_breakdown = dict(
        Holiday.objects.filter(is_active=True)
        .values_list("sensitivity_level")
        .annotate(c=Count("id"))
        .values_list("sensitivity_level", "c")
    )

    # Source: curated vs python-holidays
    source_breakdown = list(
        Holiday.objects.filter(is_active=True)
        .values("source")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ── Occurrence horizon ──────────────────────────────────────────
    occ_next_30 = HolidayOccurrence.objects.filter(
        date__range=(today, today + timedelta(days=30)),
    ).count()
    occ_next_90 = HolidayOccurrence.objects.filter(
        date__range=(today, today + timedelta(days=90)),
    ).count()

    upcoming_global = list(
        HolidayOccurrence.objects
        .filter(date__range=(today, today + timedelta(days=14)))
        .select_related("holiday")
        .order_by("date")[:12]
    )

    # ── Holiday draft stats ─────────────────────────────────────────
    total_drafts = HolidayDraft.objects.count()
    drafts_7d = HolidayDraft.objects.filter(created_at__gte=week_ago).count()

    draft_status = dict(
        HolidayDraft.objects.values_list("status")
        .annotate(c=Count("id"))
        .values_list("status", "c")
    )
    draft_queued = draft_status.get(HolidayDraft.Status.QUEUED, 0)
    draft_generating = draft_status.get(HolidayDraft.Status.GENERATING, 0)
    draft_ready = draft_status.get(HolidayDraft.Status.DRAFTS_READY, 0)
    draft_approved = draft_status.get(HolidayDraft.Status.APPROVED, 0)
    draft_dismissed = draft_status.get(HolidayDraft.Status.DISMISSED, 0)
    draft_failed = draft_status.get(HolidayDraft.Status.FAILED, 0)
    draft_expired = draft_status.get(HolidayDraft.Status.EXPIRED, 0)

    # Drafts per day (7d)
    drafts_daily = list(
        HolidayDraft.objects.filter(created_at__gte=week_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    # Recent drafts (with user + moment)
    recent_drafts = list(
        HolidayDraft.objects
        .select_related("user", "holiday_occurrence__holiday", "custom_event")
        .order_by("-created_at")[:15]
    )

    # Failed drafts that need attention (most recent first)
    failed_drafts = list(
        HolidayDraft.objects.filter(status=HolidayDraft.Status.FAILED)
        .select_related("user", "holiday_occurrence__holiday", "custom_event")
        .order_by("-updated_at")[:10]
    )

    # ── User opt-in stats ───────────────────────────────────────────
    total_prefs = UserHolidayPreference.objects.count()
    enabled_prefs = UserHolidayPreference.objects.filter(is_enabled=True).count()
    muted_prefs = UserHolidayPreference.objects.filter(
        is_enabled=True, muted_until__gt=today,
    ).count()

    # Top holidays by opt-in count
    top_optin_holidays = list(
        UserHolidayPreference.objects.filter(is_enabled=True)
        .values("holiday__name", "holiday__slug", "holiday__id")
        .annotate(optins=Count("id"))
        .order_by("-optins")[:10]
    )

    # ── Custom event stats ──────────────────────────────────────────
    total_custom_events = CustomEvent.objects.count()
    active_custom_events = CustomEvent.objects.filter(is_active=True).count()
    upcoming_custom = CustomEvent.objects.filter(
        is_active=True, date__range=(today, today + timedelta(days=30)),
    ).count()

    # ── Top users by draft activity ─────────────────────────────────
    top_users = list(
        HolidayDraft.objects.filter(created_at__gte=month_ago)
        .values("user__email", "user__full_name", "user__id")
        .annotate(
            draft_count=Count("id"),
            approved=Count("id", filter=Q(status=HolidayDraft.Status.APPROVED)),
            ready=Count("id", filter=Q(status=HolidayDraft.Status.DRAFTS_READY)),
        )
        .order_by("-draft_count")[:10]
    )

    # ── Watcher health: last successful run ─────────────────────────
    last_draft_created = (
        HolidayDraft.objects
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )

    return render(request, "admin_dashboard/calendar_intel/overview.html", {
        "page_title": "Calendar Intelligence",
        # Catalog
        "total_holidays": total_holidays,
        "active_holidays": active_holidays,
        "category_breakdown": category_breakdown,
        "sensitivity_breakdown": sensitivity_breakdown,
        "source_breakdown": source_breakdown,
        # Occurrences
        "occ_next_30": occ_next_30,
        "occ_next_90": occ_next_90,
        "upcoming_global": upcoming_global,
        # Drafts
        "total_drafts": total_drafts,
        "drafts_7d": drafts_7d,
        "draft_queued": draft_queued,
        "draft_generating": draft_generating,
        "draft_ready": draft_ready,
        "draft_approved": draft_approved,
        "draft_dismissed": draft_dismissed,
        "draft_failed": draft_failed,
        "draft_expired": draft_expired,
        "drafts_daily": drafts_daily,
        "recent_drafts": recent_drafts,
        "failed_drafts": failed_drafts,
        # User opt-ins
        "total_prefs": total_prefs,
        "enabled_prefs": enabled_prefs,
        "muted_prefs": muted_prefs,
        "top_optin_holidays": top_optin_holidays,
        # Custom events
        "total_custom_events": total_custom_events,
        "active_custom_events": active_custom_events,
        "upcoming_custom": upcoming_custom,
        # Engagement
        "top_users": top_users,
        # Watcher health
        "last_draft_created": last_draft_created,
    })


@staff_required
def draft_list_admin(request):
    """Paginated list of all HolidayDrafts with status + score filters."""
    status = request.GET.get("status", "")

    qs = (
        HolidayDraft.objects
        .select_related("user", "holiday_occurrence__holiday", "custom_event")
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "admin_dashboard/calendar_intel/draft_list.html", {
        "page_title": "All Holiday Drafts",
        "page_obj": page_obj,
        "current_status": status,
        "statuses": HolidayDraft.Status.choices,
    })


@staff_required
@require_POST
def draft_retry(request, pk):
    """Re-queue a FAILED HolidayDraft for generation."""
    from apps.calendar_intel.tasks import generate_drafts_for_moment

    draft = get_object_or_404(HolidayDraft, pk=pk)
    if draft.status not in (HolidayDraft.Status.FAILED, HolidayDraft.Status.EXPIRED):
        messages.warning(request, "Only failed or expired drafts can be retried.")
        return redirect("admin_dashboard:calendar_drafts")

    draft.status = HolidayDraft.Status.QUEUED
    draft.generation_error = ""
    draft.save(update_fields=["status", "generation_error", "updated_at"])
    generate_drafts_for_moment.delay(draft.id)
    messages.success(request, f"Re-queued draft {draft.id}. Generation will run in the background.")
    return redirect("admin_dashboard:calendar_drafts")
