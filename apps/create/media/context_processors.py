"""Template context for media orchestration capabilities."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache


def _empty_caps() -> dict:
    return {
        "kling_reels": False,
        "bannerbear_carousels": False,
        "flux_edits_per_month": 0,
        "photoroom_enabled": False,
        "orchestration_enabled": bool(getattr(settings, "MEDIA_ORCHESTRATION_ENABLED", True)),
    }


def media_capabilities(request):
    """Expose plan-tier media features to all authenticated templates."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"media_caps": _empty_caps()}

    cache_key = f"media_caps:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return {"media_caps": cached}

    from apps.core.billing.models import get_user_plan_limits
    from apps.commerce.products.photoroom import photoroom_enabled

    limits = get_user_plan_limits(user)
    caps = {
        "kling_reels": bool(limits.get("kling_reels_enabled")),
        "bannerbear_carousels": bool(limits.get("bannerbear_carousels_enabled")),
        "flux_edits_per_month": int(limits.get("fal_flux_edits_per_month") or 0),
        "photoroom_enabled": photoroom_enabled(),
        "orchestration_enabled": bool(getattr(settings, "MEDIA_ORCHESTRATION_ENABLED", True)),
    }
    cache.set(cache_key, caps, 120)
    return {"media_caps": caps}
