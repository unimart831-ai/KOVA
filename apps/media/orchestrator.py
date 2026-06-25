"""
High-level media orchestration — runs after Snap polish, feeds carousel/reel pipelines.
"""

from __future__ import annotations

import logging

from apps.media.asset_intelligence import persist_media_plan, recommend_media_plan
from apps.media.brand_dna import resolve_brand_dna
from apps.media.content_types import EnhancementBackend, MediaPlan
from apps.media.fal_client import flux_edit_image
from apps.products.business_assets import sync_asset_from_product

logger = logging.getLogger(__name__)

# Max Photoroom Plus scenes per activated campaign (economics guardrail).
MAX_PHOTOROOM_SCENES_PER_CAMPAIGN = 5


def cap_photoroom_scenes_for_plan(user, requested: int) -> int:
    """Clamp scene count to plan + campaign limits."""
    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    cap = int(limits.get("max_photoroom_scenes_per_campaign") or MAX_PHOTOROOM_SCENES_PER_CAMPAIGN)
    return max(1, min(requested, cap))


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
