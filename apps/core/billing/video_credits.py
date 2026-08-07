"""Photoroom Video animate credits — separate from studio polish pool (Pro+)."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

VIDEO_ANIMATE_ACTION = "commerce.video_animate"


def _video_actions():
    from apps.create.agents.models import AgentAction

    return AgentAction.objects.filter(action_type=VIDEO_ANIMATE_ACTION)


def get_video_animate_limits(user) -> dict:
    from apps.core.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    max_calls = int(limits.get("video_animate_per_month", 0) or 0)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = _video_actions().filter(user=user, created_at__gte=month_start).count()
    return {
        "used": used,
        "max": max_calls,
        "remaining": max(0, max_calls - used) if max_calls > 0 else 0,
        "at_limit": max_calls > 0 and used >= max_calls,
        "enabled": max_calls > 0,
    }


def check_video_animate_limit(user) -> tuple[bool, str]:
    if not getattr(settings, "PHOTOROOM_VIDEO_CREDITS_ENABLED", True):
        return True, ""
    limits = get_video_animate_limits(user)
    if not limits["enabled"]:
        return False, "Video animate is available on Pro and Agency plans."
    if limits["at_limit"]:
        return False, (
            f"You've used all {limits['max']} video animate credits this month. "
            "Reels still work with motion slideshow from your photos."
        )
    return True, ""


def record_video_animate(user, *, product_id: str, provider: str = "photoroom_video") -> None:
    from apps.create.agents.models import AgentAction

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type=VIDEO_ANIMATE_ACTION,
        description=f"Video animate ({provider})",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": str(product_id), "provider": provider},
        output_data={},
        completed_at=timezone.now(),
    )
