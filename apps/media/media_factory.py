"""
Media Factory — campaign-driven media production orchestrator.

Pipeline: Business DNA → Brand DNA → Asset → Seed → Campaign → Media Factory → QA

No media generation outside this campaign pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MEDIA_FACTORY_META_KEY = "media_factory"


def prepare_campaign_media_factory(seed, campaign=None) -> dict[str, Any]:
    """
    Build and persist CampaignVisualBrief, CarouselStrategy, ReelStrategy
    before Create Agent / Photoroom / carousel / reel pipelines run.
    """
    from apps.media.campaign_visual_brief import (
        build_campaign_visual_brief,
        persist_visual_brief,
    )
    from apps.media.carousel_strategy import build_carousel_strategy
    from apps.media.reel_strategy import build_reel_strategy
    from apps.media.media_provider_config import get_media_provider_config

    if campaign is None:
        campaign = getattr(seed, "marketing_campaign", None)

    visual_brief = build_campaign_visual_brief(seed, campaign)
    carousel_strategy = build_carousel_strategy(seed, campaign)
    reel_strategy = build_reel_strategy(seed, campaign)
    provider_config = get_media_provider_config()

    factory_payload = {
        "visual_brief": visual_brief.to_dict(),
        "carousel_strategy": carousel_strategy.to_dict(),
        "reel_strategy": reel_strategy.to_dict(),
        "provider_status": provider_config.to_dict(),
        "max_scenes_per_campaign": len(visual_brief.scenes),
    }

    # Persist on campaign
    if campaign:
        meta = dict(campaign.proposal_meta or {})
        meta[MEDIA_FACTORY_META_KEY] = factory_payload
        meta["visual_brief"] = visual_brief.to_dict()
        meta["carousel_strategy"] = carousel_strategy.to_dict()
        meta["reel_strategy"] = reel_strategy.to_dict()
        campaign.proposal_meta = meta
        campaign.save(update_fields=["proposal_meta", "updated_at"])
        persist_visual_brief(campaign, visual_brief)

    # Mirror on seed blueprint for Create Agent prompts
    blueprint = dict(getattr(seed, "blueprint", None) or {})
    blueprint["visual_brief"] = visual_brief.to_dict()
    blueprint["carousel_strategy"] = carousel_strategy.to_dict()
    blueprint["reel_strategy"] = reel_strategy.to_dict()
    blueprint[MEDIA_FACTORY_META_KEY] = factory_payload
    seed.blueprint = blueprint
    seed.save(update_fields=["blueprint", "updated_at"])

    logger.info(
        "Media factory prepared for seed %s: scenes=%d carousel=%s reel_hook=%s",
        seed.pk,
        len(visual_brief.scenes),
        carousel_strategy.type,
        reel_strategy.hook[:40],
    )

    _trigger_campaign_visual_production(seed, campaign, visual_brief)

    return factory_payload


def _trigger_campaign_visual_production(seed, campaign, visual_brief) -> None:
    """Run Photoroom polish when campaign has a product hero — brief-driven."""
    product = getattr(seed, "product", None)
    if not product or not getattr(product, "image", None):
        return
    from apps.products.photo_variations import variation_storage_marker

    marker = variation_storage_marker(product.pk)
    existing = [
        u for u in (product.additional_images or [])
        if marker in (u or "")
    ]
    if len(existing) >= 3:
        return

    try:
        from apps.products.tasks import expand_product_photo_set
        from apps.utils import fire_task

        fire_task(
            expand_product_photo_set,
            str(product.pk),
            commerce_source="campaign",
            seed_id=str(seed.pk),
        )
    except Exception as exc:
        logger.warning("Campaign visual production dispatch failed: %s", exc)


def get_media_factory_payload(seed) -> dict[str, Any]:
    campaign = getattr(seed, "marketing_campaign", None)
    if campaign:
        meta = campaign.proposal_meta or {}
        if meta.get(MEDIA_FACTORY_META_KEY):
            return meta[MEDIA_FACTORY_META_KEY]
        if meta.get("visual_brief"):
            return meta
    blueprint = getattr(seed, "blueprint", None) or {}
    return blueprint.get(MEDIA_FACTORY_META_KEY) or {}


def media_factory_prompt_section(seed) -> str:
    """Inject carousel + reel strategy into Create Agent prompt."""
    from apps.media.carousel_strategy import (
        CarouselStrategy,
        carousel_strategy_prompt_section,
    )

    payload = get_media_factory_payload(seed)
    lines = ["### MEDIA FACTORY (campaign-driven production)"]
    lines.append(
        "All visuals must align with the campaign brief. "
        "Do not invent ad-hoc image prompts outside the strategy."
    )
    cs_data = payload.get("carousel_strategy") or (seed.blueprint or {}).get("carousel_strategy")
    strategy = CarouselStrategy.from_dict(cs_data)
    if strategy:
        lines.append(carousel_strategy_prompt_section(strategy))

    rs = payload.get("reel_strategy") or (seed.blueprint or {}).get("reel_strategy")
    if rs and isinstance(rs, dict):
        lines.append(
            f"### REEL STRATEGY\nHook: {rs.get('hook', '')}\n"
            f"Objective: {rs.get('objective', 'sales')}\n"
            f"Scenes: {', '.join(s.get('type', '') for s in (rs.get('scenes') or []) if isinstance(s, dict))}"
        )
    return "\n".join(lines)


def apply_reel_strategy_to_post(post, seed) -> None:
    """Merge campaign reel strategy into post visual_metadata before compose."""
    from apps.media.reel_strategy import ReelStrategy, reel_strategy_to_compose_metadata

    payload = get_media_factory_payload(seed)
    rs_data = payload.get("reel_strategy") or (seed.blueprint or {}).get("reel_strategy")
    strategy = ReelStrategy.from_dict(rs_data)
    if not strategy:
        return
    meta = dict(post.visual_metadata or {})
    meta.update(reel_strategy_to_compose_metadata(strategy))
    post.visual_metadata = meta
    post.save(update_fields=["visual_metadata", "updated_at"])
