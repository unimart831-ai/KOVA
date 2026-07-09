"""
Professional carousel studio — curated assets, storyboard, and product-first layouts.

Design goals (parity with reel_studio + Photoroom polish):
- Square 1080×1080 slides using studio-polished assets only
- Text in dedicated bars/panels — never covering the product hero
- Distinct image per slide (no repeated modulo indexing)
- 5–6 slides: hook → showcase → benefit → showcase → price → CTA
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

# Layouts where the product frame must stay text-free.
PRODUCT_ONLY_LAYOUTS = frozenset({"minimal_caption", "showcase"})

CAROUSEL_BLOCKED_MARKERS = (
    "channel_story",
    "channel_banner",
    "channel_marketplace",
    "preflight_",
    "promo_frame",
    "sandbox",
    "local_quick_polish",
    "photofix",
)


@dataclass
class PreparedCarousel:
    plan: list[dict]
    image_urls: list[str]


def professional_mode_enabled() -> bool:
    return bool(getattr(settings, "CAROUSEL_PROFESSIONAL_MODE", True))


def show_slide_counters() -> bool:
    return bool(getattr(settings, "CAROUSEL_SHOW_COUNTERS", False))


def _variant_tier(url: str) -> tuple[int, int, str]:
    u = (url or "").lower()
    if "composition_hero" in u:
        return (0, 0, url)
    if any(m in u for m in ("studio_white", "studio_brand", "studio_safe", "service_hero")):
        return (1, 0, url)
    if "edit_ai_staging" in u:
        return (1, 2, url)
    if "edit_ai_angle" in u:
        return (1, 3, url)
    if "virtual_model" in u or "ghost_mannequin" in u:
        return (2, 0, url)
    if "ai_scene_" in u or "ai_creative_" in u:
        return (2, 1, url)
    if "ai_lifestyle" in u or "ai_contextual" in u:
        return (3, 0, url)
    if "flat_lay" in u or "beautify" in u:
        return (3, 1, url)
    return (4, 0, url)


def curate_carousel_images(urls: list[str], *, max_images: int | None = None) -> list[str]:
    """Order distinct square-ready studio assets for carousel slides."""
    from apps.products.photoroom_plus import filter_carousel_urls

    max_images = max_images or int(getattr(settings, "CAROUSEL_MAX_SOURCE_IMAGES", 8))
    pool = filter_carousel_urls([u for u in urls if u])
    clean = [
        u for u in pool
        if not any(m in (u or "").lower() for m in CAROUSEL_BLOCKED_MARKERS)
    ]
    if not clean:
        clean = pool
    if not clean:
        return []

    ordered = sorted(clean, key=_variant_tier)
    seen: set[str] = set()
    result: list[str] = []
    for url in ordered:
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= max_images:
            break
    return result


def assign_images_to_plan(plan: list[dict], curated_urls: list[str]) -> list[dict]:
    """Bind a unique curated URL to each slide spec — never reuse until pool exhausted."""
    if not curated_urls:
        return plan

    used: set[str] = set()
    assigned: list[dict] = []

    def _pick(preferred_index: int, *, product_only: bool = False) -> str:
        if preferred_index < len(curated_urls):
            candidate = curated_urls[preferred_index]
            if candidate not in used:
                return candidate
        for url in curated_urls:
            if url in used:
                continue
            if product_only and "studio" not in url.lower() and "composition" not in url.lower():
                # Prefer studio, but accept any unused if none left
                continue
            return url
        # Exhausted unique pool — allow reuse of least-used preferred, then any
        for url in curated_urls:
            if url not in used:
                return url
        return curated_urls[preferred_index % len(curated_urls)]

    for idx, spec in enumerate(plan):
        spec = dict(spec)
        layout = spec.get("layout", "")
        role = (spec.get("role") or "").lower()
        preferred = int(spec.get("image_index", idx))
        product_only = layout in PRODUCT_ONLY_LAYOUTS or layout == "minimal_caption"

        # Price / CTA slides: prefer a different hero than the opening hook
        if role in ("price", "cta") and len(curated_urls) > 1:
            preferred = max(1, preferred)

        url = _pick(preferred, product_only=product_only)
        used.add(url)
        spec["image_url"] = url
        assigned.append(spec)

    return assigned


def build_professional_carousel_plan(
    product,
    analysis: dict | None,
    key_features: list[str] | None,
    *,
    image_count: int = 1,
) -> list[dict]:
    """
    Commerce carousel arc — hook → showcase → benefit → showcase → price → CTA.
    Product-first layouts only; text never covers the product hero.
    """
    from apps.products.product_copy import (
        clean_description_sentence,
        split_description_sentences,
        strip_feature_bullet,
    )

    analysis = analysis or {}
    features = [strip_feature_bullet(str(f)) for f in (key_features or analysis.get("key_features") or [])]
    features = [f for f in features if f]

    sentences = analysis.get("description_sentences") or []
    if not sentences and analysis.get("description"):
        sentences = split_description_sentences(analysis["description"])
    sentences = [clean_description_sentence(s) for s in sentences if s]

    angle = (analysis.get("campaign_angle") or "").strip()
    hook = angle[:90] if angle else ""
    if not hook and sentences:
        hook = sentences[0][:90]
    if not hook and features:
        hook = features[0][:90]
    if not hook:
        hook = "Crafted for everyday quality you can see."

    name = (product.name or "Our pick").strip()
    price = (product.display_price or "").strip()
    # Reserve room for CTA as final slide when price exists
    max_slides = int(getattr(settings, "CAROUSEL_MAX_SLIDES", 6))
    max_slides = max(4, max_slides)

    plan: list[dict] = []

    plan.append({
        "layout": "clean_split",
        "headline": name,
        "body": hook,
        "image_index": 0,
        "role": "hook",
    })

    if image_count >= 2:
        plan.append({
            "layout": "minimal_caption",
            "headline": "",
            "caption": "",
            "image_index": 1,
            "role": "showcase",
        })

    if features:
        plan.append({
            "layout": "side_panel",
            "headline": features[0][:100],
            "body": sentences[1][:140] if len(sentences) > 1 else "",
            "image_index": min(2, max(image_count - 1, 0)),
            "role": "benefit",
        })

    if image_count >= 3 and len(features) > 1:
        plan.append({
            "layout": "minimal_caption",
            "headline": "",
            "caption": features[1][:48],
            "image_index": min(3, max(image_count - 1, 0)),
            "role": "showcase",
        })
    elif image_count >= 3:
        plan.append({
            "layout": "minimal_caption",
            "headline": "",
            "caption": "",
            "image_index": min(2, max(image_count - 1, 0)),
            "role": "showcase",
        })

    if price:
        # Prefer a distinct image from the opening hook (index 1+)
        price_idx = 1 if image_count > 1 else 0
        plan.append({
            "layout": "price_bar",
            "headline": price,
            "body": sentences[-1][:120] if sentences else "Order on WhatsApp — tap the link.",
            "subtext": name,
            "image_index": price_idx,
            "role": "price",
        })
        # Explicit CTA slide — brand + action, no product overlay
        plan.append({
            "layout": "closing_cta",
            "headline": "Order on WhatsApp",
            "body": price,
            "subtext": name,
            "image_index": 0,
            "role": "cta",
        })

    return plan[:max_slides]


def prepare_carousel_generation(
    product,
    analysis: dict | None,
    key_features: list[str] | None,
) -> PreparedCarousel:
    """Curate images, build plan, assign unique URLs per slide."""
    from apps.products.product_copy import build_product_carousel_plan

    raw = list(product.carousel_image_urls or product.all_image_urls or [])
    curated = curate_carousel_images(raw)

    if professional_mode_enabled():
        plan = build_professional_carousel_plan(
            product, analysis, key_features, image_count=max(len(curated), 1),
        )
    else:
        plan = build_product_carousel_plan(product, analysis, key_features)

    plan = assign_images_to_plan(plan, curated)
    return PreparedCarousel(plan=plan, image_urls=curated)
