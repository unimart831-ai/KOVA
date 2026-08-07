"""HTMX partial views for auto-refreshing dashboard components."""

from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.core.admin_dashboard.decorators import staff_required


@staff_required
def partial_stat_cards(request):
    """Return refreshed stat cards (polled every 30s)."""
    from apps.core.accounts.models import User, UserProfile
    from apps.create.agents.models import AgentAction
    from apps.core.billing.models import MpesaPayment
    from apps.create.content.models import Post

    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)

    total_users = User.objects.count()
    active_users_7d = User.objects.filter(
        Q(posts__created_at__gte=seven_days_ago) |
        Q(content_seeds__created_at__gte=seven_days_ago)
    ).distinct().count()

    posts_today = Post.objects.filter(
        status="published", published_at__date=today,
    ).count()
    posts_yesterday = Post.objects.filter(
        status="published", published_at__date=yesterday,
    ).count()

    agent_24h = AgentAction.objects.filter(
        created_at__gte=now - timedelta(hours=24),
    )
    agent_total_24h = agent_24h.count()
    agent_completed_24h = agent_24h.filter(status="completed").count()
    agent_success_rate = (
        round((agent_completed_24h / agent_total_24h) * 100, 1)
        if agent_total_24h > 0 else 100.0
    )

    plan_prices_kes = {"starter": 99, "growth": 500, "pro": 1500, "agency": 3500}
    mrr_kes = 0
    for pc in UserProfile.objects.filter(
        subscription_status__in=["active", "trialing"],
    ).values("plan").annotate(count=Count("id")):
        mrr_kes += plan_prices_kes.get(pc["plan"], 0) * pc["count"]

    paying_users = UserProfile.objects.filter(
        subscription_status__in=["active", "trialing"],
    ).count()

    return render(request, "admin_dashboard/partials/stat_cards.html", {
        "total_users": total_users,
        "active_users_7d": active_users_7d,
        "paying_users": paying_users,
        "posts_today": posts_today,
        "posts_yesterday": posts_yesterday,
        "agent_success_rate": agent_success_rate,
        "agent_total_24h": agent_total_24h,
        "mrr_kes": mrr_kes,
    })


@staff_required
def partial_activity_feed(request):
    """Return refreshed activity feed (polled every 30s)."""
    from apps.create.agents.models import AgentAction

    recent_actions = (
        AgentAction.objects.select_related("user")
        .order_by("-created_at")[:20]
    )
    return render(request, "admin_dashboard/partials/activity_feed.html", {
        "recent_actions": recent_actions,
    })


@staff_required
def partial_agent_health(request):
    """Return refreshed agent health grid."""
    from apps.create.agents.models import AgentAction

    now = timezone.now()
    agent_types = ["create", "analyst", "research", "adapt", "engage", "strategist"]
    agent_stats = {
        row["agent_type"]: row
        for row in AgentAction.objects.filter(
            created_at__gte=now - timedelta(hours=24),
        ).values("agent_type").annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            tokens=Sum("tokens_used"),
            avg_dur=Avg("duration_ms", filter=Q(duration_ms__gt=0)),
        )
    }
    agent_health = []
    for at in agent_types:
        row = agent_stats.get(at, {})
        total = row.get("total", 0)
        completed = row.get("completed", 0)
        rate = round((completed / total) * 100, 1) if total > 0 else 100.0
        agent_health.append({
            "type": at,
            "name": at.title(),
            "success_rate": rate,
            "runs_24h": total,
            "avg_duration_ms": int(row.get("avg_dur", 0) or 0),
            "tokens_24h": row.get("tokens", 0) or 0,
            "status": "green" if rate >= 95 else ("yellow" if rate >= 80 else "red"),
        })

    return render(request, "admin_dashboard/partials/agent_health.html", {
        "agent_health": agent_health,
    })
