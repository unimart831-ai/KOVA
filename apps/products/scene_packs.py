"""Scene pack presets for Snap studio polish (P0-2) and vertical packs v2 (P1-1)."""

from __future__ import annotations

from typing import Any, TypedDict

SCENE_PACK_AUTO = "auto"
SCENE_PACK_MARKETPLACE_WHITE = "marketplace_white"
SCENE_PACK_FOOD_DELIVERY = "food_delivery"
SCENE_PACK_FASHION_FLAT = "fashion_flat"
SCENE_PACK_BRAND_STUDIO = "brand_studio"

VALID_SCENE_PACKS = frozenset({
    SCENE_PACK_AUTO,
    SCENE_PACK_MARKETPLACE_WHITE,
    SCENE_PACK_FOOD_DELIVERY,
    SCENE_PACK_FASHION_FLAT,
    SCENE_PACK_BRAND_STUDIO,
})

SCENE_PACK_OPTIONS: tuple[dict[str, str], ...] = (
    {"id": SCENE_PACK_AUTO, "label": "Auto", "hint": "Best scenes for your product"},
    {
        "id": SCENE_PACK_MARKETPLACE_WHITE,
        "label": "Marketplace white",
        "hint": "White studio hero + Google Shopping exports",
    },
    {
        "id": SCENE_PACK_FOOD_DELIVERY,
        "label": "Food delivery",
        "hint": "Delivery-app surfaces and food styling",
    },
    {
        "id": SCENE_PACK_FASHION_FLAT,
        "label": "Fashion flat",
        "hint": "Flat lay and mannequin (Pro)",
    },
    {
        "id": SCENE_PACK_BRAND_STUDIO,
        "label": "Brand studio",
        "hint": "Brand-color hero and dark premium scene",
    },
)


def normalize_scene_pack(value: str | None) -> str:
    pack = (value or SCENE_PACK_AUTO).strip().lower()
    return pack if pack in VALID_SCENE_PACKS else SCENE_PACK_AUTO


def get_product_scene_pack(product) -> str:
    meta = getattr(product, "marketplace_metadata", None) or {}
    if not isinstance(meta, dict):
        return SCENE_PACK_AUTO
    return normalize_scene_pack(meta.get("scene_pack"))


def store_product_scene_pack(product, scene_pack: str) -> None:
    pack = normalize_scene_pack(scene_pack)
    if pack == SCENE_PACK_AUTO:
        return
    meta = dict(getattr(product, "marketplace_metadata", None) or {})
    meta["scene_pack"] = pack
    product.marketplace_metadata = meta


def scene_pack_priority_variant_ids(scene_pack: str, *, plan_tier: str) -> tuple[str, ...]:
    """Variant ids to prefer when a scene pack is selected."""
    from apps.products.photoroom_food import FOOD_SURFACE_VARIANT_IDS
    from apps.products.photoroom_plus import _plan_rank

    pack = normalize_scene_pack(scene_pack)
    if pack == SCENE_PACK_MARKETPLACE_WHITE:
        return ("studio_white", "relight", "ai_lifestyle")
    if pack == SCENE_PACK_FOOD_DELIVERY:
        return FOOD_SURFACE_VARIANT_IDS + ("beautify", "flat_lay", "ai_lifestyle")
    if pack == SCENE_PACK_FASHION_FLAT:
        from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG

        ids: list[str] = ["flat_lay"]
        ghost_spec = PLUS_VARIANT_CATALOG.get("ghost_mannequin")
        if ghost_spec and _plan_rank(ghost_spec.min_plan) <= _plan_rank(plan_tier):
            ids.append("ghost_mannequin")
        ids.extend(["studio_white", "ai_lifestyle"])
        return tuple(ids)
    if pack == SCENE_PACK_BRAND_STUDIO:
        return ("studio_brand", "studio_dark", "ai_lifestyle")
    return ()


def scene_pack_hero_studio_ids(scene_pack: str) -> tuple[str, ...] | None:
    """Override hero studio preference for pack-specific heroes."""
    pack = normalize_scene_pack(scene_pack)
    if pack == SCENE_PACK_MARKETPLACE_WHITE:
        return ("studio_white",)
    if pack == SCENE_PACK_BRAND_STUDIO:
        return ("studio_brand", "studio_white")
    return None


def scene_pack_export_budget(scene_pack: str, plan_tier: str) -> tuple[int, int]:
    """Return (story_banner_slots, marketplace_slots) adjusted for pack."""
    from apps.products.photoroom_preflight import (
        marketplace_export_budget,
        total_export_channel_budget,
    )

    story, marketplace = total_export_channel_budget(plan_tier)
    pack = normalize_scene_pack(scene_pack)
    if pack == SCENE_PACK_MARKETPLACE_WHITE:
        mp = marketplace_export_budget(plan_tier)
        if mp > 0:
            return 0, mp
    return story, marketplace


