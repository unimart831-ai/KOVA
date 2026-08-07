"""WhatsApp plan access helpers — inbox wedge vs full Business module."""

from __future__ import annotations

from apps.core.billing.models import get_user_plan_limits


def whatsapp_inbox_allowed(limits: dict | None) -> bool:
    """Inbox + utility replies (Growth wedge, Pro+ full)."""
    if not limits:
        return False
    return bool(
        limits.get("whatsapp_enabled")
        or limits.get("whatsapp_inbox_enabled")
    )


def whatsapp_full_allowed(limits: dict | None) -> bool:
    """Broadcasts, templates, Status Studio, channels (Pro+)."""
    if not limits:
        return False
    return bool(limits.get("whatsapp_enabled"))


def user_has_whatsapp_inbox(user) -> bool:
    return whatsapp_inbox_allowed(get_user_plan_limits(user))


def user_has_whatsapp_full(user) -> bool:
    return whatsapp_full_allowed(get_user_plan_limits(user))
