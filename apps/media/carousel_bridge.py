"""Carousel bridge — Bannerbear first, local graphics fallback."""

from __future__ import annotations

import logging

from apps.media.bannerbear_client import build_product_carousel_slides
from apps.media.brand_dna import resolve_brand_dna
from apps.media.content_types import MediaPlan
from apps.media.router import pick_carousel_backend

logger = logging.getLogger(__name__)


def generate_branded_carousel_urls(
  post,
  product,
  *,
  key_features: list | None = None,
  analysis: dict | None = None,
) -> list[str]:
  """
  Try Bannerbear branded slides; fall back to local generate_product_carousel.
  Uses Campaign CarouselStrategy when available on the post's seed.
  """
  from apps.agents.carousel import generate_product_carousel
  from apps.media.carousel_strategy import CarouselStrategy

  plan = None
  strategy = None
  try:
    if getattr(post, "seed_id", None):
      blueprint = getattr(post.seed, "blueprint", None) or {}
      cs = blueprint.get("carousel_strategy")
      if not cs and getattr(post.seed, "marketing_campaign", None):
        cs = (post.seed.marketing_campaign.proposal_meta or {}).get("carousel_strategy")
      strategy = CarouselStrategy.from_dict(cs)
  except Exception:
    pass

  if strategy and strategy.slides:
    from apps.media.carousel_renderer import render_carousel_from_strategy

    urls = render_carousel_from_strategy(
      post, product, strategy, key_features=key_features, analysis=analysis,
    )
    if urls:
      return urls

  try:
    asset = product.business_asset
    plan = MediaPlan.from_metadata((asset.metadata or {}).get("media_plan"))
  except Exception:
    pass

  backend = pick_carousel_backend(post.user, plan)
  if backend.value == "bannerbear":
    dna = resolve_brand_dna(post.user)
    urls = build_product_carousel_slides(product, dna, key_features=key_features)
    if urls:
      meta = dict(post.visual_metadata or {})
      meta["carousel_backend"] = "bannerbear"
      meta["carousel_slides"] = urls
      post.visual_metadata = meta
      post.save(update_fields=["visual_metadata", "updated_at"])
      return urls
    logger.info("Bannerbear carousel empty for product %s — falling back to local", product.pk)

  return generate_product_carousel(
    post,
    product,
    key_features=key_features,
    analysis=analysis or {},
    closing_cta="Shop Now",
  )
