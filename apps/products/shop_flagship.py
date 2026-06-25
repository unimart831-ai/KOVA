"""Flagship public shop layout — category rail, flash reels, promo banners, testimonials."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.utils.text import slugify

FLASH_BADGES = ("Flash sale", "Hot deal", "Limited drop", "New arrival", "Trending now")

CATEGORY_ICONS: dict[str, str] = {
    "phone": "📱",
    "smartphone": "📱",
    "laptop": "💻",
    "computer": "💻",
    "audio": "🎧",
    "headphone": "🎧",
    "gaming": "🎮",
    "game": "🎮",
    "wearable": "⌚",
    "watch": "⌚",
    "accessory": "🔌",
    "tv": "📺",
    "camera": "📷",
    "fashion": "👗",
    "clothing": "👕",
    "beauty": "💄",
    "food": "🍽️",
    "service": "✨",
    "digital": "⚡",
}


def _category_icon(name: str) -> str:
    blob = (name or "").lower()
    for key, icon in CATEGORY_ICONS.items():
        if key in blob:
            return icon
    return "🏷️"


def shop_category_nav(products_by_category: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Horizontal category chips for the flagship shop."""
    nav: list[dict[str, Any]] = [
        {"slug": "all", "name": "All", "count": 0, "icon": "🛍️", "anchor": "#shop-catalog"},
    ]
    total = 0
    for group in products_by_category or []:
        name = (group.get("name") or "Offers").strip()
        items = group.get("products") or []
        if not items:
            continue
        total += len(items)
        slug = slugify(name) or "offers"
        nav.append({
            "slug": slug,
            "name": name,
            "count": len(items),
            "icon": _category_icon(name),
            "anchor": f"#cat-{slug}",
        })
    if nav:
        nav[0]["count"] = total
    return nav if len(nav) > 1 else nav[:1]


def enrich_flash_reels(reels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark shop reels as flash-sale stories for the top strip."""
    out: list[dict[str, Any]] = []
    for i, reel in enumerate(reels or []):
        item = dict(reel)
        item["flash_badge"] = FLASH_BADGES[i % len(FLASH_BADGES)]
        item["flash_index"] = i
        out.append(item)
    return out


def shop_promo_banners(products: list, featured: list, *, reels: list | None = None) -> tuple[dict | None, dict | None]:
    """Two side-by-side promo banners from featured catalog + reels."""
    pool: list = []
    seen: set = set()

    for reel in reels or []:
        slug = reel.get("commerce_slug")
        if not slug:
            continue
        match = next((p for p in products if getattr(p, "commerce_slug", "") == slug), None)
        if match and match.pk not in seen:
            pool.append({
                "title": reel.get("product_name") or match.name,
                "subtitle": "Watch the reel — limited time offer",
                "price": reel.get("product_price") or getattr(match, "display_price", ""),
                "image": reel.get("poster_url") or getattr(match, "shop_hero_image_url", ""),
                "commerce_slug": slug,
                "cta": "Shop flash deal",
                "tone": "flash",
            })
            seen.add(match.pk)

    for product in featured or []:
        if product.pk in seen:
            continue
        image = getattr(product, "shop_hero_image_url", "") or ""
        if not image and getattr(product, "all_image_urls", None):
            image = product.all_image_urls[0]
        if not image:
            continue
        pool.append({
            "title": product.name,
            "subtitle": "Featured this week",
            "price": getattr(product, "display_price", "") or "",
            "image": image,
            "commerce_slug": product.commerce_slug,
            "cta": "Shop now",
            "tone": "featured",
        })
        seen.add(product.pk)

    for product in products or []:
        if product.pk in seen:
            continue
        image = getattr(product, "shop_hero_image_url", "") or ""
        if not image:
            continue
        pool.append({
            "title": product.name,
            "subtitle": "Customer favourite",
            "price": getattr(product, "display_price", "") or "",
            "image": image,
            "commerce_slug": product.commerce_slug,
            "cta": "View offer",
            "tone": "catalog",
        })
        seen.add(product.pk)
        if len(pool) >= 4:
            break

    left = pool[0] if len(pool) > 0 else None
    right = pool[1] if len(pool) > 1 else None
    return left, right


def shop_hero_collage(products: list, featured: list, *, limit: int = 4) -> list[dict[str, str]]:
    """Floating product images for the flagship hero."""
    collage: list[dict[str, str]] = []
    seen: set = set()
    for product in (featured or []) + (products or []):
        if product.pk in seen:
            continue
        image = getattr(product, "shop_hero_image_url", "") or ""
        if not image and getattr(product, "all_image_urls", None):
            image = product.all_image_urls[0]
        if not image:
            continue
        collage.append({
            "name": product.name,
            "image": image,
            "price": getattr(product, "display_price", "") or "",
            "commerce_slug": product.commerce_slug,
        })
        seen.add(product.pk)
        if len(collage) >= limit:
            break
    return collage


def shop_public_testimonials(user, *, limit: int = 3) -> list[dict[str, str]]:
    """Published testimonial assets for social proof on the shop."""
    from apps.products.models import BusinessAsset

    rows = (
        BusinessAsset.objects.filter(
            user=user,
            asset_type=BusinessAsset.AssetType.TESTIMONIAL,
            status=BusinessAsset.Status.PUBLISHED,
        )
        .order_by("-updated_at")[:limit]
    )
    out: list[dict[str, str]] = []
    for asset in rows:
        meta = asset.metadata or {}
        quote_text = (meta.get("quote") or asset.description or asset.title or "").strip()
        if not quote_text:
            continue
        out.append({
            "quote": quote_text[:280],
            "name": (meta.get("client") or meta.get("author") or "Happy customer")[:80],
            "location": (meta.get("location") or meta.get("city") or "")[:80],
            "rating": int(meta.get("rating") or 5),
        })
    return out


def product_whatsapp_order_url(product, brand: str, profile, user, *, request=None) -> str:
    """Per-product tracked WhatsApp order link for grid cards."""
    if not product:
        return ""
    from apps.products.commerce_checkout import tracked_whatsapp_order_url

    return tracked_whatsapp_order_url(
        user, profile, brand, product=product, request=request, source="shop",
    )


def attach_product_wa_urls(products: list, brand: str, profile, user, *, request=None) -> None:
    """Mutate products in-place with wa_order_url for templates."""
    for product in products:
        product.wa_order_url = product_whatsapp_order_url(
            product, brand, profile, user, request=request,
        )
