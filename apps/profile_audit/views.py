"""Profile health views — audit list and per-account detail."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.platforms.models import SocialAccount

AUDIT_PLATFORMS = frozenset({"facebook", "instagram", "linkedin"})


def _auditable_accounts(user):
    return (
        user.social_accounts.filter(platform__in=AUDIT_PLATFORMS, is_active=True)
        .defer("access_token", "refresh_token", "token_scope")
        .order_by("platform", "username")
    )


@login_required
def audit_list(request):
    """Connected social accounts eligible for profile completeness audits."""
    accounts = list(_auditable_accounts(request.user))
    return render(request, "profile_audit/list.html", {
        "page_title": "Profile Health",
        "accounts": accounts,
    })


@login_required
def audit_detail(request, account_id):
    """Per-account profile health — full auditor UI ships when audit models are enabled."""
    account = get_object_or_404(
        SocialAccount.objects.defer("access_token", "refresh_token", "token_scope"),
        pk=account_id,
        user=request.user,
    )
    return render(request, "profile_audit/detail.html", {
        "page_title": f"Profile health · @{account.username or account.platform}",
        "account": account,
        "audit_platforms": AUDIT_PLATFORMS,
    })
