"""
Platform-aware visual routing — pick the right polished asset per network + format.

Social-media-manager quality means:
- Instagram feed carousels → 4:5 portrait when available (more screen real estate)
- Instagram / TikTok / Facebook reels → 9:16 story exports only
- LinkedIn carousels → square or landscape heroes
- Facebook feed → square heroes
- Never ship banner (16:9) or marketplace crops to feed carousels

Works with Photoroom channel exports (channel_story, channel_feed_portrait, etc.)
and studio-polished square/lifestyle assets from the Plus pack.
"""

from __future__ import annotations

from dataclasses import dataclass

# URL markers produced by Photoroom Plus variants (see photoroom_plus.PLUS_VARIANT_CATALOG)
STORY_MARKERS = ("channel_story_uncrop", "channel_story")
PORTRAIT_FEED_MARKERS = ("channel_feed_portrait",)
SQUARE_FEED_MARKERS = (
    "studio_white",
    "studio_brand",
    "studio_dark",
    "studio_safe",
    "composition_hero",
    "edit_ai_staging",
    "edit_ai_angle",
    "ai_scene_",
    "ai_lifestyle",
    "ai_creative_",
    "flat_lay",
    "ghost_mannequin",
    "beautify",
)
BLOCKED_FOR_FEED = (
    "channel_banner",
    "channel_marketplace",
    "preflight_",
    "promo_frame",
    "sandbox",
    "local_quick_polish",
)
BLOCKED_FOR_REEL = BLOCKED_FOR_FEED + (
    "/carousels/",
    "catalog_carousel",
    "product_carousel",
)


@dataclass(frozen=True)
class PlatformVisualProfile:
    """Preferred aspect + asset markers for one platform + post format."""

    platform: str
    post_format: str
    aspect_ratio: str  # Post.AspectRatio value
    preferred_markers: tuple[str, ...]
    fallback_markers: tuple[str, ...]
    blocked_markers: tuple[str, ...] = BLOCKED_FOR_FEED


PLATFORM_PROFILES: dict[tuple[str, str], PlatformVisualProfile] = {
    ("instagram", "carousel"): PlatformVisualProfile(
        platform="instagram",
        post_format="carousel",
        aspect_ratio="portrait",
        preferred_markers=PORTRAIT_FEED_MARKERS + SQUARE_FEED_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
    ),
    ("instagram", "image"): PlatformVisualProfile(
        platform="instagram",
        post_format="image",
        aspect_ratio="portrait",
        preferred_markers=PORTRAIT_FEED_MARKERS + SQUARE_FEED_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
    ),
    ("instagram", "reel"): PlatformVisualProfile(
        platform="instagram",
        post_format="reel",
        aspect_ratio="story",
        preferred_markers=STORY_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
        blocked_markers=BLOCKED_FOR_REEL,
    ),
    ("facebook", "carousel"): PlatformVisualProfile(
        platform="facebook",
        post_format="carousel",
        aspect_ratio="square",
        preferred_markers=SQUARE_FEED_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
    ),
    ("facebook", "reel"): PlatformVisualProfile(
        platform="facebook",
        post_format="reel",
        aspect_ratio="story",
        preferred_markers=STORY_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
        blocked_markers=BLOCKED_FOR_REEL,
    ),
    ("tiktok", "reel"): PlatformVisualProfile(
        platform="tiktok",
        post_format="reel",
        aspect_ratio="story",
        preferred_markers=STORY_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
        blocked_markers=BLOCKED_FOR_REEL,
    ),
    ("linkedin", "carousel"): PlatformVisualProfile(
        platform="linkedin",
        post_format="carousel",
        aspect_ratio="square",
        preferred_markers=SQUARE_FEED_MARKERS,
        fallback_markers=SQUARE_FEED_MARKERS,
    ),
    ("linkedin", "reel"): PlatformVisualProfile(
        platform="linkedin",
        post_format="reel",
        aspect_ratio="story",
        preferred_markers=STORY_MARKERS + ("channel_banner",),
        fallback_markers=SQUARE_FEED_MARKERS,
        blocked_markers=BLOCKED_FOR_REEL,
    ),
}


def profile_for(platform: str, post_format: str) -> PlatformVisualProfile | None:
    key = ((platform or "").lower(), (post_format or "image").lower())
    return PLATFORM_PROFILES.get(key)


def _url_matches(url: str, marker: str) -> bool:
    return marker in (url or "").lower()


def _score_url(url: str, markers: tuple[str, ...]) -> int:
    """Lower score = better match (first preferred marker wins)."""
    low = (url or "").lower()
    for idx, marker in enumerate(markers):
        if marker in low:
            return idx
    return 999


def pick_platform_images(
    urls: list[str],
    *,
    platform: str,
    post_format: str,
    max_count: int | None = None,
) -> list[str]:
    """
    Return URLs ordered for this platform + format — best assets first, distinct.
    """
    prof = profile_for(platform, post_format)
    if not prof:
        return _dedupe(urls, max_count)

    clean = [
        u for u in urls
        if u and not any(b in u.lower() for b in prof.blocked_markers)
    ]
    if not clean:
        clean = [u for u in urls if u]

    ranked = sorted(
        clean,
        key=lambda u: _score_url(u, prof.preferred_markers),
    )

    # Composition hero always first when present
    composition = [u for u in ranked if "composition_hero" in u.lower()]
    rest = [u for u in ranked if u not in composition]
    ordered = composition + rest

    return _dedupe(ordered, max_count)


def aspect_ratio_for(platform: str, post_format: str) -> str:
    """Post.AspectRatio value for this platform + format."""
    prof = profile_for(platform, post_format)
    if prof:
        return prof.aspect_ratio
    if (post_format or "").lower() in ("reel", "story"):
        return "story"
    return "square"


def _dedupe(urls: list[str], max_count: int | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
        if max_count and len(out) >= max_count:
            break
    return out
