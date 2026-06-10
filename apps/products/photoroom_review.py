"""
Human-in-the-loop review flags for alteration-prone Photoroom outputs.

See docs/KOVA_PHOTOROOM_STRATEGY.md Phase 2 (apparel pilot).
"""

from __future__ import annotations

from django.conf import settings

# Variants that may alter product appearance — require seller review before publish.
ALTERATION_REVIEW_VARIANT_IDS = frozenset({
    "ghost_mannequin",
    "virtual_model",
    "beautify",
    "flat_lay",
    "edit_ai_staging",
    "edit_ai_angle",
    "ai_touchup",
    "photofix",
})


def review_alterations_enabled() -> bool:
    return bool(getattr(settings, "PHOTOROOM_REVIEW_ALTERATIONS", True))


def needs_alteration_review(
    variant_id: str,
    *,
    uncertainty_score: float | None = None,
) -> tuple[bool, str]:
    """
    Return (needs_review, reason) for a polish output.

    Ghost mannequin / virtual model always flagged when review is enabled.
    High uncertainty also flags any variant.
    """
    if not review_alterations_enabled():
        return False, ""

    if variant_id in ALTERATION_REVIEW_VARIANT_IDS:
        if variant_id == "ghost_mannequin":
            return True, "ghost_mannequin"
        if variant_id == "virtual_model":
            return True, "virtual_model"
        return True, f"alteration:{variant_id}"

    from apps.products.photoroom_api import uncertainty_is_high

    if uncertainty_is_high(uncertainty_score):
        return True, "high_uncertainty"

    return False, ""


def review_flags_for_output(
    variant_id: str,
    *,
    uncertainty_score: float | None = None,
) -> dict:
    """Metadata merged into record_studio_polish output_data."""
    flagged, reason = needs_alteration_review(
        variant_id, uncertainty_score=uncertainty_score,
    )
    if not flagged:
        return {"needs_review": False}
    return {
        "needs_review": True,
        "review_reason": reason,
        "review_before_publish": True,
    }


def summarize_review_state(actions: list) -> dict:
    """Aggregate review flags from polish AgentAction rows."""
    pending: list[dict] = []
    for action in actions:
        out = action.output_data or {}
        if not out.get("needs_review"):
            continue
        pending.append({
            "variant": out.get("variant") or "",
            "label": out.get("label") or out.get("variant") or "Scene",
            "url": out.get("url") or "",
            "reason": out.get("review_reason") or "alteration",
            "uncertainty_score": out.get("uncertainty_score"),
        })
    return {
        "alteration_review_required": bool(pending),
        "review_pending_count": len(pending),
        "review_pending": pending,
    }