def multi_angle_polish_enabled(plan_tier: str) -> bool:
    from apps.products.photoroom_preflight import GROWTH_PLUS_TIERS

    return (plan_tier or "starter").lower() in GROWTH_PLUS_TIERS


def raw_upload_image_urls(additional_images: list | None) -> list[str]:
    """User-uploaded extras (not generated polish or variation URLs)."""
    urls: list[str] = []
    for url in additional_images or []:
        if not url:
            continue
        if "studio_polish/" in url or "product_variations/" in url:
            continue
        if "channel_" in url or "preflight_" in url:
            continue
        urls.append(url)
    return urls


def marketplace_channel_image_urls(additional_images: list | None) -> list[str]:
    """Google Shopping channel exports from polished additional_images."""
    return [
        url
        for url in (additional_images or [])
        if url and "channel_marketplace_" in url
    ]


# ── Vertical packs v2 (P1-1) ────────────────────────────────────────────────

MITUMBA_KEYWORDS = (
    "mitumba",
    "thrift",
    "secondhand",
    "second-hand",
    "preloved",
    "pre-loved",
    "bale",
    "used clothing",
    "used clothes",
    "flea market",
)

VISION_CATEGORY_ALIASES: dict[str, str] = {
    "women's fashion": "apparel",
    "womens fashion": "apparel",
    "men's fashion": "apparel",
    "mens fashion": "apparel",
    "fashion": "apparel",
    "clothing": "apparel",
    "clothes": "apparel",
    "garments": "apparel",
    "mitumba": "apparel",
    "thrift": "apparel",
    "jewellery": "jewelry",
    "watches": "jewelry",
    "tech": "electronics",
    "gadgets": "electronics",
    "phones": "electronics",
    "fresh produce": "food",
    "snacks": "food",
    "skincare": "beauty",
    "cosmetics": "beauty",
    "home decor": "home",
    "furniture": "home",
}


class VerticalPackPreset(TypedDict, total=False):
    hero_studio_ids: tuple[str, ...]
    commerce_scenes: tuple[str, ...]
    proof_variants: tuple[str, ...]
    priority_variants: tuple[str, ...]
    locked_seeds: dict[str, int]
    pro_only_variants: tuple[str, ...]


VERTICAL_PACK_PRESETS: dict[str, VerticalPackPreset] = {
    "jewelry": {
        "hero_studio_ids": ("studio_dark", "studio_white"),
        "commerce_scenes": (
            "ai_creative_marble",
            "ai_scene_wall",
            "ai_lifestyle",
        ),
        "proof_variants": ("beautify", "relight", "studio_dark"),
        "priority_variants": (
            "studio_dark",
            "ai_creative_marble",
            "ai_lifestyle",
            "beautify",
        ),
        "locked_seeds": {
            "studio_dark": 88210391,
            "ai_creative_marble": 33120477,
            "ai_scene_wall": 65080068,
            "ai_lifestyle": 55994449,
            "beautify": 48672244,
        },
    },
    "electronics": {
        "hero_studio_ids": ("studio_white", "studio_brand"),
        "commerce_scenes": (
            "ai_creative_podium",
            "ai_scene_table",
            "ai_scene_shelf",
        ),
        "proof_variants": ("relight", "background_blur"),
        "priority_variants": (
            "studio_white",
            "relight",
            "ai_creative_podium",
            "ai_scene_table",
        ),
        "locked_seeds": {
            "ai_creative_podium": 48672244,
            "ai_scene_table": 117879368,
            "ai_lifestyle": 65080068,
        },
    },
    "apparel_mitumba": {
        "hero_studio_ids": ("studio_white", "flat_lay"),
        "commerce_scenes": (
            "flat_lay",
            "ai_scene_table",
            "ai_scene_retail",
        ),
        "proof_variants": ("flat_lay", "ghost_mannequin"),
        "priority_variants": (
            "flat_lay",
            "ghost_mannequin",
            "studio_white",
            "ai_scene_table",
        ),
        "pro_only_variants": ("ghost_mannequin",),
        "locked_seeds": {
            "flat_lay": 55994449,
            "ai_scene_table": 48672244,
            "ai_scene_retail": 65080068,
        },
    },
}


