"""Public shop reels — surface autopilot product reels on commerce pages."""

from __future__ import annotations

from typing import Any

from apps.content.models import Post

PUBLIC_REEL_STATUSES = (
    Post.Status.PENDING_APPROVAL,
    Post.Status.APPROVED,
    Post.Status.SCHEDULED,
    Post.Status.PUBLISHED,
)

DEFAULT_SHOP_REEL_LIMIT = 8


def _reel_card(post: Post) -> dict[str, Any] | None:
    product = post.product
    if not product or not product.is_active or not product.commerce_slug:
        return None
    if not post.reel_has_video:
        return None

    video_url = post.reel_video_url
    if not video_url:
        return None

    return {
        "post_id": str(post.pk),
        "video_url": video_url,
        "poster_url": post.reel_thumbnail_url or "",
        "product_name": product.name,
        "product_price": product.display_price,
        "commerce_slug": product.commerce_slug,
    }


def get_public_shop_reels(profile, *, limit: int = DEFAULT_SHOP_REEL_LIMIT) -> list[dict[str, Any]]:
    """Latest ready product reels for a public shop index (one per product, newest first)."""
    posts = (
        Post.objects.filter(
            user=profile.user,
            post_format=Post.PostFormat.REEL,
            status__in=PUBLIC_REEL_STATUSES,
            product__is_active=True,
        )
        .exclude(product__commerce_slug="")
        .select_related("product")
        .order_by("-created_at")[: limit * 4]
    )

    reels: list[dict[str, Any]] = []
    seen_products: set = set()

    for post in posts:
        card = _reel_card(post)
        if not card:
            continue
        product_id = post.product_id
        if product_id in seen_products:
            continue
        seen_products.add(product_id)
        reels.append(card)
        if len(reels) >= limit:
            break

    return reels


def get_public_product_reel(product) -> dict[str, Any] | None:
    """Best ready reel for a single product commerce page."""
    if not product or not product.is_active:
        return None

    posts = (
        Post.objects.filter(
            user=product.user,
            product=product,
            post_format=Post.PostFormat.REEL,
            status__in=PUBLIC_REEL_STATUSES,
        )
        .select_related("product")
        .order_by("-created_at")[:12]
    )

    for post in posts:
        card = _reel_card(post)
        if card:
            return card
    return None
