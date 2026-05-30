"""
Catalog showcase — one carousel + reel promoting multiple in-stock products.

Each product slide uses name + price (image optional). Out-of-stock physical
products are excluded. Weekly runs rotate which products appear when the
catalog exceeds the Instagram carousel slide cap.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Title + up to 8 product slides + closing CTA (Instagram max 10)
MAX_PRODUCT_SLIDES = 8


def catalog_showcase_allowed(user) -> bool:
    profile = getattr(user, "profile", None)
    return not (profile and profile.emergency_pause)


def promotable_catalog_queryset(user):
    """Active products safe to promote (excludes out-of-stock physical)."""
    from apps.products.models import Product

    return Product.objects.promotable(user).select_related("category").order_by(
        "-is_featured", "-updated_at", "name"
    )


def select_products_for_showcase(user, *, limit: int = MAX_PRODUCT_SLIDES):
    """
    Pick up to `limit` products for this showcase. Rotates by ISO week when
    the catalog is larger than the slide cap.
    """
    all_promotable = list(promotable_catalog_queryset(user))
    if not all_promotable:
        return []

    if len(all_promotable) <= limit:
        return all_promotable

    week = timezone.now().isocalendar()[1]
    start = week % len(all_promotable)
    selected = []
    for i in range(limit):
        selected.append(all_promotable[(start + i) % len(all_promotable)])
    return selected


def build_catalog_showcase_caption(user, products) -> str:
    profile = getattr(user, "profile", None)
    brand = (getattr(profile, "company_name", None) or "").strip() or "Our shop"

    lines = [f"🛍️ {brand} — what's in stock"]
    for product in products:
        line = f"• {product.name}"
        if product.display_price:
            line += f" — {product.display_price}"
        lines.append(line)

    more = promotable_catalog_queryset(user).count() - len(products)
    if more > 0:
        lines.append(f"\n+ {more} more in our catalog — swipe for prices 👉")
    else:
        lines.append("\nSwipe through for prices 👉")

    from apps.products.product_cta import resolve_product_cta_url

    shop_urls = []
    for product in products[:3]:
        url = resolve_product_cta_url(product)
        if url and url not in shop_urls:
            shop_urls.append(url)
    if shop_urls:
        lines.append("\n🛒 " + shop_urls[0])

    return "\n".join(lines)


def weekly_showcase_due(profile) -> bool:
    if not profile or not profile.catalog_showcase_weekly:
        return False
    last = profile.catalog_showcase_last_at
    if not last:
        return True
    return timezone.now() - last >= timedelta(days=7)


def mark_showcase_run(profile):
    if not profile:
        return
    profile.catalog_showcase_last_at = timezone.now()
    profile.save(update_fields=["catalog_showcase_last_at", "updated_at"])
