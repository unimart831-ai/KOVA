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
AI_SHADOWS_MODEL_HEADER = "2026-04-15"
AI_BG_SEEDS = (117879368, 55994449, 48672244, 65080068, 88210391, 33120477)

# Photoroom Edit With AI — official prompt templates (docs.photoroom.com)
EDIT_WITH_AI_PRODUCT_STAGING_BASE = (
    "Make it a professional lifestyle photoshoot with the provided object or subject as the "
    "focus of the scene. Ensure the image highlights what is unique about the object, with the "
    "goal of advertising it and showing how it impacts everyday life. The lighting should be "
    "perfectly set to create a natural and elegant atmosphere. The image should feature excellent "
    "composition and a refined mood, achieving the look of high-end lifestyle photography. "
    "Integrate a human presence or a subtle interaction with the object to enhance authenticity "
    "and visual appeal."
)
EDIT_WITH_AI_OTHER_ANGLE_BASE = (
    "Create a new photograph of this exact same scene or setting with creative variations. "
    "Change the camera angle and viewpoint (e.g., frontal to 3/4 view or side view, high to low "
    "angle, wide to tight), adjust composition and framing, and optionally vary the lighting or "
    "time of day (morning, golden hour, blue hour, overcast, or dramatic shadows). Try creative "
    "approaches such as closer details, wider establishing shots, or alternative focal points. "
    "Keep the exact same physical location and environment so it remains clearly recognizable, "
    "with the same main subjects, key elements, style, and overall mood. If there's a person, "
    "change their pose, position, or activity. If there's a product, show it from a different "
    "angle or in different use. The result should feel like a fresh, creative variation taken in "
    "the same location during the same shoot, offering a distinctly different perspective while "
    "maintaining scene continuity."
)

EDIT_WITH_AI_VARIANT_IDS = frozenset({
    "edit_ai_staging",
    "edit_ai_angle",
    "ai_touchup",
})

