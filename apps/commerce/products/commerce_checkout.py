"""WhatsApp-first checkout helpers for public commerce and campaign pages."""

from __future__ import annotations

from urllib.parse import quote


def build_product_order_wa_text(
    product,
    brand: str,
    *,
    request=None,
    campaign_title: str = "",
    source_label: str = "Kova shop",
) -> str:
    """Pre-filled WhatsApp message for a product order."""
    name = (getattr(product, "name", None) or "").strip()
    price = (getattr(product, "display_price", None) or "").strip()
    lines = [f"Hi {brand}! I'd like to order:"]
    if campaign_title:
        lines.append(f"📣 {campaign_title}")
    if name:
        item = f"• {name}"
        if price:
            item += f" — {price}"
        lines.append(item)
    elif campaign_title and not name:
        if price:
            lines.append(f"• Offer — {price}")
    lines.append("")
    lines.append("Please confirm availability and how to pay.")
    if source_label:
        lines.append(f"(via {source_label})")
    return "\n".join(lines)


def build_campaign_order_wa_text(campaign, product, brand: str, *, request=None) -> str:
    """Pre-filled WhatsApp message from a campaign landing page."""
    from apps.create.content.campaign_pages import campaign_page_url

    title = (getattr(campaign, "title", None) or "").strip()
    page_url = campaign_page_url(campaign, request)
    if product:
        return build_product_order_wa_text(
            product,
            brand,
            request=request,
            campaign_title=title,
            source_label=page_url,
        )
    lines = [
        f"Hi {brand}! I'm interested in your offer:",
        f"📣 {title}" if title else "📣 Your campaign offer",
        "",
        "Please share details and how to order.",
        f"(via {page_url})",
    ]
    return "\n".join(lines)


def tracked_whatsapp_order_url(
    seller_user,
    profile,
    brand: str,
    *,
    product=None,
    campaign=None,
    request=None,
    source: str = "shop",
) -> str:
    """Public tracked redirect URL for WhatsApp checkout (preferred over direct wa.me)."""
    from apps.commerce.products.commerce_wa_orders import build_tracked_whatsapp_order_url

    return build_tracked_whatsapp_order_url(
        seller_user,
        profile,
        brand,
        product=product,
        campaign=campaign,
        request=request,
        source=source,
    )


def whatsapp_checkout_url(phone: str, text: str) -> str:
    if not phone:
        return ""
    return f"https://wa.me/{phone}?text={quote(text)}"


def checkout_heading_for(product, *, whatsapp_available: bool) -> str:
    """Buyer-facing heading for the checkout card."""
    if whatsapp_available:
        offering = getattr(product, "offering_type", "product") if product else "product"
        if offering == "service":
            return "Book on WhatsApp"
        if offering == "digital":
            return "Get it on WhatsApp"
        return "Order on WhatsApp"
    from apps.commerce.products.product_cta import public_action_heading_for

    if product:
        return public_action_heading_for(product)
    return "Complete your order"
