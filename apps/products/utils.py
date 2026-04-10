"""
Product context utilities for agent prompt injection.

Every agent gets enriched with product data so content is aligned
with what the business actually sells and stocks.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_product_context(user) -> str:
    """
    Build a formatted product catalog summary for injection into agent prompts.
    Returns empty string if user has no products.
    Cached for 5 minutes to avoid repeated DB queries per agent call.
    """
    cache_key = f"product_context:{user.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.products.models import Product

    products = Product.objects.filter(user=user, is_active=True).select_related("category").order_by(
        "-is_featured", "stock_status", "name"
    )[:50]

    if not products:
        cache.set(cache_key, "", 300)
        return ""

    in_stock = []
    low_stock = []
    out_of_stock = []
    featured = []

    for p in products:
        line = f"• {p.name}"
        if p.display_price:
            line += f" — {p.display_price}"
        if p.is_featured:
            line += " [FEATURED]"
        if p.quantity is not None:
            line += f" [{p.quantity} units]"
        if p.category:
            line += f" ({p.category.name})"

        if p.stock_status == Product.StockStatus.OUT_OF_STOCK:
            out_of_stock.append(line)
        elif p.stock_status == Product.StockStatus.LOW_STOCK:
            low_stock.append(line)
        else:
            in_stock.append(line)

        if p.is_featured:
            featured.append(p.name)

    parts = ["## PRODUCT CATALOG"]
    parts.append("The business sells these products/services. Use this data to create relevant content.\n")

    if in_stock:
        parts.append("**IN STOCK (promote these):**")
        parts.extend(in_stock)
        parts.append("")

    if low_stock:
        parts.append("**LOW STOCK (create urgency/scarcity content):**")
        parts.extend(low_stock)
        parts.append("")

    if out_of_stock:
        parts.append("**OUT OF STOCK (DO NOT promote — redirect to alternatives):**")
        parts.extend(out_of_stock)
        parts.append("")

    if featured:
        parts.append(f"**FEATURED (push harder):** {', '.join(featured)}")
        parts.append("")

    parts.append("RULES:")
    parts.append("- NEVER create content promoting out-of-stock products.")
    parts.append("- For low-stock items, use urgency language ('limited stock', 'almost gone').")
    parts.append("- Prioritize featured products in content when relevant.")
    parts.append("- Reference real prices and product names — don't make them up.")

    result = "\n".join(parts)
    cache.set(cache_key, result, 300)
    return result


def get_product_brief_data(user) -> dict:
    """
    Gather product data for the Daily Brief.
    Returns a summary dict that the LLM uses to generate the product section.
    """
    from apps.products.models import Product, StockAlert

    products = Product.objects.filter(user=user, is_active=True)
    if not products.exists():
        return {}

    in_stock_count = products.filter(stock_status=Product.StockStatus.IN_STOCK).count()
    low_stock = list(
        products.filter(stock_status=Product.StockStatus.LOW_STOCK)
        .values_list("name", "quantity")[:5]
    )
    out_of_stock = list(
        products.filter(stock_status=Product.StockStatus.OUT_OF_STOCK)
        .values_list("name", flat=True)[:5]
    )
    featured = list(
        products.filter(is_featured=True)
        .values_list("name", flat=True)[:5]
    )
    unread_alerts = list(
        StockAlert.objects.filter(user=user, is_read=False)
        .values_list("message", flat=True)[:5]
    )

    return {
        "total_products": products.count(),
        "in_stock": in_stock_count,
        "low_stock_items": [{"name": name, "quantity": qty} for name, qty in low_stock],
        "out_of_stock_items": out_of_stock,
        "featured_items": featured,
        "unread_alerts": unread_alerts,
    }


def invalidate_product_cache(user):
    """Call this after any product update to clear the cached context."""
    cache.delete(f"product_context:{user.pk}")
