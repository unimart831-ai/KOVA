from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

from apps.agents.models import AgentConfig


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
    agent.actions_today = agent.user.agent_actions.filter(
        agent_type=slug, created_at__date=__import__("django.utils.timezone", fromlist=["now"]).now().date()
    ).count()
    agent.current_task = None
    agent.last_active_at = agent.user.agent_actions.filter(agent_type=slug).values_list("created_at", flat=True).first()
    return render(request, "components/agent_status.html", {"agent": agent})
