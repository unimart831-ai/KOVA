"""
Curate product image URLs for motion reels — story hook → hero → AI / Edit-AI → CTA.

Ensures reels use distinct scenes with varied pacing, not every export.
"""

from __future__ import annotations

REEL_EXCLUDE_MARKERS = ("preflight_", "channel_banner")
REEL_MAX_SLIDES = 5


def _variant_tier(url: str) -> tuple[int, int, str]:
    """Lower sort key = earlier in reel."""
    u = url.lower()
    if "channel_story_uncrop" in u:
        return (0, 0, url)
    if "channel_story" in u:
        return (0, 1, url)
    if any(m in u for m in ("studio_white", "service_hero", "digital_desk_hero")):
        return (1, 0, url)
    if "edit_ai_staging" in u:
        return (1, 5, url)
    if "edit_ai_angle" in u:
        return (1, 6, url)
    if "ai_scene_" in u:
        idx = u.find("ai_scene_")
        return (2, hash(u[idx : idx + 20]) % 100, url)
    if "ai_creative_" in u:
        idx = u.find("ai_creative_")
        return (2, hash(u[idx : idx + 24]) % 100, url)
    if "ai_lifestyle_alt" in u:
        return (3, 1, url)
    if "ai_lifestyle" in u:
        return (3, 0, url)
    if "ai_contextual" in u:
        return (3, 2, url)
    if any(m in u for m in ("ghost_mannequin", "virtual_model", "flat_lay", "relight")):
        return (4, 0, url)
    if "promo_frame" in u:
        return (8, 0, url)
    return (5, 0, url)


def curate_reel_image_urls(urls: list[str], *, max_slides: int = REEL_MAX_SLIDES) -> list[str]:
    """
    Order URLs for a cinematic reel: portrait hook → hero → Edit-AI / AI scenes → promo CTA.
    """
    clean = [
        u for u in urls
        if u and not any(m in u for m in REEL_EXCLUDE_MARKERS)
    ]
    if not clean:
        return []

    ordered = sorted(clean, key=_variant_tier)

    ai_markers = (
        "ai_scene_",
        "ai_creative_",
        "ai_lifestyle",
        "ai_contextual",
        "edit_ai_staging",
        "edit_ai_angle",
    )
    ai_kept = 0
    max_ai = 3
    result: list[str] = []
    seen: set[str] = set()

    for url in ordered:
        if url in seen:
            continue
        is_ai = any(m in url for m in ai_markers)
        if is_ai:
            if ai_kept >= max_ai:
                continue
            ai_kept += 1
        result.append(url)
        seen.add(url)
        if len(result) >= max_slides * 2:
            break

    promo = [u for u in result if "promo_frame" in u]
    if promo:
        result = [u for u in result if "promo_frame" not in u] + promo

    return result[: max_slides * 2]
