"""Resolve buy links for products — Kova Commerce vs marketplace URLs."""

from __future__ import annotations


def marketplace_partner_for(product):
    if getattr(product, "marketplace_partner_id", None) and product.marketplace_partner:
        return product.marketplace_partner
    return None


def uses_marketplace_cta(product) -> bool:
    """True when captions should link to the external marketplace listing."""
    mp = marketplace_partner_for(product)
    if not mp or not mp.enforce_marketplace_cta:
        return False
    return bool((product.product_url or "").strip())


def resolve_product_cta_url(product, request=None) -> str:
    """
    Primary buy link for social captions, first comments, and promotion copy.
    Marketplace partners with enforce_marketplace_cta keep their listing URL.
    """
    if uses_marketplace_cta(product):
        return (product.product_url or "").strip()

    from apps.products.commerce_links import commerce_link_url

    commerce_url = commerce_link_url(product, request)
    if commerce_url:
        return commerce_url
    return (product.product_url or "").strip()


def resolve_commerce_page_url(product, request=None) -> str:
    """Public Kova shop page — used for M-Pesa/WhatsApp even when CTA is external."""
    from apps.products.commerce_links import commerce_link_url

    return commerce_link_url(product, request)


def cta_label_for(product) -> str:
    if uses_marketplace_cta(product):
        mp = marketplace_partner_for(product)
        return mp.name if mp else "Shop"
    return "Kova shop"
