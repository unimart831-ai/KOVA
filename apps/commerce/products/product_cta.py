"""Resolve buy links for products — Kova Commerce vs external URLs."""

from __future__ import annotations

from django.conf import settings


def marketplace_partner_for(product):
    """Marketplace partner FK removed — always None in V1."""
    return None


def uses_marketplace_cta(product) -> bool:
    return False


def _absolute_url(path: str, request=None) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    if site:
        return f"{site}{path}" if path.startswith("/") else f"{site}/{path}"
    return path


def resolve_booking_cta_url(product, request=None) -> str:
    """Service CTAs: fulfillment_url → product_url (no BookingLink)."""
    return (
        (getattr(product, "fulfillment_url", "") or "").strip()
        or (getattr(product, "product_url", "") or "").strip()
    )


def resolve_direct_offer_action_url(product, request=None) -> str:
    """Best direct fulfillment URL without falling back to the Kova commerce page."""
    offering_type = getattr(product, "offering_type", "product")
    if offering_type == "service":
        return resolve_booking_cta_url(product, request)
    if offering_type == "digital":
        return (
            (getattr(product, "fulfillment_url", "") or "").strip()
            or (product.product_url or "").strip()
        )
    return ""


def resolve_product_cta_url(product, request=None) -> str:
    """
    Primary offer link for social captions, first comments, and promotion copy.
    """
    direct_url = resolve_direct_offer_action_url(product, request)
    if direct_url:
        return direct_url

    from apps.commerce.products.commerce_links import commerce_link_url

    commerce_url = commerce_link_url(product, request)
    if commerce_url:
        return commerce_url
    return (product.product_url or "").strip()


def resolve_commerce_page_url(product, request=None) -> str:
    """Public Kova shop page — used for M-Pesa/WhatsApp even when CTA is external."""
    from apps.commerce.products.commerce_links import commerce_link_url

    return commerce_link_url(product, request)


def cta_label_for(product) -> str:
    if getattr(product, "offering_type", "product") == "service":
        return "Book / inquire"
    if getattr(product, "offering_type", "product") == "digital":
        return "Access link"
    return "Kova shop"


def public_action_heading_for(product) -> str:
    offering_type = getattr(product, "offering_type", "product")
    if offering_type == "service":
        return "Book this service"
    if offering_type == "digital":
        return "Get this digital offer"
    return "Get this product"


def primary_action_label_for(product) -> str:
    offering_type = getattr(product, "offering_type", "product")
    if offering_type == "service":
        return "Book now"
    if offering_type == "digital":
        return "Get instant access"
    return "Buy now"