def _normalize_vision_category(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    if not cleaned:
        return ""
    if cleaned in VERTICAL_PACK_PRESETS:
        return cleaned
    return VISION_CATEGORY_ALIASES.get(cleaned, cleaned)


def is_mitumba_apparel(product, analysis: dict | None = None) -> bool:
    """Detect mitumba / thrift apparel from product text and vision analysis."""
    analysis = analysis or {}
    blob = " ".join(
        part.lower()
        for part in (
            getattr(product, "name", "") or "",
            " ".join(getattr(product, "tags", None) or []),
            analysis.get("product_category") or "",
            analysis.get("visual_style") or "",
            analysis.get("campaign_angle") or "",
            analysis.get("description") or "",
            " ".join(analysis.get("suggested_tags") or []),
        )
    )
    return any(kw in blob for kw in MITUMBA_KEYWORDS)


def resolve_scene_vertical(
    product,
    analysis: dict | None = None,
    *,
    stall_context: dict | None = None,
) -> str:
    """
    Resolve vertical pack key from rule-based category + vision + stall brief.

    Returns a key in VERTICAL_PACK_PRESETS or the base product category.
    """
    from apps.products.photoroom_plus import detect_product_category

    analysis = analysis or {}
    stall_context = stall_context or {}

    vision_raw = analysis.get("product_category") or stall_context.get("category_hint") or ""
    vision_category = _normalize_vision_category(str(vision_raw))

    base = detect_product_category(product, analysis)
    if vision_category in VERTICAL_PACK_PRESETS:
        return vision_category
    if vision_category in {
        "apparel", "food", "beauty", "jewelry", "electronics", "home", "general",
    }:
        base = vision_category

    if base == "apparel" and is_mitumba_apparel(product, analysis):
        return "apparel_mitumba"
    if base in VERTICAL_PACK_PRESETS:
        return base
    return base


def vertical_pack_preset(vertical: str) -> VerticalPackPreset | None:
    return VERTICAL_PACK_PRESETS.get(vertical)


def vertical_commerce_scenes(vertical: str, *, fallback_category: str) -> tuple[str, ...]:
    preset = vertical_pack_preset(vertical)
    if preset and preset.get("commerce_scenes"):
        return preset["commerce_scenes"]
    from apps.products.photoroom_plus import CATEGORY_COMMERCE_SCENES

    return CATEGORY_COMMERCE_SCENES.get(fallback_category, CATEGORY_COMMERCE_SCENES["general"])


def vertical_proof_variants(vertical: str, *, fallback_category: str) -> tuple[str, ...]:
    preset = vertical_pack_preset(vertical)
    if preset and preset.get("proof_variants"):
        return preset["proof_variants"]
    from apps.products.photoroom_plus import CATEGORY_PROOF_VARIANTS

    return CATEGORY_PROOF_VARIANTS.get(fallback_category, CATEGORY_PROOF_VARIANTS["general"])


def vertical_hero_studio_ids(vertical: str) -> tuple[str, ...] | None:
    preset = vertical_pack_preset(vertical)
    if preset and preset.get("hero_studio_ids"):
        return preset["hero_studio_ids"]
    return None


def vertical_priority_variant_ids(
    vertical: str,
    *,
    plan_tier: str,
    fallback_category: str,
) -> tuple[str, ...]:
    """Plan-aware variant boost order for a detected vertical."""
    from apps.products.photoroom_plus import PLUS_VARIANT_CATALOG, _plan_rank

    preset = vertical_pack_preset(vertical)
    if not preset:
        return ()

    pro_only = set(preset.get("pro_only_variants") or ())
    ids: list[str] = []
    for vid in preset.get("priority_variants") or ():
        if vid in pro_only:
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if not spec or _plan_rank(spec.min_plan) > _plan_rank(plan_tier):
                continue
        ids.append(vid)
    return tuple(ids)


def vertical_locked_seed(vertical: str, variant_id: str) -> int | None:
    preset = vertical_pack_preset(vertical)
    if not preset:
        return None
    seeds = preset.get("locked_seeds") or {}
    return seeds.get(variant_id)


def stall_brief_scene_signals(stall_context: dict | None) -> dict[str, Any]:
    """Extract scene-selection hints from a Batch Snap stall brief."""
    ctx = stall_context or {}
    tone = (ctx.get("campaign_tone") or "").lower()
    category_hint = (ctx.get("category_hint") or "").lower()
    return {
        "category_hint": category_hint,
        "vertical_hint": _normalize_vision_category(category_hint),
        "market_day": True,
        "wholesale_or_clearance": tone in {"wholesale", "clearance_urgency"},
        "premium_boutique": tone == "premium_boutique",
        "stall_title": ctx.get("stall_title") or "",
    }
