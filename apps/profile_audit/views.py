"""
User-facing Profile Health views.

Three surfaces:
  - list  (/profile-health/)          : overview across all connected accounts
  - detail (/profile-health/<account_id>/) : per-account suggestions to approve
  - approve/dismiss endpoints (HTMX)  : drive the suggestion state machine
  - re-audit endpoint                  : on-demand re-run audit for one account
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.platforms.models import SocialAccount
from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion


SUPPORTED_PLATFORMS = ("facebook", "instagram", "linkedin")


@login_required
def health_list(request):
    """Per-account health card list — score + a count of pending suggestions."""
    accounts = list(
        request.user.social_accounts
        .filter(is_active=True, platform__in=SUPPORTED_PLATFORMS)
        .order_by("platform", "username")
    )

    # Latest audit per account
    latest_audit_by_account = {}
    pending_by_account = {}
    for acc in accounts:
        latest = (
            ProfileAudit.objects
            .filter(social_account=acc)
            .order_by("-audited_at")
            .first()
        )
        latest_audit_by_account[acc.id] = latest
        if latest:
            pending_by_account[acc.id] = latest.suggestions.filter(
                status=ProfileUpdateSuggestion.Status.PENDING,
            ).count()
        else:
            pending_by_account[acc.id] = 0

    cards = [
        {
            "account": acc,
            "audit": latest_audit_by_account.get(acc.id),
            "pending_count": pending_by_account.get(acc.id, 0),
        }
        for acc in accounts
    ]

    # Unsupported accounts — show them so users understand why they're not audited
    unsupported = list(
        request.user.social_accounts
        .filter(is_active=True)
        .exclude(platform__in=SUPPORTED_PLATFORMS)
        .order_by("platform")
    )

    return render(request, "profile_audit/list.html", {
        "page_title": "Profile Health",
        "cards": cards,
        "unsupported": unsupported,
    })


@login_required
def health_detail(request, account_id):
    """Per-account detail with the suggestions panel."""
    account = get_object_or_404(
        SocialAccount, id=account_id, user=request.user, is_active=True,
    )
    audit = (
        ProfileAudit.objects
        .filter(social_account=account)
        .order_by("-audited_at")
        .first()
    )

    pending = applied = dismissed = failed = []
    if audit:
        all_suggestions = list(
            audit.suggestions.all().order_by("status", "field_name")
        )
        by_status = {}
        for s in all_suggestions:
            by_status.setdefault(s.status, []).append(s)
        pending = by_status.get(ProfileUpdateSuggestion.Status.PENDING, [])
        applied = by_status.get(ProfileUpdateSuggestion.Status.APPLIED, [])
        dismissed = by_status.get(ProfileUpdateSuggestion.Status.DISMISSED, [])
        failed = by_status.get(ProfileUpdateSuggestion.Status.FAILED, [])

    audit_history = (
        ProfileAudit.objects
        .filter(social_account=account)
        .order_by("-audited_at")[:10]
    )

    return render(request, "profile_audit/detail.html", {
        "page_title": f"{account.platform.title()} — Profile Health",
        "account": account,
        "audit": audit,
        "pending": pending,
        "applied": applied,
        "dismissed": dismissed,
        "failed": failed,
        "audit_history": audit_history,
    })


@login_required
@require_POST
def suggestion_approve(request, suggestion_id):
    """User approves → enqueue apply task. Returns updated row for HTMX swap."""
    from apps.profile_audit.tasks import apply_one_suggestion

    suggestion = get_object_or_404(
        ProfileUpdateSuggestion,
        id=suggestion_id,
        user=request.user,
    )
    if suggestion.status not in (
        ProfileUpdateSuggestion.Status.PENDING,
        ProfileUpdateSuggestion.Status.FAILED,
    ):
        return _render_suggestion_row(request, suggestion)

    suggestion.status = ProfileUpdateSuggestion.Status.APPROVED
    suggestion.error_message = ""
    suggestion.save(update_fields=["status", "error_message", "updated_at"])
    try:
        apply_one_suggestion.delay(suggestion.id)
    except Exception:
        # Sync fallback so the user sees something happen even without Celery up
        from apps.profile_audit.auditor import apply_suggestion
        apply_suggestion(suggestion)
    suggestion.refresh_from_db()
    return _render_suggestion_row(request, suggestion)


@login_required
@require_POST
def suggestion_dismiss(request, suggestion_id):
    suggestion = get_object_or_404(
        ProfileUpdateSuggestion,
        id=suggestion_id,
        user=request.user,
    )
    if suggestion.status == ProfileUpdateSuggestion.Status.PENDING:
        suggestion.status = ProfileUpdateSuggestion.Status.DISMISSED
        suggestion.save(update_fields=["status", "updated_at"])
    return _render_suggestion_row(request, suggestion)


def _render_suggestion_row(request, suggestion):
    return render(request, "profile_audit/partials/_suggestion_row.html", {
        "s": suggestion,
    })


@login_required
@require_POST
def reaudit_account(request, account_id):
    """User-triggered immediate re-audit. Queues the task synchronously
    via Celery so the user can refresh the page in a few seconds."""
    from apps.profile_audit.tasks import audit_one_account

    account = get_object_or_404(
        SocialAccount, id=account_id, user=request.user, is_active=True,
    )
    try:
        audit_one_account.delay(str(account.id))
    except Exception:
        # Sync fallback
        from apps.profile_audit.auditor import audit_social_account
        audit_social_account(account, generate_suggestions=True)
    return redirect("profile_audit:detail", account_id=account.id)
