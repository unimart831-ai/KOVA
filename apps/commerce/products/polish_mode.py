"""Snap polish mode — studio (Plus) vs lite (Basic + local presets)."""

from __future__ import annotations

POLISH_MODE_STUDIO = "studio"
POLISH_MODE_LITE = "lite"

VALID_POLISH_MODES = frozenset({POLISH_MODE_STUDIO, POLISH_MODE_LITE})

LITE_POLISH_NOTICE = (
    "Lite uses basic cutout and local presets — upgrade for full studio scenes."
)


def normalize_polish_mode(value: str | None) -> str:
    mode = (value or POLISH_MODE_STUDIO).strip().lower()
    return mode if mode in VALID_POLISH_MODES else POLISH_MODE_STUDIO


def get_product_polish_mode(product) -> str:
    meta = getattr(product, "marketplace_metadata", None) or {}
    if not isinstance(meta, dict):
        return POLISH_MODE_STUDIO
    return normalize_polish_mode(meta.get("polish_mode"))


def store_product_polish_mode(product, polish_mode: str) -> None:
    mode = normalize_polish_mode(polish_mode)
    if mode == POLISH_MODE_STUDIO:
        return
    meta = dict(getattr(product, "marketplace_metadata", None) or {})
    meta["polish_mode"] = mode
    product.marketplace_metadata = meta


def studio_polish_unavailable(user) -> bool:
    """True when Plus studio cannot run (missing key or platform cap)."""
    from apps.core.billing.visual_credits import get_visual_credit_usage
    from apps.commerce.products.photoroom import photoroom_enabled

    if not photoroom_enabled():
        return True
    usage = get_visual_credit_usage(user)
    return bool(usage.get("platform_blocked") or usage.get("growth_throttled"))


def resolve_polish_mode(user, explicit: str | None = None, *, product=None) -> str:
    """
    Pick lite vs studio for expand pipeline.

    Lite when merchant chose it, Photoroom Plus is unavailable, or platform pool
    is throttled/blocked — avoids burning Plus credits on failed retries.
    """
    requested = normalize_polish_mode(explicit)
    if product is not None and explicit is None:
        requested = get_product_polish_mode(product)
    if requested == POLISH_MODE_LITE:
        return POLISH_MODE_LITE
    if studio_polish_unavailable(user):
        return POLISH_MODE_LITE
    return POLISH_MODE_STUDIO


def resolve_polish_mode_for_snap(user, posted: str | None) -> str:
    """Snap launch — honor explicit lite; auto-fallback when studio unavailable."""
    return resolve_polish_mode(user, posted)
