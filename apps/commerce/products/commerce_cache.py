"""Redis-backed cache helpers for public commerce pages."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Max

SHOP_AUX_TTL = 120
BRANDING_TTL = 300


def shop_aux_cache_key(page_slug: str, user_id) -> str:
    from apps.commerce.products.models import Product

    agg = (
        Product.objects.filter(user_id=user_id, is_active=True)
        .exclude(commerce_slug="")
        .aggregate(c=Count("id"), m=Max("updated_at"))
    )
    profile_ts = ""
    try:
        from apps.core.accounts.models import UserProfile

        profile = UserProfile.objects.filter(user_id=user_id).only("updated_at").first()
        if profile and profile.updated_at:
            profile_ts = profile.updated_at.isoformat()
    except Exception:
        pass
    prod_ts = agg["m"].isoformat() if agg["m"] else "0"
    return f"commerce:shop:aux:{page_slug}:{agg['c']}:{prod_ts}:{profile_ts}"


def get_shop_auxiliary(profile, user, page_slug: str) -> dict | None:
    return cache.get(shop_aux_cache_key(page_slug, user.pk))


def set_shop_auxiliary(profile, user, page_slug: str, data: dict) -> None:
    cache.set(shop_aux_cache_key(page_slug, user.pk), data, SHOP_AUX_TTL)


def load_shop_auxiliary(profile, user, page_slug: str) -> dict:
    """Expensive shop-index lookups — cached briefly, invalidated on catalog change."""
    cached = get_shop_auxiliary(profile, user, page_slug)
    if cached is not None:
        return cached

    from apps.commerce.products.commerce_gallery import get_published_media_gallery
    from apps.commerce.products.commerce_reels import get_public_shop_reels
    from apps.commerce.products.shop_flagship import shop_public_testimonials
    from apps.commerce.products.storefront import portfolio_items_for_shop

    data = {
        "shop_reels": get_public_shop_reels(profile),
        "media_gallery": get_published_media_gallery(user),
        "shop_testimonials": shop_public_testimonials(user),
        "portfolio_items": portfolio_items_for_shop(user),
    }
    set_shop_auxiliary(profile, user, page_slug, data)
    return data


def get_commerce_branding_cached(user, profile) -> dict:
    key = f"commerce:branding:{user.pk}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    from apps.core.accounts.access import get_commerce_branding

    branding = get_commerce_branding(user, profile)
    cache.set(key, branding, BRANDING_TTL)
    return branding
