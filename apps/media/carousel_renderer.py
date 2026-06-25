"""
Carousel renderer abstraction — V1 Bannerbear/Pillow, V2 HTML screenshot (stub).

Do not tightly couple campaign carousel output to a single provider.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from apps.media.carousel_strategy import CarouselStrategy
from apps.media.media_provider_config import get_media_provider_config

logger = logging.getLogger(__name__)


class CarouselRenderer(ABC):
    """Render CarouselStrategy → list of image URLs."""

    backend_name: str = "abstract"

    @abstractmethod
    def render(
        self,
        post,
        product,
        strategy: CarouselStrategy,
        *,
        key_features: list | None = None,
        analysis: dict | None = None,
    ) -> list[str]:
        ...


class BannerbearCarouselRenderer(CarouselRenderer):
    backend_name = "bannerbear"

    def render(self, post, product, strategy, *, key_features=None, analysis=None):
        from apps.media.bannerbear_client import build_product_carousel_slides
        from apps.media.brand_dna import resolve_brand_dna

        dna = resolve_brand_dna(post.user)
        urls = build_product_carousel_slides(product, dna, key_features=key_features or [])
        if urls:
            return urls
        return []


class PillowCarouselRenderer(CarouselRenderer):
    backend_name = "pillow"

    def render(self, post, product, strategy, *, key_features=None, analysis=None):
        from apps.agents.carousel import generate_product_carousel

        slides = strategy.to_carousel_slides()
        post.carousel_slides = slides
        post.save(update_fields=["carousel_slides", "updated_at"])
        return generate_product_carousel(
            post,
            product,
            key_features=key_features,
            analysis=analysis or {},
            closing_cta=strategy.slides[-1].heading if strategy.slides else "Shop Now",
        )


class HtmlScreenshotCarouselRenderer(CarouselRenderer):
    """
    V2 path: Carousel JSON → HTML → screenshot engine → PNG.

    Stub for Phase 3 architecture — returns empty until screenshot service ships.
    """

    backend_name = "html_screenshot"

    def render(self, post, product, strategy, *, key_features=None, analysis=None):
        logger.info(
            "HtmlScreenshotCarouselRenderer: stub — strategy %s (%d slides)",
            strategy.type, len(strategy.slides),
        )
        return []


def pick_carousel_renderer(user, plan=None) -> CarouselRenderer:
    from apps.media.router import pick_carousel_backend

    backend = pick_carousel_backend(user, plan)
    config = get_media_provider_config()

    if backend.value == "bannerbear" and config.bannerbear_ready:
        return BannerbearCarouselRenderer()
    # V2: if settings.CAROUSEL_HTML_RENDERER_ENABLED: return HtmlScreenshotCarouselRenderer()
    return PillowCarouselRenderer()


def render_carousel_from_strategy(
    post,
    product,
    strategy: CarouselStrategy,
    *,
    key_features: list | None = None,
    analysis: dict | None = None,
) -> list[str]:
    """Campaign-driven carousel render entry point."""
    plan = None
    try:
        asset = product.business_asset
        from apps.media.content_types import MediaPlan

        plan = MediaPlan.from_metadata((asset.metadata or {}).get("media_plan"))
    except Exception:
        pass

    renderer = pick_carousel_renderer(post.user, plan)
    urls = renderer.render(
        post, product, strategy,
        key_features=key_features,
        analysis=analysis,
    )
    if urls:
        meta = dict(post.visual_metadata or {})
        meta["carousel_backend"] = renderer.backend_name
        meta["carousel_strategy"] = strategy.to_dict()
        meta["carousel_slides"] = urls
        post.visual_metadata = meta
        post.save(update_fields=["visual_metadata", "updated_at"])
    return urls
