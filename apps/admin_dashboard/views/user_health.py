"""
Admin dashboard — User Health & Churn Risk view.

Surfaces at-risk users during critical trial/early subscription period.
Displays churn risk score, last activity, and key engagement signals.
"""

from datetime import timedelta

from django.db.models import Count, Max, Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.admin_dashboard.decorators import staff_required


def _compute_churn_risk(user, now):
    """
    Compute a 0-100 churn risk score for a user.

    Higher = more likely to churn. Factors:
    - Days since last login (0-40 pts)
    - No published posts (0-25 pts)
    - No connected platforms (0-20 pts)
    - Trial ending soon with no conversion signal (0-15 pts)
    """
    profile = user.profile
    risk = 0
    signals = []

    # Factor 1: Inactivity (days since last login)
    if user.last_login:
        days_inactive = (now - user.last_login).days
        if days_inactive >= 7:
            risk += min(40, days_inactive * 4)
            signals.append(f"Inactive {days_inactive}d")
        elif days_inactive >= 3:
            risk += days_inactive * 3
            signals.append(f"Inactive {days_inactive}d")
    else:
        risk += 40
        signals.append("Never logged in")

    # Factor 2: No published posts
    published = getattr(user, "_published_count", 0)
    if published == 0:
        risk += 25
        signals.append("No published posts")

    # Factor 3: No connected platforms
    platforms = getattr(user, "_platform_count", 0)
    if platforms == 0:
        risk += 20
        signals.append("No platforms connected")

    # Factor 4: Trial ending soon, no upgrade signals
    if profile.subscription_status == "trialing" and profile.trial_ends_at:
        days_left = (profile.trial_ends_at - now).days
        if days_left <= 3:
            risk += 15
            signals.append(f"Trial ends in {days_left}d")
        elif days_left <= 7:
            risk += 8
            signals.append(f"Trial ends in {days_left}d")

    return min(100, risk), signals


@staff_required
def user_health(request):
    """
    User health dashboard — shows all trialing/active users ranked by churn risk.

    Enables founder to intervene with at-risk users during the critical
    first 50 customer acquisition phase.
    """
    now = timezone.now()

    # Focus on users who matter: trialing or recently active
    status_filter = request.GET.get("status", "trialing")
    qs = User.objects.select_related("profile").filter(
        onboarding_completed=True,
    )

    if status_filter == "trialing":
        qs = qs.filter(profile__subscription_status="trialing")
    elif status_filter == "active":
        qs = qs.filter(profile__subscription_status="active")
    elif status_filter == "at_risk":
        # Will filter after computing risk scores
        pass
    else:
        qs = qs.filter(profile__subscription_status__in=("trialing", "active", "past_due"))

    # Annotate with activity signals
    from apps.content.models import Post
    from apps.platforms.models import SocialAccount

    qs = qs.annotate(
        _published_count=Count(
            "posts", filter=Q(posts__status="published"),
        ),
        _platform_count=Count(
            "social_accounts", filter=Q(social_accounts__is_active=True),
        ),
    )

    # Compute risk scores
    users_with_risk = []
    for user in qs:
        risk_score, risk_signals = _compute_churn_risk(user, now)
        users_with_risk.append({
            "user": user,
            "risk_score": risk_score,
            "risk_signals": risk_signals,
            "risk_level": "critical" if risk_score >= 70 else "warning" if risk_score >= 40 else "healthy",
            "published_count": user._published_count,
            "platform_count": user._platform_count,
            "days_since_signup": (now - user.date_joined).days,
            "days_since_login": (now - user.last_login).days if user.last_login else None,
            "trial_days_left": (
                (user.profile.trial_ends_at - now).days
                if user.profile.subscription_status == "trialing" and user.profile.trial_ends_at
                else None
            ),
        })

    # Filter for at_risk if requested
    if status_filter == "at_risk":
        users_with_risk = [u for u in users_with_risk if u["risk_score"] >= 40]

    # Sort by risk score descending (most at-risk first)
    users_with_risk.sort(key=lambda u: u["risk_score"], reverse=True)

    # Summary stats
    total = len(users_with_risk)
    critical_count = sum(1 for u in users_with_risk if u["risk_level"] == "critical")
    warning_count = sum(1 for u in users_with_risk if u["risk_level"] == "warning")
    healthy_count = sum(1 for u in users_with_risk if u["risk_level"] == "healthy")

    return render(request, "admin_dashboard/users/health.html", {
        "users_with_risk": users_with_risk,
        "status_filter": status_filter,
        "total": total,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "healthy_count": healthy_count,
        "page_title": "User Health",
    })