# Commerce-first AI scenes — category → grounded scene variant ids (Option A)
CATEGORY_COMMERCE_SCENES: dict[str, tuple[str, ...]] = {
    "apparel": ("ai_scene_table", "ai_scene_shelf", "ai_scene_retail"),
    "apparel_mitumba": ("flat_lay", "ai_scene_table", "ai_scene_retail"),
    "food": ("food_surface_marble", "food_surface_rustic", "food_surface_delivery"),
    "beauty": ("ai_scene_table", "ai_creative_marble", "ai_scene_shelf"),
    "jewelry": ("ai_creative_marble", "ai_scene_wall", "ai_lifestyle"),
    "electronics": ("ai_creative_podium", "ai_scene_table", "ai_scene_shelf"),
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
    "food_surface_marble",
    "food_surface_rustic",
    "food_surface_delivery",
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

# Per-scene product framing — tight padding + fill scaling so the product dominates the square.
VARIANT_LAYOUT_STYLES: tuple[dict[str, str], ...] = (
    {
        "horizontalAlignment": "center",
        "verticalAlignment": "center",
        "padding": "0.05",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "left",
        "verticalAlignment": "bottom",
        "paddingLeft": "0.04",
        "paddingRight": "0.14",
        "paddingTop": "0.10",
        "paddingBottom": "0.04",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "right",
        "verticalAlignment": "top",
        "paddingLeft": "0.14",
        "paddingRight": "0.04",
        "paddingTop": "0.06",
        "paddingBottom": "0.12",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "center",
        "verticalAlignment": "bottom",
        "paddingLeft": "0.06",
        "paddingRight": "0.06",
        "paddingTop": "0.12",
        "paddingBottom": "0.03",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "left",
        "verticalAlignment": "center",
        "paddingLeft": "0.03",
        "paddingRight": "0.16",
        "paddingTop": "0.08",
        "paddingBottom": "0.08",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "right",
        "verticalAlignment": "bottom",
        "paddingLeft": "0.12",
        "paddingRight": "0.03",
        "paddingTop": "0.14",
        "paddingBottom": "0.04",
        "scaling": "fill",
    },
    {
        "horizontalAlignment": "center",
        "verticalAlignment": "top",
        "paddingLeft": "0.08",
        "paddingRight": "0.08",
        "paddingTop": "0.04",
        "paddingBottom": "0.14",
        "scaling": "fill",
    },
)

# Variants that receive per-slide layout offsets (not only AI lifestyle IDs).
LAYOUT_VARIANT_IDS = frozenset({
    "studio_white",
    "studio_brand",
    "studio_dark",
    "outline",
}) | AI_SCENE_VARIANT_IDS | COMMERCE_SCENE_VARIANT_IDS | SOFT_CREATIVE_VARIANT_IDS

# Studio variants that receive pr-ai-shadows-model-version when enabled (Phase 2).
STUDIO_SHADOW_HEADER_VARIANT_IDS = frozenset({
    "studio_white",
    "studio_brand",
    "studio_dark",
    "relight",
    "beautify",
    "outline",
    "upscale",
    "expand",
    "uncrop",
    "channel_marketplace",
    "channel_marketplace_jpeg",
})

PLAN_TIER_ORDER = ("starter", "growth", "pro", "agency")

# Phase C — carousel slide roles (variant pick order)
SLIDE_ROLE_PRODUCT = (
    ("hero", ("studio_white", "studio_brand")),
    ("desire", ("ai_lifestyle", "ai_lifestyle_alt", "ai_contextual")),
    ("lifestyle_edit", ("edit_ai_staging", "edit_ai_angle")),
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
    "apparel_mitumba": ("flat_lay", "ghost_mannequin"),
    "food": ("flat_lay", "text_removal"),
    "beauty": ("flat_lay", "beautify"),
    "jewelry": ("beautify", "studio_dark"),
    "electronics": ("relight", "background_blur"),
    "home": ("flat_lay", "ai_contextual"),
    "general": ("relight", "flat_lay", "background_blur"),
}
MARKETPLACE_CHANNEL_VARIANT_IDS = frozenset({
    "channel_marketplace",
    "channel_marketplace_jpeg",
})
CAROUSEL_EXCLUDE_URL_MARKERS = (
    "channel_story",
    "channel_banner",
    "channel_marketplace",
    "preflight_",
)
SHOP_GALLERY_EXCLUDE_MARKERS = CAROUSEL_EXCLUDE_URL_MARKERS + ("promo_frame",)

PRODUCT_CATEGORIES = (
    "apparel",
    "apparel_mitumba",
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
    scaling = str(getattr(settings, "PHOTOROOM_SCALING", "fill")).strip().lower()
    if scaling in ("fit", "fill"):
        out["scaling"] = scaling
    return out


def _shadow_studio() -> dict[str, str]:
    return {
        "removeBackground": "true",
        "padding": str(getattr(settings, "PHOTOROOM_PADDING", 0.06)),
        "shadow.mode": str(getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft")),
    }


def _ai_scene_studio() -> dict[str, str]:
    """Cutout + AI background; prompt auto-expansion is on by default (no legacy key)."""
    return _shadow_studio()


def _edit_with_ai_params(*, seed: int) -> dict[str, str]:
    """Edit With AI on the full frame (post smart-crop master)."""
    return {
        "removeBackground": "false",
        "referenceBox": "originalImage",
        "editWithAI.mode": "ai.auto",
        "editWithAI.seed": str(seed),
        **_export_defaults(),
    }


def _marketplace_export_params(*, export_format: str) -> dict[str, str]:
    """Google Shopping–style white-bg square (≥75% product fill)."""
    return {
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "outputSize": str(getattr(settings, "PHOTOROOM_MARKETPLACE_SIZE", "1000x1000")),
        "padding": str(getattr(settings, "PHOTOROOM_MARKETPLACE_PADDING", 0.075)),
        "shadow.mode": str(getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft")),
        "scaling": "fill",
        "referenceBox": "originalImage",
        "export.format": export_format,
    }


def _channel_export_params(*, mode: str, size_placeholder: str) -> dict[str, str]:
    """
    Story/banner exports from an already-polished square hero.

    Do not stack removeBackground + shadow on expand/uncrop — Photoroom returns 400.
    """
    return {
        f"{mode}.mode": "ai.auto",
        "outputSize": size_placeholder,
        "export.format": "jpeg",
        "referenceBox": "originalImage",
        "scaling": "fill",
        "removeBackground": "false",
    }


# Keys that conflict with expand/uncrop on pre-composited studio heroes.
_CHANNEL_EXPORT_STRIP_ON_RETRY = frozenset({
    "removeBackground",
    "padding",
    "shadow.mode",
    "shadow.directionOverride",
    "shadow.intensityOverride",
    "shadow.softnessOverride",
    "background.color",
})


def _ai_bg_headers() -> dict[str, str]:
    return {"pr-ai-background-model-version": AI_BG_MODEL_HEADER}


def _shadow_model_headers() -> dict[str, str]:
    """Optional A/B shadow model header on studio cutout variants."""
    if not getattr(settings, "PHOTOROOM_AI_SHADOWS_MODEL_ENABLED", True):
        return {}
    return {"pr-ai-shadows-model-version": AI_SHADOWS_MODEL_HEADER}


def _studio_variant_headers(variant_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = dict(extra or {})
    if variant_id in STUDIO_SHADOW_HEADER_VARIANT_IDS:
        headers.update(_shadow_model_headers())
    return headers


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
        headers=_studio_variant_headers("studio_white"),
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
        headers=_studio_variant_headers("studio_brand"),
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
        headers=_studio_variant_headers("studio_dark"),
        categories=("jewelry", "electronics", "general"),
        priority=70,
    ),
    # ── AI backgrounds ───────────────────────────────────────────────────
    "ai_lifestyle": PlusVariantSpec(
        id="ai_lifestyle",
        label="AI lifestyle scene",
        params={
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
            "background.prompt": "{commerce_retail_prompt}",
            "background.seed": str(AI_BG_SEEDS[3]),
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=(),
        min_plan="growth",
        priority=92,
    ),
    # ── Food delivery preset pack (locked surfaces — Phase 2) ─────────────
    "food_surface_marble": PlusVariantSpec(
        id="food_surface_marble",
        label="Marble counter",
        params={
            **_ai_scene_studio(),
            "background.prompt": "{food_surface_marble_prompt}",
            "background.seed": "117879368",
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("food",),
        min_plan="growth",
        priority=96,
    ),
    "food_surface_rustic": PlusVariantSpec(
        id="food_surface_rustic",
        label="Rustic table",
        params={
            **_ai_scene_studio(),
            "background.prompt": "{food_surface_rustic_prompt}",
            "background.seed": "55994449",
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("food",),
        min_plan="growth",
        priority=95,
    ),
    "food_surface_delivery": PlusVariantSpec(
        id="food_surface_delivery",
        label="Delivery surface",
        params={
            **_ai_scene_studio(),
            "background.prompt": "{food_surface_delivery_prompt}",
            "background.seed": "48672244",
            **_export_defaults(),
        },
        headers=_ai_bg_headers(),
        categories=("food",),
        min_plan="growth",
        priority=94,
    ),
    # ── Soft studio creatives (subtle surfaces — still commerce-safe) ───
    "ai_creative_splash": PlusVariantSpec(
        id="ai_creative_splash",
        label="Water splash hero",
        params={
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            "lighting.mode": "{relight_mode}",
            "background.color": "FFFFFF",
            "padding": str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        headers=_studio_variant_headers("relight"),
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
        headers=_studio_variant_headers("beautify"),
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
        min_plan="pro",
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
    "edit_ai_staging": PlusVariantSpec(
        id="edit_ai_staging",
        label="AI lifestyle staging",
        params={
            **_edit_with_ai_params(
                seed=int(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668)),
            ),
            "editWithAI.prompt": "{edit_ai_staging_prompt}",
        },
        categories=(),
        min_plan="growth",
        priority=91,
    ),
    "edit_ai_angle": PlusVariantSpec(
        id="edit_ai_angle",
        label="AI angle variation",
        params={
            **_edit_with_ai_params(seed=AI_BG_SEEDS[1]),
            "editWithAI.prompt": "{edit_ai_angle_prompt}",
        },
        categories=(),
        min_plan="growth",
        priority=90,
    ),
    "ai_touchup": PlusVariantSpec(
        id="ai_touchup",
        label="AI touch-up",
        params={
            **_edit_with_ai_params(
                seed=int(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668)),
            ),
            "editWithAI.prompt": "{touchup_prompt}",
        },
        categories=(),
        min_plan="agency",
        priority=42,
        pack_eligible=False,
    ),
    # ── Service (work evidence, no physical product) ───────────────────────
    "service_hero": PlusVariantSpec(
        id="service_hero",
        label="Service hero",
        params={
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
            **_ai_scene_studio(),
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
        params=_channel_export_params(mode="expand", size_placeholder="{story_output_size}"),
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=30,
        pack_eligible=False,
    ),
    "channel_story_uncrop": PlusVariantSpec(
        id="channel_story_uncrop",
        label="Story / Reel uncrop (9:16)",
        params=_channel_export_params(mode="uncrop", size_placeholder="{story_output_size}"),
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=29,
        pack_eligible=False,
    ),
    "channel_banner": PlusVariantSpec(
        id="channel_banner",
        label="Banner (16:9)",
        params=_channel_export_params(mode="expand", size_placeholder="{banner_output_size}"),
        categories=(),
        offering_types=("product", "service", "digital"),
        min_plan="growth",
        priority=28,
        pack_eligible=False,
    ),
    "channel_marketplace": PlusVariantSpec(
        id="channel_marketplace",
        label="Marketplace (Google Shopping PNG)",
        params=_marketplace_export_params(export_format="png"),
        headers=_studio_variant_headers("channel_marketplace"),
        categories=(),
        offering_types=("product",),
        min_plan="growth",
        priority=27,
        pack_eligible=False,
    ),
    "channel_marketplace_jpeg": PlusVariantSpec(
        id="channel_marketplace_jpeg",
        label="Marketplace (Google Shopping JPEG)",
        params=_marketplace_export_params(export_format="jpeg"),
        headers=_studio_variant_headers("channel_marketplace_jpeg"),
        categories=(),
        offering_types=("product",),
        min_plan="growth",
        priority=26,
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
        ("apparel", ("shirt", "dress", "shoe", "sneaker", "fashion", "wear", "cloth", "garment", "bag", "handbag", "jacket", "kitenge", "mitumba", "thrift")),
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


def build_edit_ai_staging_prompt(product, analysis: dict | None) -> str:
    """Photoroom Product Staging recipe + product-specific guardrails."""
    name = _clean_name(product)
    analysis = analysis or {}
    hook = analysis.get("campaign_angle") or analysis.get("value_proposition") or ""
    category = detect_product_category(product, analysis)
    extra = (
        f" The hero product is {name} — keep it fully visible, accurate in color and shape, "
        f"and the clear focal point. Category: {category}."
    )
    if hook:
        extra += f" Marketing angle: {hook}."
    extra += " No text overlays or watermarks."
    return EDIT_WITH_AI_PRODUCT_STAGING_BASE + extra


def build_edit_ai_angle_prompt(product, analysis: dict | None) -> str:
    """Photoroom Other Angle recipe + product-specific guardrails."""
    name = _clean_name(product)
    analysis = analysis or {}
    hook = analysis.get("campaign_angle") or ""
    extra = (
        f" The main product is {name} — show it from a fresh angle while keeping it "
        f"recognizable and fully visible."
    )
    if hook:
        extra += f" Mood: {hook}."
    extra += " No text overlays or watermarks."
    return EDIT_WITH_AI_OTHER_ANGLE_BASE + extra


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
        elif value == "{food_surface_marble_prompt}":
            from apps.products.photoroom_food import build_food_surface_prompt

            resolved[key] = build_food_surface_prompt("food_surface_marble", product, analysis)
        elif value == "{food_surface_rustic_prompt}":
            from apps.products.photoroom_food import build_food_surface_prompt

            resolved[key] = build_food_surface_prompt("food_surface_rustic", product, analysis)
        elif value == "{food_surface_delivery_prompt}":
            from apps.products.photoroom_food import build_food_surface_prompt

            resolved[key] = build_food_surface_prompt("food_surface_delivery", product, analysis)
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
        elif value == "{edit_ai_staging_prompt}":
            resolved[key] = build_edit_ai_staging_prompt(product, analysis)
        elif value == "{edit_ai_angle_prompt}":
            resolved[key] = build_edit_ai_angle_prompt(product, analysis)
        elif value == "{beautify_mode}":
            from apps.products.photoroom_api import beautify_mode_for_category

            category = detect_product_category(product, analysis)
            resolved[key] = beautify_mode_for_category(category)
        elif value == "{relight_mode}":
            from apps.products.photoroom_api import relight_mode_for

            offering = getattr(product, "offering_type", "product") or "product"
            category = detect_product_category(product, analysis)
            resolved[key] = relight_mode_for(offering, category)
        else:
            resolved[key] = value

    from apps.products.scene_packs import resolve_scene_vertical, vertical_locked_seed

    vertical = resolve_scene_vertical(product, analysis)
    seed_override = vertical_locked_seed(vertical, spec.id)
    if seed_override is not None:
        if "background.seed" in resolved:
            resolved["background.seed"] = str(seed_override)
        if "editWithAI.seed" in resolved:
            resolved["editWithAI.seed"] = str(seed_override)

    return apply_brand_template(resolved, brand_template, spec)


def _slide_roles_for(
    offering: str,
    category: str,
    *,
    vertical: str | None = None,
    hero_studio_ids: tuple[str, ...] | None = None,
    scene_context: dict | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    from apps.products.scene_packs import (
        vertical_commerce_scenes,
        vertical_hero_studio_ids,
        vertical_proof_variants,
    )

    if offering == "service":
        return SLIDE_ROLE_SERVICE
    if offering == "digital":
        return SLIDE_ROLE_DIGITAL

    pack_vertical = vertical or category
    proof_ids = vertical_proof_variants(pack_vertical, fallback_category=category)
    commerce_ids: tuple[str, ...] = ()
    if getattr(settings, "PHOTOROOM_CREATIVE_SCENES_ENABLED", True):
        commerce_ids = vertical_commerce_scenes(pack_vertical, fallback_category=category)

    scene_context = scene_context or {}
    desire_prefix = ("ai_lifestyle", "ai_lifestyle_alt", "ai_contextual")
    if scene_context.get("prefer_food_surfaces"):
        desire_prefix = ("food_surface_marble", "food_surface_rustic") + desire_prefix
    elif scene_context.get("prefer_jewelry_macro"):
        desire_prefix = ("ai_creative_marble", "ai_lifestyle") + desire_prefix[1:]

    desire_ids = desire_prefix + commerce_ids
    hero_ids = hero_studio_ids or vertical_hero_studio_ids(pack_vertical) or ("studio_white", "studio_brand")

    proof_boost: tuple[str, ...] = ()
    if scene_context.get("has_multi_angles"):
        proof_boost = ("edit_ai_angle",)
    if scene_context.get("prefer_repair_over_ai"):
        proof_boost = proof_boost + ("relight", "beautify", "flat_lay")
    if scene_context.get("prefer_electronics_relight"):
        proof_boost = ("relight",) + proof_boost

    if proof_boost:
        proof_ids = proof_boost + tuple(v for v in proof_ids if v not in proof_boost)

    roles: list[tuple[str, tuple[str, ...]]] = []
    for role_name, variant_ids in SLIDE_ROLE_PRODUCT:
        if role_name == "hero":
            roles.append((role_name, hero_ids))
        elif role_name == "proof":
            roles.append((role_name, proof_ids))
        elif role_name == "desire":
            roles.append((role_name, desire_ids))
        else:
            roles.append((role_name, variant_ids))
    return tuple(roles)


def slide_role_for_variant(variant_id: str, offering: str, category: str) -> str:
    """Carousel role label for a variant id."""
    if variant_id in MARKETPLACE_CHANNEL_VARIANT_IDS:
        return "marketplace"
    if variant_id in EDIT_WITH_AI_VARIANT_IDS:
        return "lifestyle_edit"
    if variant_id in COMMERCE_SCENE_VARIANT_IDS:
        return "commerce"
    if variant_id.startswith("food_surface_"):
        return "food_surface"
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
    if variant_id not in LAYOUT_VARIANT_IDS:
        return params

    style = VARIANT_LAYOUT_STYLES[layout_index % len(VARIANT_LAYOUT_STYLES)]
    out = dict(params)
    out.pop("padding", None)
    out.update(style)
    return out


def _scene_intelligence_context(
    analysis: dict | None,
    *,
    offering: str = "product",
    category: str = "general",
    vertical: str | None = None,
    stall_context: dict | None = None,
) -> dict:
    """Derive content-aware scene selection signals from vision + stall brief."""
    from apps.products.scene_packs import stall_brief_scene_signals

    analysis = analysis or {}
    pq = analysis.get("photo_quality") or {}
    multi_angles = analysis.get("multi_image_angles") or []
    if isinstance(multi_angles, str):
        multi_angles = [multi_angles]

    stall_signals = stall_brief_scene_signals(stall_context) if stall_context else {}

    lighting = (pq.get("lighting") or "good").lower()
    sharpness = (pq.get("sharpness") or "sharp").lower()
    crop = (pq.get("crop") or "comfortable").lower()
    low_quality = (
        sharpness in ("soft", "blurry")
        or lighting in ("dark", "uneven")
        or crop == "very_tight"
    )
    wrinkled_or_worn = any(
        kw in " ".join(
            part.lower()
            for part in (
                analysis.get("visual_style") or "",
                analysis.get("description") or "",
                " ".join(analysis.get("key_features") or []),
            )
        )
        for kw in ("wrinkl", "creased", "worn", "folded", "crumpled")
    )

    return {
        "offering": offering,
        "category": category,
        "vertical": vertical or category,
        "multi_angle_count": len(multi_angles),
        "has_multi_angles": len(multi_angles) >= 2,
        "low_quality": low_quality,
        "wrinkled_or_worn": wrinkled_or_worn,
        "lighting": lighting,
        "sharpness": sharpness,
        "prefer_repair_over_ai": low_quality or wrinkled_or_worn,
        "prefer_food_surfaces": category == "food" or vertical == "food",
        "prefer_jewelry_macro": vertical == "jewelry" or category == "jewelry",
        "prefer_electronics_relight": vertical == "electronics" or category == "electronics",
        "prefer_mitumba_apparel": vertical == "apparel_mitumba",
        "stall_wholesale": stall_signals.get("wholesale_or_clearance", False),
        "stall_premium": stall_signals.get("premium_boutique", False),
        "market_day": stall_signals.get("market_day", False),
    }


def _target_ai_scene_count(
    max_count: int,
    *,
    analysis: dict | None = None,
    offering: str = "product",
    category: str = "general",
    vertical: str | None = None,
    stall_context: dict | None = None,
) -> int:
    """How many AI background scenes to generate — content-aware, not budget-only."""
    min_ai = int(getattr(settings, "PHOTOROOM_MIN_AI_SCENES", 2))
    max_ai = int(getattr(settings, "PHOTOROOM_MAX_AI_SCENES", 3))
    if max_count <= 1 or offering != "product":
        return 0

    available = max_count - 1  # reserve hero
    if max_count >= 5:
        target = max_ai
    elif max_count >= 3:
        target = min_ai
    else:
        target = 1

    ctx = _scene_intelligence_context(
        analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )

    if ctx["prefer_repair_over_ai"]:
        target = min(target, 1)
    if ctx["has_multi_angles"]:
        target = max(0, target - 1)
    if ctx["stall_wholesale"]:
        target = max(1, target - 1)
    if ctx["prefer_jewelry_macro"] and max_count >= 4:
        target = min(max_ai, max(target, min_ai))
    if ctx["prefer_food_surfaces"] and max_count >= 3:
        target = min(max_ai, max(target, min_ai))

    return min(target, available, max_ai)


def _target_edit_with_ai_count(
    max_count: int,
    *,
    analysis: dict | None = None,
    offering: str = "product",
    category: str = "general",
    vertical: str | None = None,
    stall_context: dict | None = None,
) -> int:
    """How many Edit With AI slides when budget allows — boosted for multi-angle uploads."""
    if not getattr(settings, "PHOTOROOM_EDIT_WITH_AI_ENABLED", True):
        return 0
    cap = int(getattr(settings, "PHOTOROOM_EDIT_WITH_AI_MAX_PER_PACK", 2))
    if max_count < 3 or offering != "product":
        return 0

    ctx = _scene_intelligence_context(
        analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )

    if max_count < 5:
        base = 1
    else:
        base = min(cap, max(0, max_count - 3))

    if ctx["has_multi_angles"]:
        base = min(cap, base + 1)
    if ctx["prefer_repair_over_ai"]:
        base = min(base, 1)
    return min(base, cap)


def order_variants_by_slide_role(
    candidates: list[PlusVariantSpec],
    *,
    offering: str,
    category: str,
    max_count: int,
    uncertainty_score: float | None = None,
    hero_studio_ids: tuple[str, ...] | None = None,
    analysis: dict | None = None,
    vertical: str | None = None,
    stall_context: dict | None = None,
) -> list[PlusVariantSpec]:
    """Pick variants to fill hero → desire (2–3 AI) → proof → standout."""
    from apps.products.photoroom_api import (
        HIGH_UNCERTAINTY_VARIANT_IDS,
        uncertainty_is_high,
    )

    by_id = {s.id: s for s in candidates}
    picked: list[PlusVariantSpec] = []
    picked_ids: set[str] = set()
    ai_target = _target_ai_scene_count(
        max_count,
        analysis=analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )
    edit_target = _target_edit_with_ai_count(
        max_count,
        analysis=analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )
    skip_risky = uncertainty_is_high(uncertainty_score)
    scene_ctx = _scene_intelligence_context(
        analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )

    for role_name, preferred_ids in _slide_roles_for(
        offering,
        category,
        vertical=vertical,
        hero_studio_ids=hero_studio_ids,
        scene_context=scene_ctx,
    ):
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

        if role_name == "lifestyle_edit":
            picked_edit = 0
            for vid in preferred_ids:
                if len(picked) >= max_count or picked_edit >= edit_target:
                    break
                spec = by_id.get(vid)
                if spec and vid not in picked_ids:
                    picked.append(spec)
                    picked_ids.add(vid)
                    picked_edit += 1
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


def _boost_candidates_for_scene_pack(
    candidates: list[PlusVariantSpec],
    *,
    scene_pack: str | None,
    plan_tier: str,
) -> list[PlusVariantSpec]:
    from apps.products.scene_packs import (
        SCENE_PACK_AUTO,
        normalize_scene_pack,
        scene_pack_priority_variant_ids,
    )

    pack = normalize_scene_pack(scene_pack)
    if pack == SCENE_PACK_AUTO:
        return candidates

    priority_ids = scene_pack_priority_variant_ids(pack, plan_tier=plan_tier)
    if not priority_ids:
        return candidates

    by_id = {spec.id: spec for spec in candidates}
    boosted: list[PlusVariantSpec] = []
    seen: set[str] = set()
    for vid in priority_ids:
        spec = by_id.get(vid)
        if spec and vid not in seen:
            boosted.append(spec)
            seen.add(vid)
    for spec in candidates:
        if spec.id not in seen:
            boosted.append(spec)
            seen.add(spec.id)
    return boosted


def _boost_candidates_for_vertical(
    candidates: list[PlusVariantSpec],
    *,
    vertical: str,
    plan_tier: str,
    category: str,
) -> list[PlusVariantSpec]:
    from apps.products.scene_packs import vertical_priority_variant_ids

    priority_ids = vertical_priority_variant_ids(
        vertical, plan_tier=plan_tier, fallback_category=category,
    )
    if not priority_ids:
        return candidates

    by_id = {spec.id: spec for spec in candidates}
    boosted: list[PlusVariantSpec] = []
    seen: set[str] = set()
    for vid in priority_ids:
        spec = by_id.get(vid)
        if spec and vid not in seen:
            boosted.append(spec)
            seen.add(vid)
    for spec in candidates:
        if spec.id not in seen:
            boosted.append(spec)
            seen.add(spec.id)
    return boosted


def select_plus_variants(
    product,
    analysis: dict | None,
    *,
    plan_tier: str = "starter",
    max_count: int = 5,
    uncertainty_score: float | None = None,
    brand_template=None,
    brand_colors: dict | None = None,
    commerce_source: str | None = None,
    scene_pack: str | None = None,
    stall_context: dict | None = None,
) -> list[PlusVariantSpec]:
    """Pick applicable Plus variants for this product, highest priority first."""
    from apps.products.batch_snap_intelligence import is_market_day_mode
    from apps.products.photoroom_api import (
        HIGH_UNCERTAINTY_VARIANT_IDS,
        uncertainty_is_high,
    )
    from apps.products.photoroom_brand_template import hero_studio_variant_ids
    from apps.products.scene_packs import resolve_scene_vertical, vertical_hero_studio_ids

    analysis = analysis or {}
    stall_context = stall_context or analysis.get("_stall_context") or {}

    offering = getattr(product, "offering_type", "product") or "product"
    category = detect_product_category(product, analysis)
    vertical = resolve_scene_vertical(product, analysis, stall_context=stall_context)
    plan_rank = _plan_rank(plan_tier)
    skip_risky = uncertainty_is_high(uncertainty_score)
    scene_ctx = _scene_intelligence_context(
        analysis,
        offering=offering,
        category=category,
        vertical=vertical,
        stall_context=stall_context,
    )

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

    from apps.products.scene_packs import normalize_scene_pack, scene_pack_hero_studio_ids

    force_brand = is_market_day_mode(commerce_source)
    pack_hero_ids = scene_pack_hero_studio_ids(normalize_scene_pack(scene_pack))
    vertical_hero_ids = vertical_hero_studio_ids(vertical)
    hero_studio_ids = (
        pack_hero_ids
        or vertical_hero_ids
        or hero_studio_variant_ids(brand_template, brand_colors, force_brand=force_brand)
    )

    # Always include brand-aware studio hero + lifestyle for physical products
    if offering == "product":
        for required_id in (*hero_studio_ids, "ai_lifestyle"):
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

    # Category / vertical boosters (skip cutout-sensitive AI when uncertainty is high)
    if vertical == "apparel_mitumba" or (category == "apparel" and scene_ctx.get("prefer_mitumba_apparel")):
        flat = PLUS_VARIANT_CATALOG.get("flat_lay")
        if flat and flat not in candidates:
            candidates.append(flat)
        if not skip_risky:
            ghost = PLUS_VARIANT_CATALOG.get("ghost_mannequin")
            if ghost and _plan_rank(ghost.min_plan) <= plan_rank and ghost not in candidates:
                candidates.append(ghost)
    elif category == "apparel" and not skip_risky:
        ghost = PLUS_VARIANT_CATALOG.get("ghost_mannequin")
        if ghost and _plan_rank(ghost.min_plan) <= plan_rank and ghost not in candidates:
            candidates.append(ghost)
        if getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_ENABLED", False):
            vm = PLUS_VARIANT_CATALOG.get("virtual_model")
            if vm and vm not in candidates:
                candidates.append(vm)
    elif vertical == "jewelry" or category == "jewelry":
        for vid in ("studio_dark", "ai_creative_marble", "beautify", "relight"):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)
    elif vertical == "electronics" or category == "electronics":
        for vid in ("relight", "ai_creative_podium", "background_blur"):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)
    elif category == "food":
        from apps.products.photoroom_food import (
            FOOD_SURFACE_VARIANT_IDS,
            should_boost_food_beautify,
        )

        if not skip_risky:
            flat = PLUS_VARIANT_CATALOG.get("flat_lay")
            if flat and flat not in candidates:
                candidates.append(flat)
        if should_boost_food_beautify(category, commerce_source):
            beautify = PLUS_VARIANT_CATALOG.get("beautify")
            if beautify and beautify not in candidates:
                candidates.append(beautify)
        if (commerce_source or "") in {"snap", "batch_snap", "snap_to_sell"}:
            for vid in FOOD_SURFACE_VARIANT_IDS:
                spec = PLUS_VARIANT_CATALOG.get(vid)
                if spec and spec not in candidates:
                    candidates.append(spec)
    elif category == "beauty" and not skip_risky:
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
        from apps.products.scene_packs import vertical_commerce_scenes

        commerce_vids = vertical_commerce_scenes(vertical, fallback_category=category)
        for vid in commerce_vids:
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)

    if (
        offering == "product"
        and getattr(settings, "PHOTOROOM_EDIT_WITH_AI_ENABLED", True)
    ):
        for vid in ("edit_ai_staging", "edit_ai_angle"):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and _plan_rank(spec.min_plan) <= plan_rank and spec not in candidates:
                candidates.append(spec)

    candidates = _boost_candidates_for_scene_pack(
        candidates,
        scene_pack=scene_pack,
        plan_tier=plan_tier,
    )
    candidates = _boost_candidates_for_vertical(
        candidates,
        vertical=vertical,
        plan_tier=plan_tier,
        category=category,
    )

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
            hero_studio_ids=hero_studio_ids,
            analysis=analysis,
            vertical=vertical,
            stall_context=stall_context,
        )
    return ordered[: max(1, max_count)]


def get_max_variants_for_plan(plan_tier: str) -> int:
    from apps.billing.models import PLAN_LIMITS

    limits = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["starter"])
    return int(limits.get("plus_max_variants_per_product", 3))


def multi_angle_polish_credit_enabled(plan_tier: str) -> bool:
    """Growth+ plans may polish one extra uploaded angle (+1 credit)."""
    from apps.products.scene_packs import multi_angle_polish_enabled

    return multi_angle_polish_enabled(plan_tier)


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


def _strip_conflicting_edit_params(params: dict[str, str]) -> dict[str, str]:
    """Remove cutout/shadow keys that break expand/uncrop on studio heroes."""
    if not any(k in params for k in ("expand.mode", "uncrop.mode")):
        return params
    return {k: v for k, v in params.items() if k not in _CHANNEL_EXPORT_STRIP_ON_RETRY}


def _photoroom_error_detail(exc: Exception) -> str:
    resp = getattr(exc, "response", None)
    if resp is not None:
        try:
            return (resp.text or "")[:400]
        except Exception:
            pass
    return str(exc)


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
        normalize_photoroom_edit_params,
        parse_uncertainty_score,
        record_sandbox_call,
    )

    params = normalize_photoroom_edit_params(dict(params))

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

    def _post_bytes(data_params: dict[str, str], payload: bytes, filename: str) -> PhotoroomEditResult:
        try:
            resp = requests.post(
                PHOTOROOM_EDIT_URL,
                headers=headers,
                files={"imageFile": (filename, payload, "image/jpeg")},
                data=data_params,
                timeout=180,
            )
            resp.raise_for_status()
            return _finish(resp)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                fallback = _strip_conflicting_edit_params(data_params)
                if fallback != data_params:
                    logger.warning(
                        "Photoroom POST 400 — retrying without cutout stack keys=%s detail=%s",
                        list(fallback.keys())[:6],
                        _photoroom_error_detail(exc),
                    )
                    try:
                        resp = requests.post(
                            PHOTOROOM_EDIT_URL,
                            headers=headers,
                            files={"imageFile": (filename, payload, "image/jpeg")},
                            data=fallback,
                            timeout=180,
                        )
                        resp.raise_for_status()
                        return _finish(resp)
                    except Exception as retry_exc:
                        logger.error(
                            "Photoroom POST retry failed [%s]: %s",
                            list(fallback.keys())[:6],
                            _photoroom_error_detail(retry_exc),
                        )
                        return PhotoroomEditResult(content=None, error=str(retry_exc))
            logger.error(
                "Photoroom POST v2/edit (bytes) failed [%s]: %s",
                list(data_params.keys())[:6],
                _photoroom_error_detail(exc),
            )
            return PhotoroomEditResult(content=None, error=str(exc))
        except Exception as exc:
            logger.error(
                "Photoroom POST v2/edit (bytes) failed [%s]: %s",
                list(data_params.keys())[:6],
                exc,
            )
            return PhotoroomEditResult(content=None, error=str(exc))

    if file_bytes:
        return _post_bytes(params, file_bytes, file_name)

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

    return _post_bytes(params, file_bytes, filename)


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
    from apps.products.photoroom_basic import is_basic_routable_variant, run_basic_white_cutout

    params = resolve_variant_params(
        spec, product, analysis, brand_colors, brand_template=brand_template
    )
    params = apply_variant_layout(params, spec.id, layout_index)
    headers = {**spec.headers, **_studio_variant_headers(spec.id)}

    if is_basic_routable_variant(spec.id, params):
        content = run_basic_white_cutout(image_url, params)
        if content:
            return PhotoroomEditResult(
                content=content,
                uncertainty_score=None,
                api="basic/v1/segment",
            )
        logger.info("Basic cutout failed for %s — falling back to Plus", spec.id)

    result = photoroom_edit(image_url, params, extra_headers=headers)
    return result


def catalog_labels() -> list[str]:
    return [spec.label for spec in PLUS_VARIANT_CATALOG.values()]
