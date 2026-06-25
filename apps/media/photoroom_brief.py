"""
Photoroom brief execution — map CampaignVisualBrief → Plus variants + QA.

All campaign-grade Photoroom jobs should flow through here (orchestrator entry).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from apps.media.campaign_visual_brief import CampaignVisualBrief
    from apps.products.photoroom_api import PhotoroomEditResult
    from apps.products.photoroom_plus import PlusVariantSpec

logger = logging.getLogger(__name__)

# Scene role → Photoroom variant IDs (professional pack — ordered by priority)
SCENE_ROLE_VARIANTS: dict[str, tuple[str, ...]] = {
    "studio": (
        "smart_crop",
        "photofix",
        "studio_safe",
        "studio_brand",
        "relight",
        "beautify",
    ),
    "lifestyle": (
        "ai_lifestyle",
        "ai_scene_table",
        "ai_scene_shelf",
        "ai_scene_retail",
        "edit_ai_staging",
    ),
    "feature": (
        "edit_ai_angle",
        "background_blur",
        "upscale",
        "text_removal",
    ),
    "offer": (
        "edit_ai_staging",
        "ai_creative_podium",
        "ai_creative_marble",
        "relight",
    ),
    "cta": (
        "channel_story",
        "channel_banner",
        "expand",
    ),
}

# Category boosts — appended when brief business_type / detected category matches
CATEGORY_VARIANT_BOOSTS: dict[str, tuple[str, ...]] = {
    "electronics": (
        "ai_creative_podium",
        "ai_scene_table",
        "ai_scene_shelf",
        "relight",
        "background_blur",
        "virtual_model_hold",
    ),
    "wholesale_retail": (
        "ai_scene_retail",
        "ai_creative_podium",
        "ai_scene_shelf",
        "virtual_model_hold",
    ),
    "apparel": ("flat_lay", "ghost_mannequin", "virtual_model"),
    "apparel_mitumba": ("flat_lay", "ghost_mannequin", "virtual_model"),
    "food": ("beautify_nocutout", "flat_lay", "food_surface_marble", "food_surface_rustic", "beautify", "virtual_model_hold"),
    "beauty": ("beautify_nocutout", "flat_lay", "ai_creative_marble", "beautify", "virtual_model_adorn"),
    "jewelry": ("studio_dark", "ai_creative_marble", "relight_nocutout", "virtual_model_adorn"),
    "home": ("ai_scene_shelf", "ai_scene_wall", "ai_scene_table", "virtual_model_hold"),
    "general": ("virtual_model_hold",),
}

VARIANT_TO_SCENE_ROLE: dict[str, str] = {}
for _role, _ids in SCENE_ROLE_VARIANTS.items():
    for _vid in _ids:
        VARIANT_TO_SCENE_ROLE.setdefault(_vid, _role)


def professional_mode_enabled() -> bool:
    return bool(getattr(settings, "PHOTOROOM_PROFESSIONAL_MODE", True))


def max_scenes_for_user(user) -> int:
    from apps.media.orchestrator import cap_photoroom_scenes_for_plan, professional_scene_cap

    cap = professional_scene_cap() if professional_mode_enabled() else 5
    return cap_photoroom_scenes_for_plan(user, cap)


def variant_ids_from_brief(
    brief: CampaignVisualBrief,
    *,
    user,
    category: str = "general",
    offering: str = "product",
) -> list[str]:
    """Ordered variant IDs derived from campaign visual brief + category."""
    from apps.media.campaign_visual_brief import SCENE_ROLE_ALIASES

    scenes = brief.capped_scenes(user) if user else list(brief.scenes or [])
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(vid: str) -> None:
        if vid and vid not in seen:
            seen.add(vid)
            ordered.append(vid)

    # Per-scene heroes (2 variants each — studio, lifestyle, feature, offer, cta)
    for scene in scenes:
        role = SCENE_ROLE_ALIASES.get(str(scene).lower().replace(" ", "_"), str(scene).lower())
        role_ids = SCENE_ROLE_VARIANTS.get(role, ())
        for vid in role_ids[:2]:
            _add(vid)

    biz = (brief.business_type or "").lower().replace("-", "_")
    for key in (category, biz):
        if key in CATEGORY_VARIANT_BOOSTS:
            for vid in CATEGORY_VARIANT_BOOSTS[key]:
                _add(vid)

    if offering == "product" and getattr(settings, "PHOTOROOM_VIRTUAL_MODEL_ENABLED", False):
        from apps.products.photoroom_virtual_models import (
            catalog_variant_for_strategy,
            resolve_virtual_model_strategy,
        )

        strat_category = category
        if biz in ("fashion_beauty",) and category == "general":
            strat_category = "apparel"
        _add(catalog_variant_for_strategy(resolve_virtual_model_strategy(strat_category)))

    if getattr(settings, "PHOTOROOM_EDIT_WITH_AI_ENABLED", True):
        _add("edit_ai_staging")
        _add("edit_ai_angle")

    cap = max_scenes_for_user(user) if user else len(ordered)
    return ordered[: max(1, cap)]


def scene_prompt_for_variant(
    brief: CampaignVisualBrief | None,
    variant_id: str,
    *,
    product_name: str = "",
) -> str | None:
    if not brief:
        return None
    role = VARIANT_TO_SCENE_ROLE.get(variant_id, "studio")
    return brief.photoroom_scene_prompt(role, product_name=product_name)


def merge_brief_into_params(
    params: dict[str, str],
    scene_prompt: str | None,
) -> dict[str, str]:
    """Blend campaign brief prompt into Photoroom API params."""
    if not scene_prompt:
        return params
    merged = dict(params)
    for key in ("background.prompt", "editWithAI.prompt", "flatLay.prompt", "ghostMannequin.prompt"):
        if key in merged and merged[key]:
            merged[key] = f"{scene_prompt} {merged[key]}".strip()
        elif key in merged:
            merged[key] = scene_prompt
    return merged


def validate_plus_result(
    result: PhotoroomEditResult,
    *,
    variant_id: str = "",
) -> tuple[bool, str]:
    """Post-render QA — uncertainty, size, sandbox."""
    if getattr(result, "sandbox_limited", False):
        return False, "sandbox_limited"
    if getattr(result, "error", None):
        return False, str(result.error)[:120]
    content = getattr(result, "content", None)
    if not content or len(content) < 2048:
        return False, "empty_or_tiny_output"
    score = getattr(result, "uncertainty_score", None)
    threshold = float(getattr(settings, "PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD", 0.6))
    if score is not None and score > threshold and variant_id not in (
        "relight",
        "relight_nocutout",
        "photofix",
        "beautify",
        "smart_crop",
    ):
        return False, f"high_uncertainty:{score:.2f}"
    return True, ""


def qa_retry_params(variant_id: str, category: str) -> dict[str, str] | None:
    """Fallback params when QA fails — PhotoFix / relight / safe studio."""
    from apps.products.photoroom_api import beautify_mode_for_category, relight_mode_for

    if variant_id in ("photofix", "beautify", "beautify_nocutout", "smart_crop"):
        return None
    if category == "food":
        return {"beautify.mode": beautify_mode_for_category(category), "removeBackground": "false"}
    return {
        "lighting.mode": relight_mode_for("product", category),
        "removeBackground": "true",
        "background.color": "FFFFFF",
        "padding": "0.08",
    }


def prioritize_brief_variants(
    candidates: list[PlusVariantSpec],
    brief_ids: list[str],
) -> list[PlusVariantSpec]:
    """Reorder candidate specs — brief-driven IDs first."""
    by_id = {s.id: s for s in candidates}
    ordered: list[PlusVariantSpec] = []
    seen: set[str] = set()
    for vid in brief_ids:
        spec = by_id.get(vid)
        if spec and vid not in seen:
            ordered.append(spec)
            seen.add(vid)
    for spec in sorted(candidates, key=lambda s: -s.priority):
        if spec.id not in seen:
            ordered.append(spec)
            seen.add(spec.id)
    return ordered
