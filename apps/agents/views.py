from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.agents.models import AgentAction, AgentConfig


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
    """Agent control center — toggle and configure agents."""
    agents = request.user.agent_configs.all()

    # Auto-create default agent configs if none exist
    if not agents.exists():
        for agent_type, _ in AgentConfig.AgentType.choices:
            AgentConfig.objects.create(user=request.user, agent_type=agent_type)
        agents = request.user.agent_configs.all()

    by_type = {a.agent_type: a for a in agents}
    agents_ordered = [by_type[k] for k in _PIPELINE_ORDER if k in by_type]

    return render(request, "agents/control.html", {
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

    actions = actions[:100]

    return render(request, "agents/activity_log.html", {
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

    return render(request, "agents/detail.html", {
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
