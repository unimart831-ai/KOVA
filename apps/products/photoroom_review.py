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
    "virtual_model_hold",
    "virtual_model_adorn",
    "beautify",
    "beautify_nocutout",
    "flat_lay",
    "edit_ai_staging",
    "edit_ai_angle",
    "ai_touchup",
    "photofix",
    "ai_ironing",
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
        if variant_id in ("virtual_model_hold", "virtual_model_adorn"):
            return True, variant_id
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
        "review_status": "pending",
    }


def summarize_review_state(actions: list) -> dict:
    """Aggregate review flags from polish AgentAction rows."""
    pending: list[dict] = []
    for action in actions:
        out = action.output_data or {}
        if not out.get("needs_review"):
            continue
        review_status = out.get("review_status") or "pending"
        if review_status in ("approved", "rejected"):
            continue
        pending.append({
            "variant": out.get("variant") or "",
            "label": out.get("label") or out.get("variant") or "Scene",
            "url": out.get("url") or "",
            "reason": out.get("review_reason") or "alteration",
            "uncertainty_score": out.get("uncertainty_score"),
            "review_status": review_status,
            "action_id": str(action.pk),
        })
    return {
        "alteration_review_required": bool(pending),
        "review_pending_count": len(pending),
        "review_pending": pending,
    }


def review_state_for_product(product) -> dict:
    """Aggregate review flags for a product's polish outputs."""
    from apps.products.gallery_preferences import polish_actions_for_product

    actions = list(polish_actions_for_product(product)[:80])
    return summarize_review_state(actions)


def post_blocked_by_alteration_review(post) -> tuple[bool, str]:
    """
    Block autopublish when alteration-prone polish outputs are pending review.

    Returns (blocked, human-readable reason).
    """
    if not review_alterations_enabled():
        return False, ""

    product = getattr(post, "product", None)
    if not product:
        return False, ""

    state = review_state_for_product(product)
    if not state.get("alteration_review_required"):
        return False, ""

    count = int(state.get("review_pending_count") or 0)
    pending = state.get("review_pending") or []
    labels = ", ".join(
        (p.get("label") or p.get("variant") or "scene")[:24]
        for p in pending[:3]
    )
    suffix = f" ({labels})" if labels else ""
    reason = (
        f"{count} polished scene{'s' if count != 1 else ''} need your approval "
        f"before publish{suffix}."
    )
    return True, reason


def block_post_for_alteration_review(post, *, source: str = "publish") -> None:
    """Move post to pending approval and notify merchant."""
    from apps.content.models import Post
    from apps.notifications.models import Notification

    blocked, reason = post_blocked_by_alteration_review(post)
    if not blocked:
        return

    post.status = Post.Status.PENDING_APPROVAL
    post.ai_reasoning = f"ALTERATION REVIEW ({source}): {reason}"[:500]
    post.save(update_fields=["status", "ai_reasoning", "updated_at"])
    Notification.create_for_user(
        post.user,
        "system",
        f"Publish paused — approve polished scenes on the product page. {reason[:120]}",
        related_post=post,
    )
