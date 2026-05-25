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
AI_BG_SEEDS = (117879368, 55994449, 48672244, 65080068)

PLAN_TIER_ORDER = ("starter", "growth", "pro", "agency")

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
    return {
        "referenceBox": "originalImage",
        "outputSize": str(getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")),
        "export.format": "jpeg",
    }


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
        priority=90,
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
        priority=85,
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
        priority=80,
    ),
    # ── Enhancement ──────────────────────────────────────────────────────
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
            "beautify.mode": "ai.auto",
            "background.color": "FFFFFF",
            "padding": "0.10",
            "shadow.mode": "ai.soft",
            **_export_defaults(),
        },
        categories=("beauty", "jewelry", "general"),
        min_plan="growth",
        priority=72,
    ),
    "background_blur": PlusVariantSpec(
        id="background_blur",
        label="Depth blur",
        params={
            "removeBackground": "true",
            "background.blur.mode": "ai.auto",
            "padding": str(getattr(settings, "PHOTOROOM_PADDING", 0.12)),
            "shadow.mode": "ai.soft",
            **_export_defaults(),
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
            "virtualModel.mode": "ai.auto",
            "virtualModel.prompt": "{apparel_prompt}",
            "virtualModel.quality": "high",
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


def build_lifestyle_prompt(product, analysis: dict | None, *, variant: str = "primary") -> str:
    name = _clean_name(product)
    category = detect_product_category(product, analysis)
    analysis = analysis or {}
    angle = analysis.get("campaign_angle") or analysis.get("visual_style") or "professional marketing"
    templates = {
        "apparel": {
            "primary": (
                f"A professional product photo of {name} displayed on a clean minimal studio set "
                f"with soft natural lighting, subtle props, and a modern lifestyle feel. {angle}."
            ),
            "alt": (
                f"{name} styled in an urban streetwear scene with warm golden hour light, "
                f"shallow depth of field, and a premium editorial look."
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
    return bucket[key]


def build_contextual_prompt(product, analysis: dict | None) -> str:
    name = _clean_name(product)
    analysis = analysis or {}
    audience = analysis.get("target_audience") or "customers"
    features = ", ".join((analysis.get("key_features") or [])[:3])
    feature_clause = f" Highlight: {features}." if features else ""
    return (
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
) -> dict[str, str]:
    from apps.products.photoroom import pick_background_color_hex

    brand_colors = brand_colors or {}
    resolved: dict[str, str] = {}
    for key, value in spec.params.items():
        if value == "{brand_color}":
            resolved[key] = pick_background_color_hex(product, brand_colors)
        elif value == "{lifestyle_prompt}":
            resolved[key] = build_lifestyle_prompt(product, analysis, variant="primary")
        elif value == "{lifestyle_prompt_alt}":
            resolved[key] = build_lifestyle_prompt(product, analysis, variant="alt")
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
        else:
            resolved[key] = value
    return resolved


def select_plus_variants(
    product,
    analysis: dict | None,
    *,
    plan_tier: str = "starter",
    max_count: int = 5,
) -> list[PlusVariantSpec]:
    """Pick applicable Plus variants for this product, highest priority first."""
    offering = getattr(product, "offering_type", "product") or "product"
    category = detect_product_category(product, analysis)
    plan_rank = _plan_rank(plan_tier)

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

    # Category boosters
    if category == "apparel":
        for vid in ("ghost_mannequin", "virtual_model"):
            spec = PLUS_VARIANT_CATALOG.get(vid)
            if spec and spec not in candidates:
                candidates.append(spec)
    elif category in ("food", "beauty"):
        spec = PLUS_VARIANT_CATALOG.get("flat_lay")
        if spec and spec not in candidates:
            candidates.append(spec)

    seen: set[str] = set()
    ordered: list[PlusVariantSpec] = []
    for spec in sorted(candidates, key=lambda s: -s.priority):
        if spec.id in seen:
            continue
        seen.add(spec.id)
        ordered.append(spec)

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
) -> bytes | None:
    """Call Photoroom Plus v2/edit with arbitrary params. Returns JPEG/PNG bytes."""
    api_key, headers = _api_key_headers(extra_headers)
    if not api_key:
        logger.info("Photoroom edit skipped: PHOTOROOM_API_KEY not set")
        return None

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
                return resp.content
        except Exception as exc:
            logger.warning("Photoroom GET v2/edit failed (%s), trying POST: %s", params.get("background.prompt", "studio")[:40], exc)

    loaded = _load_image_bytes(image_url)
    if not loaded:
        return None
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
        return resp.content or None
    except Exception as exc:
        logger.error("Photoroom POST v2/edit failed [%s]: %s", list(params.keys())[:4], exc)
        return None


def run_plus_variant(
    image_url: str,
    spec: PlusVariantSpec,
    product,
    analysis: dict | None,
    brand_colors: dict | None,
) -> bytes | None:
    params = resolve_variant_params(spec, product, analysis, brand_colors)
    return photoroom_edit(image_url, params, extra_headers=spec.headers)


def catalog_labels() -> list[str]:
    return [spec.label for spec in PLUS_VARIANT_CATALOG.values()]
