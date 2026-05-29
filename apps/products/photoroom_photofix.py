"""
Photoroom PhotoFix — auto-correct lighting, brightness, and color before studio polish.

Maps to beautify.mode + lighting.mode on v2/edit (catalog variant `photofix`).
https://www.photoroom.com/api
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PHOTOFIX_VARIANT_ID = "photofix"


def photofix_enabled() -> bool:
    if not getattr(settings, "PHOTOROOM_PHOTOFIX_ENABLED", True):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def should_run_photofix_for_commerce(*, commerce_source: str | None = None) -> bool:
    """Snap / batch uploads always get PhotoFix when enabled."""
    if not photofix_enabled():
        return False
    if commerce_source in ("snap", "batch_snap", "snap_to_sell"):
        return True
    return bool(getattr(settings, "PHOTOROOM_PHOTOFIX_ALWAYS", False))


def photofix_params() -> dict[str, str]:
    """Flat v2/edit params for PhotoFix (no background removal)."""
    output_size = getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")
    return {
        "removeBackground": "false",
        "beautify.mode": "ai.auto",
        "lighting.mode": "ai.auto",
        "outputSize": output_size,
        "export.format": "jpeg",
        "referenceBox": "originalImage",
    }
