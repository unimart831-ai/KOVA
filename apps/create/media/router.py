"""Plan-tier gates and backend selection for media pipelines."""

from __future__ import annotations

from typing import Any

from apps.create.media.content_types import CarouselBackend, EnhancementBackend, MediaPlan, ReelBackend


def plan_allows(user, feature: str, default: bool = False) -> bool:
  from apps.core.billing.models import get_user_plan_limits
  return bool(get_user_plan_limits(user).get(feature, default))


def pick_reel_backend(
  user,
  *,
  plan: MediaPlan | None = None,
  image_count: int = 1,
  visual_metadata: dict | None = None,
) -> ReelBackend:
  meta = visual_metadata or {}
  if meta.get("reel_compose_backend") == "ffmpeg":
    return ReelBackend.FFMPEG
  if plan and plan.reel_backend == ReelBackend.KLING:
    if plan_allows(user, "kling_reels_enabled"):
      from apps.create.media.fal_client import fal_enabled
      if fal_enabled():
        return ReelBackend.KLING
  if meta.get("prefer_photoroom_video") or meta.get("composition_hero_url"):
    from apps.commerce.products.photoroom_video import video_generation_enabled
    if video_generation_enabled() and image_count == 1:
      return ReelBackend.PHOTOROOM
  return ReelBackend.FFMPEG


def pick_carousel_backend(user, plan: MediaPlan | None = None) -> CarouselBackend:
  if plan and plan.carousel_backend == CarouselBackend.BANNERBEAR:
    if plan_allows(user, "bannerbear_carousels_enabled"):
      from apps.create.media.bannerbear_client import bannerbear_enabled
      if bannerbear_enabled():
        return CarouselBackend.BANNERBEAR
  return CarouselBackend.LOCAL


def pick_enhancement_backend(user, plan: MediaPlan | None = None) -> EnhancementBackend:
  if plan and plan.enhancement == EnhancementBackend.FLUX_EDIT:
    if plan_allows(user, "fal_flux_edits_per_month", 0) > 0:
      from apps.create.media.fal_client import fal_enabled
      if fal_enabled():
        return EnhancementBackend.FLUX_EDIT
  from apps.commerce.products.photoroom import photoroom_enabled
  if photoroom_enabled():
    return EnhancementBackend.PHOTOROOM
  return EnhancementBackend.NONE


def reel_backend_for_post(post) -> ReelBackend:
  user = post.user
  meta = dict(post.visual_metadata or {})
  plan = None
  if post.product_id:
    try:
      asset = post.product.business_asset
      plan = MediaPlan.from_metadata((asset.metadata or {}).get("media_plan"))
    except Exception:
      pass
  image_count = len(
    meta.get("source_images")
    or meta.get("reel_image_sources")
    or post.media_urls
    or []
  )
  return pick_reel_backend(user, plan=plan, image_count=image_count, visual_metadata=meta)
