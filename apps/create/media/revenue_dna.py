"""Revenue DNA — winning hooks/CTAs/formats from attribution."""

from __future__ import annotations

from typing import Any


def get_revenue_dna_hints(user, *, days: int = 30) -> dict[str, Any]:
    """Top-performing campaign angles for proposal biasing."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.create.briefs.asset_attribution import asset_type_breakdown, top_asset_this_week

    since = timezone.now() - timedelta(days=days)
    top = top_asset_this_week(user, since) or {}
    rows = asset_type_breakdown(user, since) or []
    winning_hooks: list[str] = []
    if top.get("title"):
        winning_hooks.append(str(top["title"])[:120])
    winning_formats = [str(r.get("type_label", "")) for r in rows if r.get("type_label")]
    return {
        "winning_hooks": winning_hooks,
        "winning_formats": list(dict.fromkeys(winning_formats)),
        "top_revenue_kes": float(top.get("revenue") or 0),
    }


def bias_proposals_with_revenue_dna(proposals: list, hints: dict) -> list:
    """Boost proposals whose intent matches recent revenue winners."""
    if not hints.get("winning_hooks"):
        return proposals
    hooks_text = " ".join(hints["winning_hooks"]).lower()
    for p in proposals:
        title = (getattr(p, "title", "") or "").lower()
        if any(word in hooks_text for word in title.split() if len(word) > 4):
            p.rationale = (getattr(p, "rationale", "") + " (Revenue DNA: similar angle performed well.)").strip()
    return proposals
