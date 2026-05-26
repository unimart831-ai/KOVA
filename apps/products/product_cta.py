"""Resolve buy links for products — Kova Commerce vs marketplace URLs."""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse


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
    booking_link = getattr(product, "booking_link", None)
    if not booking_link and getattr(product, "user_id", None):
        booking_link = product.user.booking_links.filter(is_active=True).first()
    if not booking_link or not booking_link.is_active:
        return ""

    path = reverse("bookings:public_book", kwargs={"slug": booking_link.slug})
    params = {"src": "commerce"}
    if getattr(product, "name", ""):
        params["service"] = product.name
    return _absolute_url(f"{path}?{urlencode(params)}", request)


def resolve_direct_offer_action_url(product, request=None) -> str:
    """Best direct fulfillment URL without falling back to the Kova commerce page."""
    if uses_marketplace_cta(product):
        return (product.product_url or "").strip()

    offering_type = getattr(product, "offering_type", "product")
    if offering_type == "service":
        return (
            (getattr(product, "fulfillment_url", "") or "").strip()
            or resolve_booking_cta_url(product, request)
            or (product.product_url or "").strip()
        )
    if offering_type == "digital":
        return (
            (getattr(product, "fulfillment_url", "") or "").strip()
            or (product.product_url or "").strip()
        )
    return ""


def resolve_product_cta_url(product, request=None) -> str:
    """
    Primary offer link for social captions, first comments, and promotion copy.
    Marketplace partners with enforce_marketplace_cta keep their listing URL.
    """
    direct_url = resolve_direct_offer_action_url(product, request)
    if direct_url:
        return direct_url

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
    if getattr(product, "offering_type", "product") == "service":
        return "Booking page"
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
    if uses_marketplace_cta(product):
        mp = marketplace_partner_for(product)
        return f"Open on {mp.name}" if mp else "Open listing"
    return "Buy now"
