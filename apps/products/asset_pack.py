"""
Merchant-facing asset pack — group polish outputs by channel (Feed · Story · Marketplace · Original).
"""

from __future__ import annotations

from dataclasses import dataclass

FEED_MARKERS = (
    "studio_polish/",
    "studio_white",
    "studio_brand",
    "studio_dark",
    "studio_safe",
    "ai_scene_",
    "edit_ai_",
    "ai_lifestyle",
    "ai_creative_",
    "composition_hero",
    "promo_frame",
)
STORY_MARKERS = ("channel_story_uncrop", "channel_story")
PORTRAIT_FEED_MARKERS = ("channel_feed_portrait",)
MARKETPLACE_MARKERS = ("channel_marketplace_",)
ORIGINAL_MARKERS = ("product_images/",)


@dataclass
class AssetPackGroup:
    id: str
    label: str
    hint: str
    urls: list[str]


def _classify_url(url: str) -> str:
    u = (url or "").lower()
    if not u:
        return "other"
    if any(m in u for m in MARKETPLACE_MARKERS):
        return "marketplace"
    if any(m in u for m in STORY_MARKERS):
        return "story"
    if any(m in u for m in PORTRAIT_FEED_MARKERS):
        return "feed"
    if "preflight_" in u or "channel_banner" in u:
        return "other"
    if any(m in u for m in ORIGINAL_MARKERS) and "studio_polish" not in u:
        return "original"
    if any(m in u for m in FEED_MARKERS):
        return "feed"
    if "product_variations/" in u:
        return "feed"
    return "feed"


def build_asset_pack(product) -> list[AssetPackGroup]:
    """Build tab groups for product detail asset pack UI."""
    from apps.products.gallery_preferences import filter_gallery_urls

    urls = filter_gallery_urls(list(product.all_image_urls or []), product)
    buckets: dict[str, list[str]] = {
        "feed": [],
        "story": [],
        "marketplace": [],
        "original": [],
    }
    seen: set[str] = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        bucket = _classify_url(url)
        if bucket in buckets:
            buckets[bucket].append(url)

    groups = [
        AssetPackGroup(
            id="feed",
            label="Feed",
            hint="Square 1080×1080 or portrait 1080×1350 — Instagram & Facebook carousels",
            urls=buckets["feed"],
        ),
        AssetPackGroup(
            id="story",
            label="Story",
            hint="Portrait 9:16 — Reels & Stories (native Photoroom export)",
            urls=buckets["story"],
        ),
        AssetPackGroup(
            id="marketplace",
            label="Marketplace",
            hint="Google Shopping white background 1000×1000",
            urls=buckets["marketplace"],
        ),
        AssetPackGroup(
            id="original",
            label="Original",
            hint="Your camera upload — unmodified",
            urls=buckets["original"],
        ),
    ]
    return [g for g in groups if g.urls]
