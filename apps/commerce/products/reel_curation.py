"""
Curate product image URLs for motion reels — story hook → hero → AI / Edit-AI → CTA.

Ensures reels use distinct scenes with varied pacing, not every export.
Skips raw uploads, preflight intermediates, and low-quality sandbox outputs.
"""

from __future__ import annotations

REEL_EXCLUDE_MARKERS = (
    "preflight_",
    "channel_banner",
    "channel_marketplace",
    "sandbox",
    "local_quick_polish",
    "photofix",
    "/carousels/",
    "catalog_carousel",
    "product_carousel",
)
REEL_RAW_SNAP_MARKERS = ("product_images/",)
REEL_MAX_SLIDES = 5
REEL_MAX_AI_SCENES = 4
REEL_MIN_SLIDES = 3
STORY_EXPORT_MARKERS = ("channel_story_uncrop", "channel_story")


def story_export_urls(urls: list[str]) -> list[str]:
    """Native Photoroom 9:16 exports — prefer uncrop before cropped story."""
    uncrop = [u for u in urls if u and "channel_story_uncrop" in u.lower()]
    story = [u for u in urls if u and "channel_story" in u.lower() and u not in uncrop]
    seen: set[str] = set()
    ordered: list[str] = []
    for url in uncrop + story:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _is_native_story_export(url: str) -> bool:
    u = (url or "").lower()
    return any(m in u for m in STORY_EXPORT_MARKERS)


def _is_raw_snap_url(url: str) -> bool:
    """Unpolished camera upload — skip when Plus/studio variants exist."""
    u = url.lower()
    if any(m in u for m in REEL_RAW_SNAP_MARKERS) and "studio_polish" not in u:
        return True
    return False


def _is_reel_excluded(url: str) -> bool:
    u = (url or "").lower()
    return any(m in u for m in REEL_EXCLUDE_MARKERS)


def _variant_tier(url: str) -> tuple[int, int, str]:
    """Lower sort key = earlier in reel."""
    u = url.lower()
    if "composition_hero" in u:
        return (-1, 0, url)
    if "channel_story_uncrop" in u:
        return (0, 0, url)
    if "channel_story" in u:
        return (0, 1, url)
    if any(m in u for m in ("studio_safe", "studio_white", "service_hero", "digital_desk_hero")):
        return (1, 0, url)
    if "studio_brand" in u or "studio_dark" in u:
        return (1, 1, url)
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
    if "background_blur" in u or "relight_nocutout" in u:
        return (3, 3, url)
    if any(
        m in u
        for m in (
            "ghost_mannequin",
            "virtual_model",
            "virtual_model_hold",
            "virtual_model_adorn",
            "flat_lay",
            "relight",
            "beautify",
        )
    ):
        return (4, 0, url)
    if "promo_frame" in u:
        return (8, 0, url)
    return (5, 0, url)


def curate_reel_image_urls(
    urls: list[str],
    *,
    max_slides: int = REEL_MAX_SLIDES,
    upload_only: bool = False,
) -> list[str]:
    """
    Order URLs for a cinematic reel: portrait hook → hero → one AI scene → promo CTA.

    Professional pacing: 3–5 slides max; at most 2 AI-generated scenes.

    When ``upload_only`` is True (Use as-is products), keep merchant upload order
    and include raw ``product_images/`` paths — no studio/AI tier sorting.
    """
    clean = [
        u for u in urls
        if u and not _is_reel_excluded(u)
    ]
    if not clean:
        return []

    if upload_only:
        seen: set[str] = set()
        result: list[str] = []
        for url in clean:
            if url in seen:
                continue
            seen.add(url)
            result.append(url)
            if len(result) >= max_slides:
                break
        return result

    polished = [u for u in clean if not _is_raw_snap_url(u)]
    pool = polished if polished else clean

    ordered = sorted(pool, key=_variant_tier)

    ai_markers = (
        "ai_scene_",
        "ai_creative_",
        "ai_lifestyle",
        "ai_contextual",
        "edit_ai_staging",
        "edit_ai_angle",
        "ghost_mannequin",
        "virtual_model",
        "virtual_model_hold",
        "virtual_model_adorn",
        "flat_lay",
        "beautify",
    )
    ai_kept = 0
    result: list[str] = []
    seen: set[str] = set()

    for url in ordered:
        if url in seen:
            continue
        is_ai = any(m in url for m in ai_markers)
        if is_ai:
            if ai_kept >= REEL_MAX_AI_SCENES:
                continue
            ai_kept += 1
        result.append(url)
        seen.add(url)
        if len(result) >= max_slides:
            break

    promo = [u for u in result if "promo_frame" in u]
    if promo:
        result = [u for u in result if "promo_frame" not in u] + promo

    # Prefer native 9:16 story exports as opening hero frames (before FFmpeg reframe).
    story_frames = story_export_urls(pool)
    if story_frames:
        body = [u for u in result if not _is_native_story_export(u)]
        result = story_frames[:2] + body
        seen_story: set[str] = set()
        deduped: list[str] = []
        for url in result:
            if url in seen_story:
                continue
            seen_story.add(url)
            deduped.append(url)
        result = deduped[:max_slides]

    if len(pool) >= REEL_MIN_SLIDES and len(result) < REEL_MIN_SLIDES:
        for url in ordered:
            if url in seen:
                continue
            is_ai = any(m in url for m in ai_markers)
            if is_ai and ai_kept >= REEL_MAX_AI_SCENES:
                continue
            if is_ai:
                ai_kept += 1
            result.append(url)
            seen.add(url)
            if len(result) >= REEL_MIN_SLIDES or len(result) >= max_slides:
                break

    return result[:max_slides]
