"""Visual credit metering — Photoroom Plus studio polish (platform + per-user)."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from apps.billing.models import get_user_plan_limits

# Current action type (legacy alias: commerce.pro_scene)
STUDIO_POLISH_ACTION = "commerce.studio_polish"
LEGACY_PRO_SCENE_ACTION = "commerce.pro_scene"


def _studio_polish_actions_filter():
    from django.db.models import Q
    from apps.agents.models import AgentAction

    return AgentAction.objects.filter(
        Q(action_type=STUDIO_POLISH_ACTION) | Q(action_type=LEGACY_PRO_SCENE_ACTION)
    )


def get_platform_photoroom_usage() -> dict:
    """Platform-wide Photoroom pool consumption this month."""
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pool = int(getattr(settings, "PHOTOROOM_MONTHLY_POOL", 5000))
    reserve = int(getattr(settings, "PHOTOROOM_POOL_RESERVE", 500))
    usable = max(0, pool - reserve)

    used = _studio_polish_actions_filter().filter(created_at__gte=month_start).count()

    return {
        "used": used,
        "pool": pool,
        "reserve": reserve,
        "usable": usable,
        "remaining": max(0, usable - used),
        "at_limit": used >= usable,
        "cost_usd_monthly": float(getattr(settings, "PHOTOROOM_MONTHLY_COST_USD", 500)),
        "cost_per_image": round(
            float(getattr(settings, "PHOTOROOM_MONTHLY_COST_USD", 500)) / max(pool, 1),
            4,
        ),
    }


def get_visual_credit_usage(user) -> dict:
    """Monthly studio polish quota for UI and enforcement."""
    limits = get_user_plan_limits(user)
    max_credits = limits.get("visual_enhancements_per_month", 0)
    unlimited = max_credits >= 999999
    platform = get_platform_photoroom_usage()

    if unlimited:
        return {
            "used": 0,
            "max": max_credits,
            "remaining": max_credits,
            "at_limit": False,
            "unlimited": True,
            "plan_label": limits.get("label", "Starter"),
            "platform": platform,
            "platform_blocked": platform["at_limit"],
        }

    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = _studio_polish_actions_filter().filter(
        user=user,
        created_at__gte=month_start,
    ).count()

    user_at_limit = used >= max_credits
    platform_blocked = platform["at_limit"]

    return {
        "used": used,
        "max": max_credits,
        "remaining": max(0, max_credits - used),
        "at_limit": user_at_limit or platform_blocked,
        "user_at_limit": user_at_limit,
        "platform_blocked": platform_blocked,
        "unlimited": False,
        "plan_label": limits.get("label", "Starter"),
        "platform": platform,
    }


def check_visual_credit_limit(user) -> tuple[bool, str]:
    usage = get_visual_credit_usage(user)
    if usage["unlimited"]:
        if usage.get("platform_blocked"):
            return False, (
                "Studio polish is temporarily unavailable — platform monthly capacity reached. "
                "Use as-is or try again next month."
            )
        return True, ""

    if usage.get("platform_blocked"):
        return False, (
            "Studio polish is temporarily unavailable — platform monthly capacity reached. "
            "Use as-is or try again next month."
        )

    if not usage["user_at_limit"]:
        return True, ""

    return False, (
        f"You've used all {usage['max']} studio polish credits this month "
        f"on your {usage['plan_label']} plan. Use as-is or upgrade for more."
    )


def begin_studio_polish_session(user, *, product_id: str, source: str = "snap") -> "AgentAction":
    """Mark expand in progress so Snap status does not show a false 'running' stall."""
    from apps.agents.models import AgentAction

    return AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type=STUDIO_POLISH_ACTION,
        description="Studio polish in progress",
        status=AgentAction.ActionStatus.STARTED,
        input_data={"product_id": str(product_id), "source": source, "session": True},
        output_data={},
    )


def finish_studio_polish_session(
    session,
    *,
    success: bool,
    output_data: dict | None = None,
    error_message: str = "",
) -> None:
    """Complete or fail the expand session started by begin_studio_polish_session."""
    from apps.agents.models import AgentAction

    session.status = (
        AgentAction.ActionStatus.COMPLETED
        if success
        else AgentAction.ActionStatus.FAILED
    )
    session.output_data = output_data or {}
    session.error_message = error_message[:2000] if error_message else ""
    session.completed_at = timezone.now()
    if success:
        session.description = (
            f"Studio polish complete "
            f"({(output_data or {}).get('variations_created', 0)} assets)"
        )
    else:
        reason = (output_data or {}).get("reason") or (output_data or {}).get("error") or "failed"
        session.description = f"Studio polish failed ({reason})"
    session.save(
        update_fields=[
            "status",
            "output_data",
            "error_message",
            "completed_at",
            "description",
        ]
    )


def record_studio_polish(user, *, product_id, provider: str = "photoroom_plus", output_data: dict | None = None) -> None:
    from apps.agents.models import AgentAction

    AgentAction.objects.create(
        user=user,
        agent_type="create",
        action_type=STUDIO_POLISH_ACTION,
        description=f"Studio polish ({provider})",
        status=AgentAction.ActionStatus.COMPLETED,
        input_data={"product_id": str(product_id), "provider": provider},
        output_data=output_data or {},
        completed_at=timezone.now(),
    )


# Backwards compatibility
PRO_SCENE_ACTION = STUDIO_POLISH_ACTION
record_pro_scene = record_studio_polish
