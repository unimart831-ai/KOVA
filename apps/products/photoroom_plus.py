"""
Photoroom Plus v2/edit — full feature catalog and smart variant selection.

Each variant = one API call = one visual credit.
See https://docs.photoroom.com/image-editing-api-plus-plan/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PHOTOROOM_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
AI_BG_MODEL_HEADER = "background-studio-beta-2025-03-17"
AI_BG_SEEDS = (117879368, 55994449, 48672244, 65080068, 88210391, 33120477)

# Commerce-first AI scenes — category → grounded scene variant ids (Option A)
CATEGORY_COMMERCE_SCENES: dict[str, tuple[str, ...]] = {
    "apparel": ("ai_scene_table", "ai_scene_shelf", "ai_scene_retail"),
    "food": ("ai_scene_table", "ai_creative_marble", "ai_scene_shelf"),
    "beauty": ("ai_scene_table", "ai_creative_marble", "ai_scene_shelf"),
    "jewelry": ("ai_scene_table", "ai_creative_marble", "ai_scene_wall"),
    "electronics": ("ai_scene_table", "ai_scene_shelf", "ai_creative_podium"),
    "home": ("ai_scene_shelf", "ai_scene_wall", "ai_scene_table"),
    "general": ("ai_scene_table", "ai_scene_shelf", "ai_scene_retail"),
}
# Backward-compatible alias used by settings flag PHOTOROOM_CREATIVE_SCENES_ENABLED
CATEGORY_CREATIVE_VARIANTS = CATEGORY_COMMERCE_SCENES

COMMERCE_SCENE_VARIANT_IDS = frozenset({
    "ai_scene_table",
    "ai_scene_shelf",
    "ai_scene_wall",
    "ai_scene_retail",
})
SOFT_CREATIVE_VARIANT_IDS = frozenset({
    "ai_creative_marble",
    "ai_creative_botanical",
    "ai_creative_podium",
})
# Dramatic effects — kept in catalog for manual use, excluded from auto Snap packs
DEPRECATED_CREATIVE_VARIANT_IDS = frozenset({
    "ai_creative_splash",
    "ai_creative_neon",
    "ai_creative_powder",
})
CREATIVE_VARIANT_IDS = COMMERCE_SCENE_VARIANT_IDS | SOFT_CREATIVE_VARIANT_IDS | DEPRECATED_CREATIVE_VARIANT_IDS
AI_SCENE_VARIANT_IDS = frozenset({
    "ai_lifestyle",
    "ai_lifestyle_alt",
    "ai_contextual",
}) | COMMERCE_SCENE_VARIANT_IDS | SOFT_CREATIVE_VARIANT_IDS

# Per-scene product framing — avoids “same product, different background” look.
VARIANT_LAYOUT_STYLES: tuple[dict[str, str], ...] = (
    {
        "horizontalAlignment": "left",
        "verticalAlignment": "bottom",
        "paddingLeft": "0.06",
        "paddingRight": "0.24",
        "paddingTop": "0.20",
        "paddingBottom": "0.06",
    },
    {
        "horizontalAlignment": "center",
        "verticalAlignment": "center",
        "padding": "0.16",
    },
    {
        "horizontalAlignment": "right",
        "verticalAlignment": "top",
        "paddingLeft": "0.22",
        "paddingRight": "0.06",
        "paddingTop": "0.08",
        "paddingBottom": "0.18",
    },
    {
        "horizontalAlignment": "center",
        "verticalAlignment": "bottom",
        "paddingLeft": "0.10",
        "paddingRight": "0.10",
        "paddingTop": "0.22",
        "paddingBottom": "0.05",
    },
    {
        "horizontalAlignment": "left",
        "verticalAlignment": "center",
        "paddingLeft": "0.05",
        "paddingRight": "0.28",
        "paddingTop": "0.12",
        "paddingBottom": "0.12",
    },
)

PLAN_TIER_ORDER = ("starter", "growth", "pro", "agency")

# Phase C — carousel slide roles (variant pick order)
SLIDE_ROLE_PRODUCT = (
    ("hero", ("studio_white", "studio_brand")),
    ("desire", ("ai_lifestyle", "ai_lifestyle_alt", "ai_contextual")),
    ("proof", ()),  # filled per category below
    ("standout", ("studio_dark", "outline", "background_blur")),
)
SLIDE_ROLE_SERVICE = (
    ("hero", ("service_hero",)),
    ("context", ("service_context",)),
    ("trust", ("relight", "background_blur", "beautify")),
)
SLIDE_ROLE_DIGITAL = (
    ("hero", ("digital_desk_hero",)),
    ("mockup", ("digital_device_mockup",)),
    ("desire", ("ai_contextual", "ai_lifestyle", "ai_lifestyle_alt")),
)
CATEGORY_PROOF_VARIANTS: dict[str, tuple[str, ...]] = {
    "apparel": ("ghost_mannequin", "virtual_model"),
    "food": ("flat_lay", "text_removal"),
    "beauty": ("flat_lay", "beautify"),
    "jewelry": ("beautify", "studio_dark"),
    "electronics": ("relight", "background_blur"),
    "home": ("flat_lay", "ai_contextual"),
    "general": ("relight", "flat_lay", "background_blur"),
}
CAROUSEL_EXCLUDE_URL_MARKERS = ("channel_story", "channel_banner", "preflight_")
SHOP_GALLERY_EXCLUDE_MARKERS = CAROUSEL_EXCLUDE_URL_MARKERS + ("promo_frame",)

PRODUCT_CATEGORIES = (
    "apparel",
    "food",
    "beauty",
    "jewelry",
    "electronics",
    "home",
    "general",
)


@dataclass(frozen=True)
class PlusVariantSpec:
    id: str
    label: str
    params: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)
    categories: tuple[str, ...] = ()
    offering_types: tuple[str, ...] = ("product",)
    min_plan: str = "starter"
    priority: int = 50
    pack_eligible: bool = True  # False = preflight/channel only, not scene pack


def _export_defaults() -> dict[str, str]:
    out = {
        "referenceBox": "originalImage",
        "outputSize": str(getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")),
        "export.format": "jpeg",
    }
    scaling = str(getattr(settings, "PHOTOROOM_SCALING", "fit")).strip().lower()
    if scaling in ("fit", "fill"):
        out["scaling"] = scaling
    return out


def _shadow_studio() -> dict[str, str]:
    return {
        "removeBackground": "true",
        "padding": str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
        "shadow.mode": str(getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft")),
    }


def _ai_bg_headers() -> dict[str, str]:
    return {"pr-ai-background-model-version": AI_BG_MODEL_HEADER}


PLUS_VARIANT_CATALOG: dict[str, PlusVariantSpec] = {
    # ── Core studio (every product) ──────────────────────────────────────
    "studio_white": PlusVariantSpec(
        id="studio_white",
        label="White studio",
        params={
            **_shadow_studio(),
            "background.color": "FFFFFF",
            **_export_defaults(),
        },
        categories=(),
        priority=100,
    ),
    "studio_brand": PlusVariantSpec(
        id="studio_brand",
        label="Brand studio",
        params={
            **_shadow_studio(),
            "background.color": "{brand_color}",
            **_export_defaults(),
        },
        categories=(),
        priority=95,
    ),
    "studio_dark": PlusVariantSpec(
        id="studio_dark",
        label="Premium dark studio",
        params={
            **_shadow_studio(),
            "background.color": "1A1A2E",
            **_export_defaults(),
        },
        categories=("jewelry", "electronics", "general"),
        priority=70,
    ),
    # ── AI backgrounds ───────────────────────────────────────────────────
    "ai_lifestyle": PlusVariantSpec(
        id="ai_lifestyle",
        label="AI lifestyle scene",
        params={
            **_shadow_studio(),
            "background.prompt": "{lifestyle_prompt}",
            "background.seed": str(AI_BG_SEEDS[0]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        priority=98,
    ),
    "ai_lifestyle_alt": PlusVariantSpec(
        id="ai_lifestyle_alt",
        label="AI lifestyle (alt)",
        params={
            **_shadow_studio(),
            "background.prompt": "{lifestyle_prompt_alt}",
            "background.seed": str(AI_BG_SEEDS[1]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        priority=97,
    ),
    "ai_contextual": PlusVariantSpec(
        id="ai_contextual",
        label="AI contextual scene",
        params={
            **_shadow_studio(),
            "background.prompt": "{contextual_prompt}",
            "background.seed": str(AI_BG_SEEDS[2]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=96,
    ),
    # ── Commerce AI scenes (product-forward surfaces) ────────────────────
    "ai_scene_table": PlusVariantSpec(
        id="ai_scene_table",
        label="Table / counter",
        params={
            **_shadow_studio(),
            "background.prompt": "{commerce_table_prompt}",
            "background.seed": str(AI_BG_SEEDS[0]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=95,
    ),
    "ai_scene_shelf": PlusVariantSpec(
        id="ai_scene_shelf",
        label="Shelf display",
        params={
            **_shadow_studio(),
            "background.prompt": "{commerce_shelf_prompt}",
            "background.seed": str(AI_BG_SEEDS[1]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=94,
    ),
    "ai_scene_wall": PlusVariantSpec(
        id="ai_scene_wall",
        label="Wall / ledge",
        params={
            **_shadow_studio(),
            "background.prompt": "{commerce_wall_prompt}",
            "background.seed": str(AI_BG_SEEDS[2]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=93,
    ),
    "ai_scene_retail": PlusVariantSpec(
        id="ai_scene_retail",
        label="Retail display",
        params={
            **_shadow_studio(),
            "background.prompt": "{commerce_retail_prompt}",
            "background.seed": str(AI_BG_SEEDS[3]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=92,
    ),
    # ── Soft studio creatives (subtle surfaces — still commerce-safe) ───
    "ai_creative_splash": PlusVariantSpec(
        id="ai_creative_splash",
        label="Water splash hero",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_splash_prompt}",
            "background.seed": str(AI_BG_SEEDS[4]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("food", "beauty", "general"),
        min_plan="growth",
        priority=40,
        pack_eligible=False,
    ),
    "ai_creative_marble": PlusVariantSpec(
        id="ai_creative_marble",
        label="Luxury marble surface",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_marble_prompt}",
            "background.seed": str(AI_BG_SEEDS[0]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("beauty", "jewelry", "home", "food", "general"),
        min_plan="growth",
        priority=88,
    ),
    "ai_creative_botanical": PlusVariantSpec(
        id="ai_creative_botanical",
        label="Soft botanical",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_botanical_prompt}",
            "background.seed": str(AI_BG_SEEDS[1]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("beauty", "food", "home", "apparel"),
        min_plan="growth",
        priority=87,
    ),
    "ai_creative_neon": PlusVariantSpec(
        id="ai_creative_neon",
        label="Neon tech glow",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_neon_prompt}",
            "background.seed": str(AI_BG_SEEDS[2]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("electronics", "apparel", "general"),
        min_plan="growth",
        priority=35,
        pack_eligible=False,
    ),
    "ai_creative_powder": PlusVariantSpec(
        id="ai_creative_powder",
        label="Powder explosion",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_powder_prompt}",
            "background.seed": str(AI_BG_SEEDS[3]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("beauty", "food"),
        min_plan="pro",
        priority=34,
        pack_eligible=False,
    ),
    "ai_creative_podium": PlusVariantSpec(
        id="ai_creative_podium",
        label="Gradient podium",
        params={
            **_shadow_studio(),
            "background.prompt": "{creative_podium_prompt}",
            "background.seed": str(AI_BG_SEEDS[5]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("electronics", "general"),
        min_plan="growth",
        priority=86,
    ),
    # ── Enhancement ──────────────────────────────────────────────────────
    "photofix": PlusVariantSpec(
        id="photofix",
        label="PhotoFix",
        params={
            "removeBackground": "false",
            "beautify.mode": "{beautify_mode}",
            "beautify.seed": str(getattr(settings, "BEAUTIFY_SEED_DEFAULT", 117879368)),
            "lighting.mode": "ai.auto",
            **_export_defaults(),
        },
        categories=(),
        min_plan="starter",
        priority=90,
        pack_eligible=False,
    ),
    "smart_crop": PlusVariantSpec(
        id="smart_crop",
        label="Smart crop",
        params={
            "removeBackground": "false",
            "outputSize": str(getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")),
            "padding": str(getattr(settings, "PHOTOROOM_SMART_CROP_PADDING", "10%")),
            "segmentation.prompt": "product",
            "export.format": "jpeg",
            "referenceBox": "originalImage",
        },
        categories=(),
        min_plan="starter",
        priority=88,
        pack_eligible=False,
    ),
    "relight": PlusVariantSpec(
        id="relight",
        label="AI relight",
        params={
            "removeBackground": "true",
            "lighting.mode": "ai.auto",
            "background.color": "FFFFFF",
            "padding": str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=(),
        min_plan="growth",
        priority=75,
    ),
    "beautify": PlusVariantSpec(
        id="beautify",
        label="AI beautify",
        params={
            "removeBackground": "true",
            "beautify.mode": "{beautify_mode}",
            "beautify.seed": str(getattr(settings, "BEAUTIFY_SEED_DEFAULT", 117879368)),
            "background.color": "FFFFFF",
            "padding": "0.10",
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=("beauty", "jewelry", "general", "food"),
        min_plan="growth",
        priority=72,
    ),
    "background_blur": PlusVariantSpec(
        id="background_blur",
        label="Depth blur",
        params={
            "removeBackground": "false",
            "background.blur.mode": str(
                getattr(settings, "PHOTOROOM_DEFAULT_BLUR_MODE", "bokeh")
            ),
            "background.blur.radius": str(
                getattr(settings, "PHOTOROOM_DEFAULT_BLUR_RADIUS", 0.01)
            ),
            "referenceBox": "originalImage",
            "outputSize": str(getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")),
            "export.format": "jpeg",
        },
        categories=("general", "electronics", "home"),
        min_plan="growth",
        priority=65,
    ),
    "text_removal": PlusVariantSpec(
        id="text_removal",
        label="Clean labels",
        params={
            "removeBackground": "false",
            "textRemoval.mode": "ai.auto",
            "background.color": "FFFFFF",
            **_export_defaults(),
        },
        categories=("food", "beauty", "general"),
        min_plan="pro",
        priority=60,
    ),
    "outline": PlusVariantSpec(
        id="outline",
        label="Product outline",
        params={
            "removeBackground": "true",
            "background.color": "FFFFFF",
            "outline.color": "000000",
            "outline.width": "3",
            "padding": "0.14",
            **_export_defaults(),
        },
        categories=("general", "electronics"),
        min_plan="pro",
        priority=55,
    ),
    # ── Category-specific generation ─────────────────────────────────────
    "flat_lay": PlusVariantSpec(
        id="flat_lay",
        label="Flat lay",
        params={
            "flatLay.mode": "ai.auto",
            "flatLay.prompt": "{flat_lay_prompt}",
            "flatLay.size": "SQUARE_HD",
            **_export_defaults(),
        },
        categories=("food", "beauty", "home", "general"),
        priority=88,
    ),
    "ghost_mannequin": PlusVariantSpec(
        id="ghost_mannequin",
        label="Ghost mannequin",
        params={
            "ghostMannequin.mode": "ai.auto",
            "ghostMannequin.prompt": "{apparel_prompt}",
            "ghostMannequin.size": "SQUARE_HD",
            **_export_defaults(),
        },
        categories=("apparel",),
        priority=92,
    ),
    "virtual_model": PlusVariantSpec(
        id="virtual_model",
        label="Virtual model",
        params={
            "removeBackground": "false",
            "referenceBox": "originalImage",
            "virtualModel.mode": "ai.auto",
            "virtualModel.model.preset.name": "avery",
            "virtualModel.scene.preset.name": "street",
            "virtualModel.pose": "standing",
            "virtualModel.size": "SQUARE_HD",
            **_export_defaults(),
        },
        categories=("apparel",),
        min_plan="growth",
        priority=86,
    ),
    # ── Resize / expand (Pro+) ───────────────────────────────────────────
    "upscale": PlusVariantSpec(
        id="upscale",
        label="AI upscale",
        params={
            "removeBackground": "true",
            "background.color": "FFFFFF",
            "upscale.mode": "ai.auto",
            "upscale.downscaleIfNeeded": "true",
            "padding": "0.12",
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=(),
        min_plan="pro",
        priority=50,
    ),
    "expand": PlusVariantSpec(
        id="expand",
        label="AI expand",
        params={
            "removeBackground": "true",
            "expand.mode": "ai.auto",
            "background.color": "FFFFFF",
            "padding": "0.08",
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=(),
        min_plan="pro",
        priority=48,
    ),
    "uncrop": PlusVariantSpec(
        id="uncrop",
        label="AI uncrop",
        params={
            "removeBackground": "true",
            "uncrop.mode": "ai.auto",
            "background.color": "FFFFFF",
            "padding": "0.10",
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=(),
        min_plan="agency",
        priority=45,
    ),
    "ai_touchup": PlusVariantSpec(
        id="ai_touchup",
        label="AI touch-up",
        params={
            "removeBackground": "false",
            "referenceBox": "originalImage",
            "editWithAI.mode": "ai.auto",
            "editWithAI.prompt": "{touchup_prompt}",
            "editWithAI.seed": str(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668)),
            **_export_defaults(),
        },
        categories=(),
        min_plan="agency",
        priority=42,
    ),
    # ── Service (work evidence, no physical product) ───────────────────────
    "service_hero": PlusVariantSpec(
        id="service_hero",
        label="Service hero",
        params={
            **_shadow_studio(),
            "background.prompt": "{service_prompt}",
            "background.seed": str(AI_BG_SEEDS[3]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        offering_types=("service",),
        priority=100,
    ),
    "service_context": PlusVariantSpec(
        id="service_context",
        label="Service context",
        params={
            **_shadow_studio(),
            "background.prompt": "{service_context_prompt}",
            "background.seed": str(AI_BG_SEEDS[0]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        offering_types=("service",),
        min_plan="growth",
        priority=90,
    ),
    # ── Digital (screenshots, SaaS, templates) ───────────────────────────
    "digital_desk_hero": PlusVariantSpec(
        id="digital_desk_hero",
        label="Clean desk hero",
        params={
            **_shadow_studio(),
            "background.prompt": "{digital_desk_prompt}",
            "background.seed": str(AI_BG_SEEDS[1]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        offering_types=("digital",),
        priority=100,
    ),
    "digital_device_mockup": PlusVariantSpec(
        id="digital_device_mockup",
        label="Device mockup",
        params={
            **_shadow_studio(),
            "background.prompt": "{digital_device_prompt}",
            "background.seed": str(AI_BG_SEEDS[2]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        offering_types=("digital",),
        min_plan="growth",
        priority=95,
    ),
    # ── Channel exports (Phase B — not scene pack) ───────────────────────
    "channel_story": PlusVariantSpec(
        id="channel_story",
        label="Story / Reel (9:16)",
        params={
            **_shadow_studio(),
            "expand.mode": "ai.auto",
            "outputSize": "{story_output_size}",
            "export.format": "jpeg",
            "referenceBox": "originalImage",
        },
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=30,
        pack_eligible=False,
    ),
    "channel_story_uncrop": PlusVariantSpec(
        id="channel_story_uncrop",
        label="Story / Reel uncrop (9:16)",
        params={
            **_shadow_studio(),
            "uncrop.mode": "ai.auto",
            "outputSize": "{story_output_size}",
            "export.format": "jpeg",
            "referenceBox": "originalImage",
        },
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=29,
        pack_eligible=False,
    ),
    "channel_banner": PlusVariantSpec(
        id="channel_banner",
        label="Banner (16:9)",
        params={
            **_shadow_studio(),
            "expand.mode": "ai.auto",
            "outputSize": "{banner_output_size}",
            "export.format": "jpeg",
            "referenceBox": "originalImage",
        },
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=28,
        pack_eligible=False,
    ),
}


def _plan_rank(tier: str) -> int:
    try:
        return PLAN_TIER_ORDER.index(tier)
    except ValueError:
        return 0


def _product_blob(product, analysis: dict | None) -> str:
    analysis = analysis or {}
    parts = [
        product.name or "",
        " ".join(product.tags or []),
        " ".join(analysis.get("suggested_tags") or []),
        " ".join(analysis.get("key_features") or []),
        analysis.get("visual_style") or "",
        analysis.get("campaign_angle") or "",
        analysis.get("description") or "",
        analysis.get("product_category") or "",
    ]
    return " ".join(parts).lower()


def detect_product_category(product, analysis: dict | None = None) -> str:
    blob = _product_blob(product, analysis)
    rules = (
        ("apparel", ("shirt", "dress", "shoe", "sneaker", "fashion", "wear", "cloth", "garment", "bag", "handbag", "jacket", "kitenge")),
        ("food", ("food", "snack", "spice", "coffee", "tea", "cake", "bread", "honey", "sauce", "drink", "juice", "meal")),
        ("beauty", ("beauty", "skin", "lotion", "cream", "cosmetic", "perfume", "serum", "hair", "makeup", "skincare")),
        ("jewelry", ("jewel", "ring", "necklace", "watch", "gold", "silver", "bracelet", "earring")),
        ("electronics", ("phone", "laptop", "electronic", "gadget", "charger", "cable", "speaker", "headphone", "tech")),
        ("home", ("home", "decor", "furniture", "candle", "kitchen", "vase", "pillow", "linen")),
    )
    for category, keywords in rules:
        if any(k in blob for k in keywords):
            return category
    return "general"


def _clean_name(product) -> str:
    from apps.products.commerce_autopilot import sanitize_product_name

    return sanitize_product_name(product.name) or "the product"


_COMMERCE_VISIBILITY_RULES = (
    "The product must be the clear hero — fully visible, sharp, and unobstructed, "
    "occupying at least half the frame. Use a simple realistic surface or setting with "
    "soft natural or studio light. No water splash, liquid, powder burst, neon glow, "
    "smoke, or particles covering the product. No text, logos, or extra products."
)


def _commerce_prompt(base: str) -> str:
    return f"{base.rstrip('.')}. {_COMMERCE_VISIBILITY_RULES}"


def build_commerce_scene_prompt(scene: str, product, analysis: dict | None) -> str:
    """Grounded e-commerce scenes — table, shelf, wall, retail display."""
    name = _clean_name(product)
    category = detect_product_category(product, analysis)
    analysis = analysis or {}
    angle = analysis.get("campaign_angle") or analysis.get("visual_style") or ""
    mood = f" Mood: {angle}." if angle else ""

    table_by_category = {
        "apparel": (
            f"{name} placed on a clean wooden table or light concrete surface, "
            f"angled product shot with soft daylight from the side, minimal props, "
            f"footwear and fashion e-commerce style"
        ),
        "food": (
            f"{name} on a rustic wooden table or clean kitchen counter, warm natural "
            f"daylight, simple complementary ingredients kept small and out of the way"
        ),
        "beauty": (
            f"{name} on a white vanity tray or marble bathroom counter, soft diffused "
            f"light, minimal spa props, premium skincare product photography"
        ),
        "jewelry": (
            f"{name} on a neutral stone or velvet display pad on a table, elegant soft "
            f"studio lighting, luxury boutique product shot"
        ),
        "electronics": (
            f"{name} on a modern desk or light oak table, minimal workspace props pushed "
            f"to the background, crisp professional tech product photography"
        ),
        "home": (
            f"{name} on a styled side table or kitchen counter, cozy interior daylight, "
            f"home decor e-commerce styling"
        ),
        "general": (
            f"{name} on a clean neutral table surface, balanced soft studio lighting, "
            f"simple uncluttered product photography"
        ),
    }
    shelf_by_category = {
        "apparel": (
            f"{name} displayed on a minimal retail shelf or wall-mounted ledge, "
            f"clean boutique interior, product facing camera clearly"
        ),
        "food": (
            f"{name} on a grocery or pantry shelf with soft depth of field, label readable, "
            f"clean market styling"
        ),
        "beauty": (
            f"{name} on a bright bathroom or boutique shelf, organized minimal layout, "
            f"soft flattering light"
        ),
        "jewelry": (
            f"{name} on a glass or wooden display shelf, subtle reflections, luxury retail"
        ),
        "electronics": (
            f"{name} on a clean tech store shelf or minimalist wall unit, modern retail display"
        ),
        "home": (
            f"{name} on a styled floating shelf in a bright Scandinavian room, lifestyle home retail"
        ),
        "general": (
            f"{name} on a simple wall shelf or retail ledge, neutral background, product clearly visible"
        ),
    }
    wall_by_category = {
        "apparel": (
            f"{name} mounted or placed on a wall hook or peg rail in a clean closet-boutique "
            f"setting, front-facing product visibility"
        ),
        "jewelry": (
            f"{name} on a wall-mounted jewelry display or neutral ledge, soft spotlight, "
            f"elegant minimal backdrop"
        ),
        "home": (
            f"{name} on a wall-mounted ledge or picture shelf in a modern living room, "
            f"natural window light"
        ),
        "general": (
            f"{name} on a wall ledge or minimal wall-mounted display, clean neutral wall, "
            f"product centered and fully visible"
        ),
    }
    retail_by_category = {
        "apparel": (
            f"{name} on a clean shoe-store display table or boutique counter, organized retail "
            f"presentation, bright even lighting"
        ),
        "electronics": (
            f"{name} on a tech retail counter with minimal signage area left blank, "
            f"premium launch display aesthetic"
        ),
        "general": (
            f"{name} on a shop counter or retail display table, professional store presentation, "
            f"product as the focal point"
        ),
    }

    prompts = {
        "ai_scene_table": table_by_category.get(category, table_by_category["general"]),
        "ai_scene_shelf": shelf_by_category.get(category, shelf_by_category["general"]),
        "ai_scene_wall": wall_by_category.get(category, wall_by_category.get("general", table_by_category["general"])),
        "ai_scene_retail": retail_by_category.get(category, retail_by_category["general"]),
    }
    base = prompts.get(scene, table_by_category["general"])
    return _commerce_prompt(f"{base}.{mood}")


def build_lifestyle_prompt(product, analysis: dict | None, *, variant: str = "primary") -> str:
    name = _clean_name(product)
    category = detect_product_category(product, analysis)
    analysis = analysis or {}
    angle = analysis.get("campaign_angle") or analysis.get("visual_style") or "professional marketing"
    templates = {
        "apparel": {
            "primary": (
                f"A professional product photo of {name} on a clean wooden table or neutral "
                f"floor surface with soft natural lighting and minimal props"
            ),
            "alt": (
                f"{name} displayed on a boutique shelf or retail table with warm even light "
                f"and a polished e-commerce look"
            ),
        },
        "food": {
            "primary": (
                f"A appetizing product photo of {name} on a rustic wooden table with natural "
                f"ingredients nearby, warm daylight, and a clean food photography style."
            ),
            "alt": (
                f"{name} presented on a marble counter in a bright modern kitchen, "
                f"soft shadows, fresh and inviting atmosphere."
            ),
        },
        "beauty": {
            "primary": (
                f"A luxury beauty product photo of {name} on a soft spa-inspired surface "
                f"with gentle pastel tones, clean minimal props, and flattering soft light."
            ),
            "alt": (
                f"{name} on a vanity tray with botanical accents, dewy fresh aesthetic, "
                f"premium skincare campaign style."
            ),
        },
        "jewelry": {
            "primary": (
                f"An elegant product photo of {name} on a dark velvet surface with "
                f"dramatic studio lighting, subtle reflections, and luxury jewelry styling."
            ),
            "alt": (
                f"{name} displayed on a soft neutral stone surface with warm ambient light "
                f"and a high-end boutique feel."
            ),
        },
        "electronics": {
            "primary": (
                f"A sleek tech product photo of {name} on a modern desk setup with "
                f"minimal props, cool neutral tones, and crisp professional lighting."
            ),
            "alt": (
                f"{name} in a contemporary workspace scene with clean lines, soft shadows, "
                f"and a premium gadget launch aesthetic."
            ),
        },
        "home": {
            "primary": (
                f"A styled home product photo of {name} in a cozy modern interior with "
                f"natural window light, warm textures, and lifestyle home decor styling."
            ),
            "alt": (
                f"{name} on a styled shelf in a bright Scandinavian-inspired room, "
                f"soft neutral palette, inviting atmosphere."
            ),
        },
        "general": {
            "primary": (
                f"A professional product photo of {name} in a clean lifestyle setting "
                f"with balanced natural light, subtle background blur, and e-commerce quality."
            ),
            "alt": (
                f"{name} in a premium retail display scene with soft studio lighting "
                f"and a polished marketing campaign look."
            ),
        },
    }
    bucket = templates.get(category, templates["general"])
    key = "alt" if variant.endswith("alt") else "primary"
    base = bucket[key]
    if angle and angle != "professional marketing":
        base = f"{base}. {angle}"
    return _commerce_prompt(base)


def build_creative_prompt(style: str, product, analysis: dict | None) -> str:
    """Soft studio surfaces — marble, botanical, podium (commerce-safe)."""
    name = _clean_name(product)
    analysis = analysis or {}
    angle = analysis.get("campaign_angle") or analysis.get("visual_style") or ""
    angle_clause = f" Campaign mood: {angle}." if angle else ""

    prompts = {
        "ai_creative_splash": (
            f"Dynamic high-speed water splash photography behind {name}: crystal-clear "
            f"water droplets, fresh splash motion, crisp studio strobe lighting, refreshing "
            f"premium beverage or skincare hero shot, clean background blur, no text.{angle_clause}"
        ),
        "ai_creative_marble": (
            f"{name} resting on a clean white and soft gold marble counter surface, subtle "
            f"reflection beneath the product, premium boutique advertising, soft diffused light, "
            f"minimal props, no text.{angle_clause}"
        ),
        "ai_creative_botanical": (
            f"{name} on a neutral surface with soft blurred greenery in the far background only, "
            f"fresh natural daylight, organic calm atmosphere, product stays sharp and dominant, "
            f"no text.{angle_clause}"
        ),
        "ai_creative_neon": (
            f"Bold cyberpunk neon gradient backdrop with magenta, cyan, and deep purple glow, "
            f"futuristic tech product showcase for {name}, dramatic rim light, social media "
            f"scroll-stopping aesthetic, no text or UI.{angle_clause}"
        ),
        "ai_creative_powder": (
            f"Dramatic cosmetic powder explosion with soft colorful particles frozen mid-air "
            f"behind {name}, high-fashion beauty campaign studio lighting, vibrant yet "
            f"premium, clean product focus, no text.{angle_clause}"
        ),
        "ai_creative_podium": (
            f"{name} on a minimal geometric product podium with a soft pastel gradient studio "
            f"backdrop, subtle floor reflection, modern launch presentation, clean Apple-style "
            f"reveal aesthetic, no text.{angle_clause}"
        ),
    }
    raw = prompts.get(
        style,
        f"A clean marketing background for {name}, premium social commerce hero shot.{angle_clause}",
    )
    if style in DEPRECATED_CREATIVE_VARIANT_IDS:
        return raw
    return _commerce_prompt(raw)


def build_contextual_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    analysis = analysis or {}
    audience = analysis.get("target_audience") or "customers"
    features = ", ".join((analysis.get("key_features") or [])[:3])
    feature_clause = f" Highlight: {features}." if features else ""
    return _commerce_prompt(
        f"Create a photorealistic marketing scene featuring {name} designed to appeal to {audience}. "
        f"The setting should feel authentic, aspirational, and ready for social commerce.{feature_clause}"
    )


def build_flat_lay_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    category = detect_product_category(product, analysis)
    if category == "food":
        return f"Top-down flat lay of {name} with complementary ingredients and clean food styling on a neutral surface."
    if category == "beauty":
        return f"Top-down flat lay of {name} with minimal spa accessories on a soft pastel surface."
    return f"Top-down flat lay of {name} with tasteful minimal props on a clean studio surface."


def build_apparel_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    return (
        f"Professional apparel presentation of {name}, clean studio styling, "
        f"natural fit, premium fashion e-commerce quality."
    )


def build_touchup_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    return (
        f"Enhance this product photo of {name} for premium e-commerce: improve clarity, "
        f"color balance, and lighting while keeping the product accurate and unchanged."
    )


def build_service_prompt(product, analysis: dict | None, *, context: bool = False) -> str:
    name = _clean_name(product)
    analysis = analysis or {}
    hook = analysis.get("credibility_hook") or analysis.get("campaign_angle") or "trusted professional service"
    if context:
        return (
            f"A professional marketing scene representing {name}: {hook}. "
            f"People or workspace context allowed, warm trustworthy atmosphere, no text overlays."
        )
    return (
        f"A clean hero image representing {name} service offering: {hook}. "
        f"Professional, modern, trustworthy visual for social media marketing."
    )


def build_digital_desk_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    analysis = analysis or {}
    hook = analysis.get("campaign_angle") or analysis.get("value_proposition") or "premium digital product"
    return (
        f"A clean minimal desk setup hero shot showcasing {name} on a laptop screen: {hook}. "
        f"Modern workspace, soft natural light, uncluttered surface, no text overlays, marketing ready."
    )


def build_digital_device_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    analysis = analysis or {}
    hook = analysis.get("campaign_angle") or "professional digital offering"
    return (
        f"A floating device mockup (laptop and smartphone at a dynamic angle) displaying {name}: {hook}. "
        f"Sleek tech aesthetic, subtle gradient background, premium SaaS launch visual, no UI text."
    )


def resolve_variant_params(
    spec: PlusVariantSpec,
    product,
    analysis: dict | None,
    brand_colors: dict | None,
    brand_template=None,
) -> dict[str, str]:
    from apps.products.photoroom import pick_background_color_hex
    from apps.products.photoroom_brand_template import apply_brand_template

    brand_colors = brand_colors or {}
    resolved: dict[str, str] = {}
    for key, value in spec.params.items():
        if value == "{brand_color}":
            resolved[key] = pick_background_color_hex(product, brand_colors)
        elif value == "{lifestyle_prompt}":
            resolved[key] = build_lifestyle_prompt(product, analysis, variant="primary")
        elif value == "{lifestyle_prompt_alt}":
            resolved[key] = build_lifestyle_prompt(product, analysis, variant="alt")
        elif value == "{creative_splash_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_splash", product, analysis)
        elif value == "{creative_marble_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_marble", product, analysis)
        elif value == "{creative_botanical_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_botanical", product, analysis)
        elif value == "{creative_neon_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_neon", product, analysis)
        elif value == "{creative_powder_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_powder", product, analysis)
        elif value == "{creative_podium_prompt}":
            resolved[key] = build_creative_prompt("ai_creative_podium", product, analysis)
        elif value == "{commerce_table_prompt}":
            resolved[key] = build_commerce_scene_prompt("ai_scene_table", product, analysis)
        elif value == "{commerce_shelf_prompt}":
            resolved[key] = build_commerce_scene_prompt("ai_scene_shelf", product, analysis)
        elif value == "{commerce_wall_prompt}":
            resolved[key] = build_commerce_scene_prompt("ai_scene_wall", product, analysis)
        elif value == "{commerce_retail_prompt}":
            resolved[key] = build_commerce_scene_prompt("ai_scene_retail", product, analysis)
        elif value == "{contextual_prompt}":
            resolved[key] = build_contextual_prompt(product, analysis)
        elif value == "{flat_lay_prompt}":
            resolved[key] = build_flat_lay_prompt(product, analysis)
        elif value == "{apparel_prompt}":
            resolved[key] = build_apparel_prompt(product, analysis)
        elif value == "{service_prompt}":
            resolved[key] = build_service_prompt(product, analysis, context=False)
        elif value == "{service_context_prompt}":
            resolved[key] = build_service_prompt(product, analysis, context=True)
        elif value == "{digital_desk_prompt}":
            resolved[key] = build_digital_desk_prompt(product, analysis)
        elif value == "{digital_device_prompt}":
            resolved[key] = build_digital_device_prompt(product, analysis)
        elif value == "{story_output_size}":
            resolved[key] = str(getattr(settings, "PHOTOROOM_STORY_SIZE", "1080x1920"))
        elif value == "{banner_output_size}":
            resolved[key] = str(getattr(settings, "PHOTOROOM_BANNER_SIZE", "1920x1080"))
        elif value == "{touchup_prompt}":
            resolved[key] = build_touchup_prompt(product, analysis)
        elif value == "{beautify_mode}":
            from apps.products.photoroom_api import beautify_mode_for_category

            category = detect_product_category(product, analysis)
            resolved[key] = beautify_mode_for_category(category)
        else:
            resolved[key] = value
    return apply_brand_template(resolved, brand_template, spec)


def _slide_roles_for(offering: str, category: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if offering == "service":
        return SLIDE_ROLE_SERVICE
    if offering == "digital":
        return SLIDE_ROLE_DIGITAL
    proof_ids = CATEGORY_PROOF_VARIANTS.get(category, CATEGORY_PROOF_VARIANTS["general"])
    commerce_ids: tuple[str, ...] = ()
    if getattr(settings, "PHOTOROOM_CREATIVE_SCENES_ENABLED", True):
        commerce_ids = CATEGORY_COMMERCE_SCENES.get(
            category, CATEGORY_COMMERCE_SCENES["general"]
        )
    # Lifestyle scenes first, then grounded commerce surfaces
    desire_ids = (
        "ai_lifestyle",
        "ai_lifestyle_alt",
        "ai_contextual",
    ) + commerce_ids
    roles: list[tuple[str, tuple[str, ...]]] = []
    for role_name, variant_ids in SLIDE_ROLE_PRODUCT:
        if role_name == "proof":
            roles.append((role_name, proof_ids))
        elif role_name == "desire":
            roles.append((role_name, desire_ids))
        else:
            roles.append((role_name, variant_ids))
    return tuple(roles)


def slide_role_for_variant(variant_id: str, offering: str, category: str) -> str:
    """Carousel role label for a variant id."""
    if variant_id in COMMERCE_SCENE_VARIANT_IDS:
        return "commerce"
    if variant_id in SOFT_CREATIVE_VARIANT_IDS | DEPRECATED_CREATIVE_VARIANT_IDS:
        return "creative"
    for role_name, variant_ids in _slide_roles_for(offering, category):
        if variant_id in variant_ids:
            return role_name
    return "extra"


def filter_carousel_urls(urls: list[str]) -> list[str]:
    """Square carousel slides — exclude channel exports and preflight intermediates."""
    return [
        u for u in urls
        if u and not any(marker in u for marker in CAROUSEL_EXCLUDE_URL_MARKERS)
    ]


def filter_shop_gallery_urls(urls: list[str]) -> list[str]:
    """Buyer-facing shop galleries — product photos only, no promo/text slides."""
    return [
        u for u in urls
        if u and not any(marker in u for marker in SHOP_GALLERY_EXCLUDE_MARKERS)
    ]


def apply_variant_layout(
    params: dict[str, str],
    variant_id: str,
    layout_index: int,
) -> dict[str, str]:
    """Shift product position/size per AI scene so slides feel distinct."""
    if not getattr(settings, "PHOTOROOM_VARIANT_LAYOUTS_ENABLED", True):
        return params
    if variant_id not in AI_SCENE_VARIANT_IDS:
        return params

    style = VARIANT_LAYOUT_STYLES[layout_index % len(VARIANT_LAYOUT_STYLES)]
    out = dict(params)
    out.pop("padding", None)
    out.update(style)
    return out


def _target_ai_scene_count(max_count: int) -> int:
    """How many AI background scenes to generate when budget allows."""
    min_ai = int(getattr(settings, "PHOTOROOM_MIN_AI_SCENES", 2))
    max_ai = int(getattr(settings, "PHOTOROOM_MAX_AI_SCENES", 3))
    if max_count <= 1:
        return 0
    available = max_count - 1  # reserve hero
    if max_count >= 5:
        target = max_ai
    elif max_count >= 3:
        target = min_ai
    else:
        target = 1
    return min(target, available, max_ai)


def order_variants_by_slide_role(
    candidates: list[PlusVariantSpec],
    *,
    offering: str,
    category: str,
    max_count: int,
    uncertainty_score: float | None = None,
) -> list[PlusVariantSpec]:
    """Pick variants to fill hero → desire (2–3 AI) → proof → standout."""
    from apps.products.photoroom_api import (
        HIGH_UNCERTAINTY_VARIANT_IDS,
        uncertainty_is_high,
    )

    by_id = {s.id: s for s in candidates}
    picked: list[PlusVariantSpec] = []
    picked_ids: set[str] = set()
    ai_target = _target_ai_scene_count(max_count)
    skip_risky = uncertainty_is_high(uncertainty_score)

    for role_name, preferred_ids in _slide_roles_for(offering, category):
        if role_name == "desire":
            picked_desire = 0
            for vid in preferred_ids:
                if len(picked) >= max_count or picked_desire >= ai_target:
                    break
                spec = by_id.get(vid)
                if spec and vid not in picked_ids:
                    picked.append(spec)
                    picked_ids.add(vid)
                    picked_desire += 1
            continue

        for vid in preferred_ids:
            if skip_risky and vid in HIGH_UNCERTAINTY_VARIANT_IDS:
                continue
            spec = by_id.get(vid)
            if spec and vid not in picked_ids:
                picked.append(spec)
                picked_ids.add(vid)
                break
        if len(picked) >= max_count:
            break

    if len(picked) < max_count:
        for spec in sorted(candidates, key=lambda s: -s.priority):
            if spec.id in picked_ids:
                continue
            if skip_risky and spec.id in HIGH_UNCERTAINTY_VARIANT_IDS:
                continue
            picked.append(spec)
            picked_ids.add(spec.id)
            if len(picked) >= max_count:
                break

    return picked[: max(1, max_count)]


def select_plus_variants(
    product,
    analysis: dict | None,
    *,
    plan_tier: str = "starter",
    max_count: int = 5,
    uncertainty_score: float | None = None,
) -> list[PlusVariantSpec]:
    """Pick applicable Plus variants for this product, highest priority first."""
    from apps.products.photoroom_api import (
        HIGH_UNCERTAINTY_VARIANT_IDS,
        uncertainty_is_high,
    )

    offering = getattr(product, "offering_type", "product") or "product"
    category = detect_product_category(product, analysis)
    plan_rank = _plan_rank(plan_tier)
    skip_risky = uncertainty_is_high(uncertainty_score)

    candidates: list[PlusVariantSpec] = []
    for spec in PLUS_VARIANT_CATALOG.values():
        if not spec.pack_eligible:
            continue
        if offering not in spec.offering_types:
            continue
        if _plan_rank(spec.min_plan) > plan_rank:
            continue
        if spec.categories and category not in spec.categories:
            continue
        candidates.append(spec)

    # Always include universal studio + lifestyle for physical products
    if offering == "product":
        for required_id in ("studio_white", "ai_lifestyle"):
            req = PLUS_VARIANT_CATALOG.get(required_id)
            if req and req not in candidates:
                candidates.append(req)
    elif offering == "service":
        for required_id in ("service_hero", "service_context"):
            req = PLUS_VARIANT_CATALOG.get(required_id)
            if req and req not in candidates:
                candidates.append(req)
    elif offering == "digital":
        for required_id in ("digital_desk_hero", "digital_device_mockup"):
            req = PLUS_VARIANT_CATALOG.get(required_id)
            if req and req not in candidates:
                candidates.append(req)

    # Category boosters (skip cutout-sensitive AI when uncertainty is high)
    if category == "apparel" and not skip_risky:
        for vid in ("ghost_mannequin", "virtual_model"):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)
    elif category in ("food", "beauty") and not skip_risky:
        spec = PLUS_VARIANT_CATALOG.get("flat_lay")
        if spec and spec not in candidates:
            candidates.append(spec)
    if skip_risky:
        relight = PLUS_VARIANT_CATALOG.get("relight")
        if relight and relight not in candidates:
            candidates.append(relight)

    if (
        offering == "product"
        and getattr(settings, "PHOTOROOM_CREATIVE_SCENES_ENABLED", True)
    ):
        for vid in CATEGORY_COMMERCE_SCENES.get(category, CATEGORY_COMMERCE_SCENES["general"]):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)

    seen: set[str] = set()
    ordered: list[PlusVariantSpec] = []
    for spec in sorted(candidates, key=lambda s: -s.priority):
        if spec.id in seen:
            continue
        seen.add(spec.id)
        ordered.append(spec)

    if skip_risky:
        ordered = [s for s in ordered if s.id not in HIGH_UNCERTAINTY_VARIANT_IDS]

    if getattr(settings, "PHOTOROOM_SLIDE_ROLES_ENABLED", True):
        return order_variants_by_slide_role(
            ordered,
            offering=offering,
            category=category,
            max_count=max_count,
            uncertainty_score=uncertainty_score,
        )
    return ordered[: max(1, max_count)]


def get_max_variants_for_plan(plan_tier: str) -> int:
    from apps.billing.models import PLAN_LIMITS

    limits = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["starter"])
    return int(limits.get("plus_max_variants_per_product", 3))


def _api_key_headers(extra: dict | None = None) -> tuple[str | None, dict]:
    from apps.products.photoroom import _api_key_headers as base_headers

    api_key, headers = base_headers()
    if extra:
        headers = {**headers, **extra}
    return api_key, headers


def _resolve_public_image_url(image_url: str) -> str | None:
    from apps.products.photoroom import _resolve_public_image_url as resolve

    return resolve(image_url)


def _load_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    from apps.products.photoroom import _load_image_bytes as load

    return load(image_url)


def photoroom_edit(
    image_url: str,
    params: dict[str, str],
    *,
    extra_headers: dict | None = None,
    file_bytes: bytes | None = None,
    file_name: str = "image.jpg",
) -> "PhotoroomEditResult":
    """Call Photoroom Plus v2/edit; returns bytes and x-uncertainty-score when present."""
    from apps.products.photoroom_api import (
        PhotoroomEditResult,
        check_sandbox_quota,
        parse_uncertainty_score,
        record_sandbox_call,
    )

    api_key, headers = _api_key_headers(extra_headers)
    if not api_key:
        logger.info("Photoroom edit skipped: PHOTOROOM_API_KEY not set")
        return PhotoroomEditResult(content=None, error="not_configured")

    allowed, limit_msg = check_sandbox_quota()
    if not allowed:
        logger.warning("Photoroom sandbox limit: %s", limit_msg)
        return PhotoroomEditResult(content=None, sandbox_limited=True, error=limit_msg)

    def _finish(resp: requests.Response) -> PhotoroomEditResult:
        record_sandbox_call()
        uncertainty = parse_uncertainty_score(resp.headers)
        content = resp.content or None
        if uncertainty is not None:
            logger.debug(
                "Photoroom uncertainty=%.3f keys=%s",
                uncertainty,
                list(params.keys())[:5],
            )
        return PhotoroomEditResult(content=content, uncertainty_score=uncertainty)

    if file_bytes:
        try:
            resp = requests.post(
                PHOTOROOM_EDIT_URL,
                headers=headers,
                files={"imageFile": (file_name, file_bytes, "image/jpeg")},
                data=params,
                timeout=180,
            )
            resp.raise_for_status()
            return _finish(resp)
        except Exception as exc:
            logger.error("Photoroom POST v2/edit (bytes) failed [%s]: %s", list(params.keys())[:4], exc)
            return PhotoroomEditResult(content=None, error=str(exc))

    public_url = _resolve_public_image_url(image_url)
    if public_url:
        try:
            resp = requests.get(
                PHOTOROOM_EDIT_URL,
                headers=headers,
                params={"imageUrl": public_url, **params},
                timeout=180,
            )
            resp.raise_for_status()
            if resp.content:
                return _finish(resp)
        except Exception as exc:
            logger.warning(
                "Photoroom GET v2/edit failed (%s), trying POST: %s",
                params.get("background.prompt", "studio")[:40],
                exc,
            )

    loaded = _load_image_bytes(image_url)
    if not loaded:
        return PhotoroomEditResult(content=None, error="load_failed")
    file_bytes, filename = loaded

    try:
        resp = requests.post(
            PHOTOROOM_EDIT_URL,
            headers=headers,
            files={"imageFile": (filename, file_bytes, "image/jpeg")},
            data=params,
            timeout=180,
        )
        resp.raise_for_status()
        return _finish(resp)
    except Exception as exc:
        logger.error("Photoroom POST v2/edit failed [%s]: %s", list(params.keys())[:4], exc)
        return PhotoroomEditResult(content=None, error=str(exc))


def run_plus_variant(
    image_url: str,
    spec: PlusVariantSpec,
    product,
    analysis: dict | None,
    brand_colors: dict | None,
    brand_template=None,
    *,
    layout_index: int = 0,
) -> "PhotoroomEditResult":
    from apps.products.photoroom_api import PhotoroomEditResult

    params = resolve_variant_params(
        spec, product, analysis, brand_colors, brand_template=brand_template
    )
    params = apply_variant_layout(params, spec.id, layout_index)
    return photoroom_edit(image_url, params, extra_headers=spec.headers)


def catalog_labels() -> list[str]:
    return [spec.label for spec in PLUS_VARIANT_CATALOG.values()]
