"""
Photoroom Create Any Image — promo / sale banners for Agency campaigns (P2).
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def create_any_image_enabled(user) -> bool:
    from apps.billing.models import get_effective_plan_tier

    if not getattr(settings, "PHOTOROOM_CREATE_ANY_ENABLED", False):
        return False
    if not getattr(settings, "PHOTOROOM_API_KEY", ""):
        return False
    tier = get_effective_plan_tier(getattr(user, "profile", None))
    return tier in ("agency", "pro")


def generate_promo_banner(
    *,
    prompt: str,
    output_size: str = "1080x1080",
    seed: int | None = None,
) -> bytes | None:
    """Generate a branded promo frame via Plus create-any-image params."""
    from apps.products.photoroom_plus import photoroom_edit

    params = {
        "background.prompt": prompt[:500],
        "outputSize": output_size,
        "export.format": "jpeg",
        "removeBackground": "false",
    }
    if seed is not None:
        params["background.seed"] = str(seed)

    # Create Any Image uses prompt-only generation — no source image required in some flows;
    # we pass a 1×1 placeholder via photoroom_edit when no hero exists.
    result = photoroom_edit("", params)
    if result.ok and result.content:
        return result.content
    logger.warning("Create Any Image failed: %s", result.error)
    return None
