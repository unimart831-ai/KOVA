"""Agent HTTP endpoints.

Dashboard agent templates were removed for V1. Control / strategist / detail /
activity pages redirect so users never hit TemplateDoesNotExist. Staff can
inspect agents via admin_dashboard. Toggle / status return empty OK for HTMX.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.create.agents.models import AgentConfig


def _v1_agents_redirect(request, notice=None):
    """Send everyone to Home; optional flash for explicit /agents/ visits."""
    if notice:
        messages.info(request, notice)
    return redirect("brief:home")


@login_required
def agent_control(request):
    """V1: no agent control panel — agents run via Settings / Home."""
    return _v1_agents_redirect(
        request,
        "Kova runs agents in the background. Adjust approval and WhatsApp reply settings in Settings.",
    )


@login_required
def agent_toggle(request, slug):
    """Toggle agent on/off (HTMX)."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    agent.is_active = not agent.is_active
    agent.save(update_fields=["is_active"])
    return HttpResponse(status=204)


@login_required
def agent_status(request, slug):
    """HTMX status poll — dashboard partial removed in V1; return empty OK."""
    get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    return HttpResponse(status=204)


@login_required
def agent_activity_log(request):
    """V1: activity log template removed — redirect to Home."""
    return _v1_agents_redirect(request)


@login_required
def agent_detail(request, slug):
    """V1: agent detail template removed — redirect to Home."""
    return _v1_agents_redirect(request)


@login_required
@require_POST
def agent_update_instructions(request, slug):
    """Update custom instructions for an agent, then return to Home."""
    agent = get_object_or_404(AgentConfig, user=request.user, agent_type=slug)
    agent.custom_instructions = request.POST.get("custom_instructions", "").strip()
    agent.save(update_fields=["custom_instructions", "updated_at"])
    return redirect("brief:home")


@login_required
def strategist_dashboard(request):
    """V1: strategist dashboard template removed — redirect to Home."""
    return _v1_agents_redirect(request)
