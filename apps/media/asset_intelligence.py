"""
Asset intelligence — pick content formats from asset type and business context.
"""

from __future__ import annotations

from typing import Any

from apps.media.brand_dna import BrandDNA, resolve_brand_dna
from apps.media.content_types import (
  CarouselBackend,
  ContentFormat,
  EnhancementBackend,
  MediaPlan,
  ReelBackend,
)
from apps.products.models import BusinessAsset, Product


def _asset_type(asset: Any) -> str:
  if asset is None:
    return BusinessAsset.AssetType.PRODUCT
  if isinstance(asset, BusinessAsset):
    return asset.asset_type
  if isinstance(asset, Product):
    from apps.products.business_assets import asset_type_for_product
    return asset_type_for_product(asset)
  return str(getattr(asset, "asset_type", BusinessAsset.AssetType.PRODUCT))


def recommend_media_plan(
  user,
  *,
  asset: Any = None,
  product: Product | None = None,
  image_count: int = 1,
  analysis: dict | None = None,
  profile=None,
) -> MediaPlan:
  """Recommend formats and backends for a business asset."""
  from apps.billing.models import get_user_plan_limits
  from apps.media.bannerbear_client import bannerbear_enabled
  from apps.media.fal_client import fal_enabled

  dna = resolve_brand_dna(user, profile)
  limits = get_user_plan_limits(user)
  asset_type = _asset_type(asset or product)
  business_model = dna.business_model
  analysis = analysis or {}

  formats: list[ContentFormat] = [ContentFormat.SINGLE_POST]
  reel_backend = ReelBackend.FFMPEG
  carousel_backend = CarouselBackend.LOCAL
  enhancement = EnhancementBackend.PHOTOROOM
  scene_pack = "auto"
  rationale_parts: list[str] = []

  is_transformation = any(
    w in (analysis.get("visual_style") or "").lower()
    for w in ("before", "after", "transformation")
  ) or asset_type in (BusinessAsset.AssetType.SERVICE,)

  if asset_type in (BusinessAsset.AssetType.PORTFOLIO, BusinessAsset.AssetType.CASE_STUDY):
    formats = [ContentFormat.CAROUSEL, ContentFormat.SINGLE_POST]
    if image_count >= 2:
      formats.append(ContentFormat.REEL)
    rationale_parts.append("portfolio/case study → carousel-first")
  elif asset_type in (BusinessAsset.AssetType.SERVICE,) or business_model == "service":
    formats = [ContentFormat.REEL, ContentFormat.STORY, ContentFormat.SINGLE_POST]
    if image_count >= 2:
      formats.append(ContentFormat.CAROUSEL)
    rationale_parts.append("service business → reel-first")
  elif asset_type in (BusinessAsset.AssetType.PROMOTION, BusinessAsset.AssetType.OFFER):
    formats = [ContentFormat.CAROUSEL, ContentFormat.STORY, ContentFormat.WHATSAPP_OFFER]
    rationale_parts.append("promotion → carousel + urgency")
  else:
    if image_count >= 2:
      formats.extend([ContentFormat.CAROUSEL, ContentFormat.REEL])
    elif image_count == 1:
      formats.append(ContentFormat.REEL)
    rationale_parts.append("product catalog → shop + motion")

  if limits.get("kling_reels_enabled") and fal_enabled():
    from apps.billing.models import get_effective_plan_tier
    tier = get_effective_plan_tier(profile or getattr(user, "profile", None))
    if is_transformation or business_model == "service":
      reel_backend = ReelBackend.KLING
      rationale_parts.append("Kling for transformation motion")
    elif image_count == 1 and tier in ("pro", "agency"):
      reel_backend = ReelBackend.KLING
      rationale_parts.append("Kling hero product reel (Pro+)")

  if limits.get("bannerbear_carousels_enabled") and bannerbear_enabled():
    if ContentFormat.CAROUSEL in formats:
      carousel_backend = CarouselBackend.BANNERBEAR
      rationale_parts.append("Bannerbear branded carousel")

  if limits.get("fal_flux_edits_per_month", 0) > 0 and fal_enabled():
    if asset_type in (BusinessAsset.AssetType.PROMOTION, BusinessAsset.AssetType.EVENT):
      enhancement = EnhancementBackend.FLUX_EDIT
      rationale_parts.append("Flux creative for promo/event")

  kling_prompt = f"{dna.kling_motion_hint()}. {dna.brand_name} brand."
  flux_prompt = f"Professional marketing creative, {dna.flux_style_suffix()}"

  if business_model == "product":
    scene_pack = "marketplace_white" if image_count == 1 else "brand_studio"

  return MediaPlan(
    formats=_dedupe_formats(formats),
    enhancement=enhancement,
    reel_backend=reel_backend,
    carousel_backend=carousel_backend,
    scene_pack=scene_pack,
    kling_prompt=kling_prompt.strip(),
    flux_edit_prompt=flux_prompt.strip(),
    rationale="; ".join(rationale_parts),
  )


def _dedupe_formats(formats: list[ContentFormat]) -> list[ContentFormat]:
  seen: set[ContentFormat] = set()
  out: list[ContentFormat] = []
  for fmt in formats:
    if fmt not in seen:
      seen.add(fmt)
      out.append(fmt)
  return out


def persist_media_plan(asset: BusinessAsset, plan: MediaPlan) -> None:
  metadata = dict(asset.metadata or {})
  metadata["media_plan"] = plan.to_metadata()
  asset.metadata = metadata
  asset.save(update_fields=["metadata", "updated_at"])
