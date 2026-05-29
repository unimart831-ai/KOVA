"""Admin — content seed quota overrides for testing and promotions."""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.billing.enforcement import get_seed_usage
from apps.billing.models import ContentSeedQuotaLog
from apps.billing.seed_quota import (
    clear_seed_quota_overrides,
    reset_seed_usage,
    set_seed_bonus,
    set_seed_limit_override,
)


@staff_required
def seed_quota_hub(request):
    """Lookup user by email and manage monthly seed quota."""
    user = None
    seed_usage = None
    recent_logs = []
    email = request.GET.get("email", "").strip()

    if email:
        user = (
            User.objects.select_related("profile")
            .filter(Q(email__iexact=email) | Q(full_name__icontains=email))
            .first()
        )
        if user:
            seed_usage = get_seed_usage(user)
            recent_logs = ContentSeedQuotaLog.objects.filter(user=user).select_related(
                "admin",
            )[:15]

    context = {
        "page_title": "Content seed quotas",
        "commerce_section": "content",
        "email": email,
        "target_user": user,
        "seed_usage": seed_usage,
        "recent_logs": recent_logs,
    }
    return render(request, "admin_dashboard/content/seed_quota.html", context)


@staff_required
def seed_quota_log(request):
    """Audit log of all seed quota admin actions."""
    qs = ContentSeedQuotaLog.objects.select_related("user", "admin").order_by("-created_at")

    email = request.GET.get("email", "").strip()
    if email:
        qs = qs.filter(Q(user__email__icontains=email) | Q(user__full_name__icontains=email))

    paginator = Paginator(qs, 40)
    page = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "admin_dashboard/content/seed_quota_log.html",
        {
            "page_title": "Seed quota log",
            "commerce_section": "content",
            "page_obj": page,
            "email": email,
            "total_count": paginator.count,
        },
    )


@senior_staff_required
@require_POST
def seed_quota_action(request, pk):
    """POST handler: reset / override / bonus / clear."""
    user = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    action = (request.POST.get("action") or "").strip()
    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Please enter a reason for this change.")
        return _redirect_back(request, user)

    try:
        if action == "reset_usage":
            after = reset_seed_usage(user, request.user, reason)
            messages.success(
                request,
                f"Reset seed counter for {user.email}. "
                f"Now {after['used']}/{after['max']} used ({after['remaining']} left).",
            )
        elif action == "set_limit":
            raw = (request.POST.get("limit_override") or "").strip()
            if not raw:
                messages.error(request, "Enter a monthly limit number, or use Clear all.")
                return _redirect_back(request, user)
            limit = int(raw)
            if limit < 1:
                raise ValueError("Limit must be at least 1")
            after = set_seed_limit_override(user, request.user, limit, reason)
            messages.success(
                request,
                f"Limit override set to {limit}. "
                f"Effective quota: {after['used']}/{after['max']} ({after['remaining']} left).",
            )
        elif action == "clear_limit":
            after = set_seed_limit_override(user, request.user, None, reason)
            messages.success(request, f"Cleared limit override. {after['remaining']} seeds left.")
        elif action == "set_bonus":
            raw = (request.POST.get("bonus") or "").strip()
            bonus = int(raw) if raw else 0
            after = set_seed_bonus(user, request.user, bonus, reason)
            messages.success(
                request,
                f"Bonus seeds set to +{bonus}. "
                f"Effective max {after['max']} ({after['remaining']} remaining).",
            )
        elif action == "clear_all":
            after = clear_seed_quota_overrides(user, request.user, reason)
            messages.success(
                request,
                f"All seed overrides cleared. Back to plan default: "
                f"{after['used']}/{after['max']} ({after['remaining']} left).",
            )
        else:
            messages.error(request, "Unknown action.")
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Could not apply change: {exc}")

    return _redirect_back(request, user)


def _redirect_back(request, user):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt:
        return redirect(nxt)
    return redirect(
        reverse("admin_dashboard:seed_quota_hub") + f"?email={user.email}",
    )
