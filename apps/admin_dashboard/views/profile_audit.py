"""Admin dashboard view for profile audits across all users."""
from datetime import timedelta

from django.db.models import Avg, Count, Max, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required
from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion


@staff_required
def profile_audit_overview(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Audit volume ────────────────────────────────────────────────
    total_audits = ProfileAudit.objects.count()
    audits_7d = ProfileAudit.objects.filter(audited_at__gte=week_ago).count()
    audits_with_errors = ProfileAudit.objects.filter(audited_at__gte=week_ago).exclude(error="").count()

    # ── Latest-audit-per-account aggregates ────────────────────────
    latest_ids = list(
        ProfileAudit.objects
        .values("social_account_id")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )
    latest_audits = ProfileAudit.objects.filter(id__in=latest_ids, error="")
    accounts_audited = latest_audits.count()

    score_buckets = {
        "good": latest_audits.filter(completeness_score__gte=85).count(),
        "ok": latest_audits.filter(completeness_score__gte=60, completeness_score__lt=85).count(),
        "low": latest_audits.filter(completeness_score__gte=30, completeness_score__lt=60).count(),
        "critical": latest_audits.filter(completeness_score__lt=30).count(),
    }
    avg_score = latest_audits.aggregate(avg=Avg("completeness_score"))["avg"] or 0

    # Per-platform averages
    per_platform = list(
        latest_audits
        .values("social_account__platform")
        .annotate(
            count=Count("id"),
            avg_score=Avg("completeness_score"),
        )
        .order_by("-count")
    )

    # ── Suggestion stats ────────────────────────────────────────────
    sugg_status = dict(
        ProfileUpdateSuggestion.objects
        .values_list("status").annotate(c=Count("id"))
        .values_list("status", "c")
    )
    suggestions_applied_7d = ProfileUpdateSuggestion.objects.filter(
        status=ProfileUpdateSuggestion.Status.APPLIED,
        applied_at__gte=week_ago,
    ).count()
    suggestions_failed_7d = ProfileUpdateSuggestion.objects.filter(
        status=ProfileUpdateSuggestion.Status.FAILED,
        updated_at__gte=week_ago,
    ).count()

    # ── Top problematic fields ──────────────────────────────────────
    pending = ProfileUpdateSuggestion.objects.filter(
        status=ProfileUpdateSuggestion.Status.PENDING,
    )
    top_pending_fields = list(
        pending.values("field_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # ── Top users with lowest scores ────────────────────────────────
    top_low_scoring = list(
        latest_audits
        .select_related("user", "social_account")
        .order_by("completeness_score")[:15]
    )

    # ── Recent failures ─────────────────────────────────────────────
    recent_failures = list(
        ProfileUpdateSuggestion.objects.filter(status=ProfileUpdateSuggestion.Status.FAILED)
        .select_related("user", "social_account")
        .order_by("-updated_at")[:10]
    )

    # ── Audit volume per day (7d) ───────────────────────────────────
    daily = list(
        ProfileAudit.objects.filter(audited_at__gte=week_ago)
        .annotate(date=TruncDate("audited_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    last_audit_at = ProfileAudit.objects.order_by("-audited_at").values_list("audited_at", flat=True).first()

    return render(request, "admin_dashboard/profile_audit/overview.html", {
        "page_title": "Profile Audits",
        "total_audits": total_audits,
        "audits_7d": audits_7d,
        "audits_with_errors": audits_with_errors,
        "accounts_audited": accounts_audited,
        "avg_score": int(round(avg_score)),
        "score_buckets": score_buckets,
        "per_platform": per_platform,
        "sugg_pending": sugg_status.get(ProfileUpdateSuggestion.Status.PENDING, 0),
        "sugg_approved": sugg_status.get(ProfileUpdateSuggestion.Status.APPROVED, 0),
        "sugg_applied": sugg_status.get(ProfileUpdateSuggestion.Status.APPLIED, 0),
        "sugg_dismissed": sugg_status.get(ProfileUpdateSuggestion.Status.DISMISSED, 0),
        "sugg_failed": sugg_status.get(ProfileUpdateSuggestion.Status.FAILED, 0),
        "suggestions_applied_7d": suggestions_applied_7d,
        "suggestions_failed_7d": suggestions_failed_7d,
        "top_pending_fields": top_pending_fields,
        "top_low_scoring": top_low_scoring,
        "recent_failures": recent_failures,
        "daily": daily,
        "last_audit_at": last_audit_at,
    })
