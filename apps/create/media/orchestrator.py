"""
High-level media orchestration — runs after Snap polish, feeds carousel/reel pipelines.
"""

from __future__ import annotations

import logging

from apps.create.media.asset_intelligence import persist_media_plan, recommend_media_plan
from apps.create.media.brand_dna import resolve_brand_dna
from apps.create.media.content_types import EnhancementBackend, MediaPlan
from apps.create.media.fal_client import flux_edit_image
from apps.commerce.products.business_assets import sync_asset_from_product

logger = logging.getLogger(__name__)

# Max Photoroom Plus scenes per activated campaign.
# Professional mode raises cap — Photoroom is primary value (see PHOTOROOM_PROFESSIONAL_MODE).
MAX_PHOTOROOM_SCENES_PER_CAMPAIGN = 5
PROFESSIONAL_PHOTOROOM_SCENES_PER_CAMPAIGN = 12


def professional_scene_cap() -> int:
    from django.conf import settings

    if getattr(settings, "PHOTOROOM_PROFESSIONAL_MODE", True):
        return int(
            getattr(settings, "PHOTOROOM_PROFESSIONAL_SCENE_CAP", PROFESSIONAL_PHOTOROOM_SCENES_PER_CAMPAIGN)
        )
    return MAX_PHOTOROOM_SCENES_PER_CAMPAIGN


def cap_photoroom_scenes_for_plan(user, requested: int) -> int:
    """Clamp scene count to plan + campaign limits."""
    from apps.core.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    cap = int(limits.get("max_photoroom_scenes_per_campaign") or professional_scene_cap())
    return max(1, min(requested, cap))


def execute_visual_brief(
    product,
    *,
    seed=None,
    campaign=None,
    analysis: dict | None = None,
    commerce_source: str = "campaign",
) -> dict:
    """
    Central Photoroom entry for campaign-driven visual production.
    Builds/refreshes CampaignVisualBrief then runs studio polish.
    """
    from apps.create.media.campaign_visual_brief import (
        build_campaign_visual_brief,
        get_visual_brief_for_product,
        persist_visual_brief,
    )
    from apps.commerce.products.photo_variations import expand_product_photos

    brief = get_visual_brief_for_product(product)
    if not brief and seed is not None:
        brief = build_campaign_visual_brief(seed, campaign, user=product.user)
        if campaign:
            persist_visual_brief(campaign, brief)

    return expand_product_photos(
        product,
        analysis=analysis,
        commerce_source=commerce_source,
        visual_brief=brief,
    )


def plan_media_for_product(
  product,
  *,
  analysis: dict | None = None,
) -> MediaPlan:
  """Compute and persist media plan on the linked BusinessAsset."""
  user = product.user
  image_count = len(product.all_image_urls or [])
  asset = sync_asset_from_product(product)
  plan = recommend_media_plan(
    user,
    asset=asset,
    product=product,
    image_count=image_count,
    analysis=analysis,
  )
  persist_media_plan(asset, plan)
  return plan


def apply_flux_enhancement_if_needed(product, plan: MediaPlan) -> str | None:
  """Optional Flux edit on hero image when plan requests it."""
  if plan.enhancement != EnhancementBackend.FLUX_EDIT:
    return None
  urls = product.all_image_urls
  if not urls:
    return None
  dna = resolve_brand_dna(product.user)
  prompt = plan.flux_edit_prompt or f"Professional marketing visual, {dna.flux_style_suffix()}"
  return flux_edit_image(urls[0], prompt=prompt)


def media_hints_for_reel_post(plan: MediaPlan | None) -> dict:
  """Visual metadata hints for reel posts."""
  if not plan:
    return {}
  hints: dict = {
    "media_plan_rationale": plan.rationale,
  }
  if plan.reel_backend.value == "kling":
    hints["reel_compose_backend"] = "kling"
    hints["kling_prompt"] = plan.kling_prompt
    hints["prefer_kling_video"] = True
  elif plan.reel_backend.value == "photoroom":
    hints["prefer_photoroom_video"] = True
  return hints
