"""
Use Photoroom-polished product photos for carousel and reel posts.

When a post is tied to a product with studio polish, skip FLUX / image_gen —
real polished assets are always better than synthetic fallbacks.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def analysis_for_post(post) -> dict:
    """Best-effort vision / snap analysis for carousel copy."""
    product = getattr(post, "product", None)
    if not product:
        return {}
    meta = getattr(product, "marketplace_metadata", None) or {}
    analysis = meta.get("snap_analysis") or meta.get("vision_analysis") or {}
    if isinstance(analysis, dict):
        return analysis
    return {}


def polished_carousel_sources(product, *, max_images: int = 5) -> list[str]:
    from apps.content.carousel_studio import curate_carousel_images

    raw = list(product.carousel_image_urls or [])
    if not raw:
        raw = [u for u in (product.all_image_urls or []) if u]
    return curate_carousel_images(raw, max_images=max_images)


def polished_reel_sources(product) -> list[str]:
    from apps.content.tasks import _normalize_reel_image_source
    from apps.products.reel_curation import curate_reel_image_urls

    urls = polished_carousel_sources(product, max_images=5)
    sources: list[str] = []
    for url in curate_reel_image_urls(urls):
        normalized = _normalize_reel_image_source(url)
        if normalized:
            sources.append(normalized)
    return sources


def apply_polished_carousel_post(
    post,
    product,
    *,
    key_features: list | None = None,
    analysis: dict | None = None,
) -> bool:
    from apps.media.carousel_bridge import generate_branded_carousel_urls

    if not polished_carousel_sources(product):
        return False

    urls = generate_branded_carousel_urls(
        post,
        product,
        key_features=key_features or [],
        analysis=analysis or analysis_for_post(post),
    )
    if urls:
        logger.info(
            "Applied polished carousel (%d slides) to post %s (product %s)",
            len(urls),
            post.pk,
            product.pk,
        )
        return True
    return False


def apply_polished_reel_post(post, product) -> bool:
    from apps.content.models import Post
    from apps.content.tasks import _queue_reel_compose

    sources = polished_reel_sources(product)
    if not sources:
        return False

    meta = dict(post.visual_metadata or {})
    meta["source_images"] = sources
    meta.setdefault("reel_template", "story_arc")
    meta["visual_strategy"] = meta.get("visual_strategy") or "carousel"
    meta["prefer_photoroom_video"] = len(sources) == 1
    if len(sources) >= 2:
        meta["reel_compose_backend"] = "ffmpeg"
    post.visual_metadata = meta
    post.media_urls = sources
    post.aspect_ratio = Post.AspectRatio.STORY
    post.media_status = Post.MediaStatus.GENERATED
    post.save(
        update_fields=[
            "visual_metadata",
            "media_urls",
            "aspect_ratio",
            "media_status",
            "updated_at",
        ]
    )
    _queue_reel_compose(str(post.pk))
    logger.info(
        "Applied polished reel sources (%d frames) to post %s (product %s)",
        len(sources),
        post.pk,
        product.pk,
    )
    return True


def try_apply_product_polished_media(post) -> bool:
    """
    Populate carousel or reel from product polish when possible.
    Returns True when media is ready (no FLUX needed).
    """
    from apps.content.models import Post

    product = getattr(post, "product", None)
    if not product or not product_has_polished_gallery(product):
        return False

    fmt = post.post_format or Post.PostFormat.TEXT
    if fmt == Post.PostFormat.CAROUSEL:
        return apply_polished_carousel_post(post, product, analysis=analysis_for_post(post))
    if fmt in (Post.PostFormat.REEL, Post.PostFormat.STORY):
        return apply_polished_reel_post(post, product)
    return False


def refresh_product_polished_posts(product) -> int:
    """
    After studio polish finishes, fix carousel/reel posts that failed FLUX
    or were created before polish assets existed.
    """
    from apps.content.models import Post
    from django.db.models import Q

    if not product_has_polished_gallery(product):
        return 0

    candidates = Post.objects.filter(
        product=product,
        post_format__in=(
            Post.PostFormat.CAROUSEL,
            Post.PostFormat.REEL,
            Post.PostFormat.STORY,
        ),
    ).filter(
        Q(media_status__in=(
            Post.MediaStatus.FAILED,
            Post.MediaStatus.PENDING,
            Post.MediaStatus.NONE,
        ))
        | Q(media_urls=[])
        | Q(media_urls__isnull=True)
    )

    updated = 0
    for post in candidates.iterator():
        if try_apply_product_polished_media(post):
            updated += 1
    updated += refresh_product_reel_compose(product)
    if updated:
        logger.info(
            "Refreshed polished media on %d post(s) for product %s",
            updated,
            product.pk,
        )
    return updated


def refresh_product_reel_compose(product) -> int:
    """
    Re-queue reel compose when the product gallery grew (e.g. after async scene expand).
    """
    from apps.content.models import Post

    sources = polished_reel_sources(product)
    if len(sources) < 2:
        return 0

    queued = 0
    for post in Post.objects.filter(
        product=product,
        post_format=Post.PostFormat.REEL,
    ).iterator():
        meta = dict(post.visual_metadata or {})
        existing = meta.get("source_images") or []
        if len(existing) >= len(sources):
            continue
        meta["source_images"] = sources
        meta["prefer_photoroom_video"] = False
        meta["reel_compose_backend"] = "ffmpeg"
        meta.pop("reel_video_url", None)
        meta["video_compose_status"] = "pending"
        post.visual_metadata = meta
        post.media_urls = sources
        post.save(update_fields=["visual_metadata", "media_urls", "updated_at"])
        from apps.content.tasks import _queue_reel_compose

        _queue_reel_compose(str(post.pk))
        queued += 1
    if queued:
        logger.info(
            "Re-queued reel compose on %d post(s) for product %s (%d frames)",
            queued,
            product.pk,
            len(sources),
        )
    return queued


def product_has_polished_gallery(product) -> bool:
    """True when polish produced usable square/studio assets (not just raw upload)."""
    if not product:
        return False
    urls = polished_carousel_sources(product, max_images=1)
    if urls:
        return True
    extras = product.additional_images or []
    markers = (
        "studio_polish",
        "studio_white",
        "studio_brand",
        "ai_scene_",
        "edit_ai_",
        "virtual_model",
        "ghost_mannequin",
    )
    return any(
        any(m in (u or "").lower() for m in markers)
        for u in extras
    )
