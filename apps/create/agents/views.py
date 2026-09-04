from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.create.agents.models import AgentAction, AgentConfig
from apps.insight.analytics.models import GrowthSnapshot


_PIPELINE_ORDER = (
    "research",
    "create",
    "adapt",
    "engage",
    "analyst",
    "strategist",
)


@login_required
def agent_control(request):
    """Agent control center — staff-only; SMB users manage autonomy in Settings."""
    if not request.user.is_staff:
        messages.info(
            request,
            "Kova runs automatically. Adjust approval and reply settings in Settings.",
        )
        return redirect("accounts:settings")

    agents = request.user.agent_configs.all()

    # Auto-create default agent configs if none exist
    if not agents.exists():
        for agent_type, _ in AgentConfig.AgentType.choices:
            AgentConfig.objects.create(user=request.user, agent_type=agent_type)
        agents = request.user.agent_configs.all()

    by_type = {a.agent_type: a for a in agents}
    agents_ordered = [by_type[k] for k in _PIPELINE_ORDER if k in by_type]

    return render(request, "dashboard/agents/control.html", {
        "agents": agents_ordered,
        "page_title": "Agent Control Center",
    })


@login_required
def agent_toggle(request, slug):
    """Toggle agent on/off (HTMX)."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    agent.is_active = not agent.is_active
    agent.save(update_fields=["is_active"])
    return HttpResponse(status=204)


@login_required
def agent_status(request, slug):
    """Return agent status card (HTMX polling)."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    # Add runtime data for the template
    today = timezone.now().date()
    agent.actions_today = agent.user.agent_actions.filter(
        agent_type=slug, created_at__date=today
    ).count()
    agent.current_task = None
    agent.last_active_at = agent.user.agent_actions.filter(agent_type=slug).values_list("created_at", flat=True).first()
    return render(request, "components/agent_status.html", {"agent": agent})


@login_required
def agent_activity_log(request):
    """Full activity log across all agents."""
    agent_filter = request.GET.get("agent", "")
    status_filter = request.GET.get("status", "")

    actions = AgentAction.objects.filter(user=request.user).order_by("-created_at")

    if agent_filter:
        actions = actions.filter(agent_type=agent_filter)
    if status_filter:
        actions = actions.filter(status=status_filter)

    actions = list(actions[:100])

    return render(request, "dashboard/agents/activity_log.html", {
        "actions": actions,
        "agent_filter": agent_filter,
        "status_filter": status_filter,
        "agent_types": AgentConfig.AgentType.choices,
        "page_title": "Agent Activity Log",
    })


@login_required
def agent_detail(request, slug):
    """Detail view for a single agent — config + recent activity."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    today = timezone.now().date()

    recent_actions = AgentAction.objects.filter(
        user=request.user,
        agent_type=slug,
    ).order_by("-created_at")[:20]

    stats = {
        "total_actions": AgentAction.objects.filter(user=request.user, agent_type=slug).count(),
        "actions_today": AgentAction.objects.filter(
            user=request.user, agent_type=slug, created_at__date=today
        ).count(),
        "total_tokens": AgentAction.objects.filter(
            user=request.user, agent_type=slug, tokens_used__gt=0
        ).aggregate(total=Sum("tokens_used"))["total"] or 0,
    }

    return render(request, "dashboard/agents/detail.html", {
        "agent": agent,
        "recent_actions": recent_actions,
        "stats": stats,
        "page_title": agent.name,
    })


@login_required
@require_POST
def agent_update_instructions(request, slug):
    """Update custom instructions for an agent."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    agent.custom_instructions = request.POST.get("custom_instructions", "").strip()
    agent.save(update_fields=["custom_instructions", "updated_at"])
    return redirect("agents:detail", slug=slug)


@login_required
def strategist_dashboard(request):
    """
    Growth Advisor Dashboard — the Strategist Agent's command center.
    Shows follower growth, content-to-growth correlation, revenue signals,
    and recent strategy cycle outputs.
    """
    from datetime import timedelta as td

    user = request.user

    # Growth summary (30 days)
    growth_summary = GrowthSnapshot.get_growth_summary(user, days=30)

    # Recent snapshots for sparkline data (14 days per platform)
    from collections import defaultdict
    cutoff_14d = timezone.now().date() - td(days=14)
    recent_snapshots = GrowthSnapshot.objects.filter(
        user=user, snapshot_date__gte=cutoff_14d,
    ).select_related("social_account").order_by("snapshot_date")

    sparklines = defaultdict(list)
    for snap in recent_snapshots:
        sparklines[snap.social_account.platform].append({
            "date": snap.snapshot_date.isoformat(),
            "followers": snap.followers,
            "delta": snap.followers_delta,
        })

    # Total followers across all platforms (latest snapshot per account)
    from django.db.models import Max
    latest_per_account = GrowthSnapshot.objects.filter(user=user).values(
        "social_account"
    ).annotate(latest=Max("snapshot_date"))

    total_followers = 0
    total_delta_7d = 0
    for entry in latest_per_account:
        snap = GrowthSnapshot.objects.filter(
            social_account_id=entry["social_account"],
            snapshot_date=entry["latest"],
        ).first()
        if snap:
            total_followers += snap.followers

    # 7-day total growth
    week_ago = timezone.now().date() - td(days=7)
    week_snapshots = GrowthSnapshot.objects.filter(
        user=user, snapshot_date__gte=week_ago,
    )
    total_delta_7d = sum(s.followers_delta for s in week_snapshots)

    # Latest strategy cycle output
    latest_strategy = AgentAction.objects.filter(
        user=user,
        agent_type="strategist",
        action_type="strategy_cycle",
        status=AgentAction.ActionStatus.COMPLETED,
    ).order_by("-created_at").first()

    strategy_data = latest_strategy.output_data if latest_strategy else {}
    growth_assessment = strategy_data.get("growth_assessment", {})

    # Content-to-growth correlation (reuse strategist logic)
    from apps.create.agents.strategist_agent import _get_content_growth_correlation, _get_revenue_signals
    content_growth = _get_content_growth_correlation(user, days=30)
    revenue_signals = _get_revenue_signals(user, days=30)

    # Recent strategy cycles (last 5)
    recent_cycles = AgentAction.objects.filter(
        user=user,
        agent_type="strategist",
        action_type="strategy_cycle",
        status=AgentAction.ActionStatus.COMPLETED,
    ).order_by("-created_at")[:5]

    return render(request, "dashboard/agents/strategist_dashboard.html", {
        "page_title": "Growth Advisor",
        "growth_summary": growth_summary,
        "sparklines": dict(sparklines),
        "total_followers": total_followers,
        "total_delta_7d": total_delta_7d,
        "growth_assessment": growth_assessment,
        "content_growth": content_growth,
        "revenue_signals": revenue_signals,
        "recent_cycles": recent_cycles,
        "latest_strategy": latest_strategy,
        "strategy_data": strategy_data,
    })
