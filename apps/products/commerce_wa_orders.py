"""
WhatsApp order click tracking + seller notifications.

Buyers hit a signed Kova redirect first; we log the intent, notify the seller,
then forward to wa.me with the pre-filled order message.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse

from apps.products.commerce_checkout import (
    build_campaign_order_wa_text,
    build_product_order_wa_text,
    whatsapp_checkout_url,
)
from apps.products.commerce_seo import brand_name
from apps.products.commerce_social import resolve_shop_whatsapp

logger = logging.getLogger(__name__)

_SIGNER_SALT = "kova-commerce-wa-order"
_TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=_SIGNER_SALT)


def build_wa_order_token(
    *,
    product_id: str = "",
    campaign_id: str = "",
    source: str = "shop",
) -> str:
    payload = "|".join([
        (product_id or "")[:36],
        (campaign_id or "")[:36],
        (source or "shop")[:32],
    ])
    return _signer().sign(payload)


def parse_wa_order_token(token: str) -> dict:
    try:
        raw = _signer().unsign(token, max_age=_TOKEN_MAX_AGE)
    except SignatureExpired as exc:
        raise ValueError("This order link has expired.") from exc
    except BadSignature as exc:
        raise ValueError("Invalid order link.") from exc

    parts = raw.split("|", 2)
    while len(parts) < 3:
        parts.append("")
    product_id, campaign_id, source = parts[0], parts[1], parts[2]
    return {
        "product_id": product_id or None,
        "campaign_id": campaign_id or None,
        "source": source or "shop",
    }


def _absolute_redirect_base(request=None) -> str:
    if request:
        return request.build_absolute_uri(reverse("public_whatsapp_order"))
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    path = reverse("public_whatsapp_order")
    return f"{site}{path}" if site else path


def build_tracked_whatsapp_order_url(
    seller_user,
    profile,
    brand: str,
    *,
    product=None,
    campaign=None,
    request=None,
    source: str = "shop",
) -> str:
    """Signed Kova URL that tracks the click before opening WhatsApp."""
    phone = resolve_shop_whatsapp(profile, seller_user)
    if not phone:
        return ""

    # Ensure we can build the destination message (validates product/campaign exist).
    try:
        _build_order_message(
            seller_user, profile, brand, product=product, campaign=campaign, request=request,
        )
    except ValueError:
        return ""

    token = build_wa_order_token(
        product_id=str(product.pk) if product else "",
        campaign_id=str(campaign.pk) if campaign else "",
        source=source,
    )
    base = _absolute_redirect_base(request)
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}t={quote(token)}"


def _load_order_context(token_data: dict):
    from apps.content.models import MarketingCampaign
    from apps.products.models import Product

    product = None
    campaign = None
    seller_user = None

    if token_data.get("product_id"):
        product = (
            Product.objects.select_related("user", "user__profile")
            .filter(pk=token_data["product_id"], is_active=True)
            .first()
        )
        if not product:
            raise ValueError("Product not found.")
        seller_user = product.user

    if token_data.get("campaign_id"):
        campaign = (
            MarketingCampaign.objects.select_related(
                "user", "user__profile", "content_seed", "content_seed__product",
            )
            .filter(pk=token_data["campaign_id"])
            .first()
        )
        if not campaign:
            raise ValueError("Campaign not found.")
        seller_user = campaign.user
        if product is None:
            from apps.content.campaign_pages import _campaign_product

            product = _campaign_product(campaign)

    if seller_user is None:
        raise ValueError("Order link is missing product or campaign context.")

    return seller_user, seller_user.profile, product, campaign


def _build_order_message(
    seller_user,
    profile,
    brand: str,
    *,
    product=None,
    campaign=None,
    request=None,
) -> str:
    if campaign:
        return build_campaign_order_wa_text(campaign, product, brand, request=request)
    if product:
        return build_product_order_wa_text(product, brand, request=request, source_label="Kova shop")
    raise ValueError("Nothing to order.")


def record_whatsapp_order_click(
    request,
    *,
    seller_user,
    product,
    campaign,
    source: str,
) -> None:
    try:
        from apps.analytics.models import Conversion
        from apps.content.campaign_attribution import create_attributed_conversion

        metadata = {
            "source": source,
            "referrer": (request.META.get("HTTP_REFERER") or "")[:500],
            "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:300],
        }
        if product:
            metadata["product_id"] = str(product.pk)
            metadata["commerce_slug"] = product.commerce_slug

        create_attributed_conversion(
            seller_user,
            Conversion.ConversionType.LEAD,
            product=product,
            campaign=campaign,
            event_name="whatsapp_order_click",
            utm_campaign=(campaign.slug if campaign else "")[:255],
            metadata=metadata,
        )
    except Exception:
        logger.exception("whatsapp order click tracking failed")


def notify_seller_whatsapp_order_intent(
    seller_user,
    *,
    product,
    campaign,
    source: str,
) -> None:
    """In-app alert + optional WhatsApp utility message to the owner."""
    brand = brand_name(seller_user.profile, seller_user)
    if product:
        item_label = product.name
    elif campaign:
        item_label = campaign.title
    else:
        item_label = "your offer"

    source_labels = {
        "campaign": "campaign page",
        "shop": "shop",
        "product": "product page",
    }
    via = source_labels.get(source, source)

    message = (
        f"New WhatsApp order started for {item_label} (via {via}). "
        f"Check your WhatsApp — a buyer may be messaging you now."
    )

    try:
        from apps.notifications.models import Notification

        Notification.create_for_user(seller_user, "system", message)
    except Exception:
        logger.exception("in-app WA order notification failed for user %s", seller_user.pk)

    _try_whatsapp_owner_alert(seller_user, message)


def notify_seller_payment_received(commerce_payment) -> None:
    """Alert seller (in-app + WhatsApp) when a commerce payment completes.

    Fired via the CommercePayment post-save signal, so every completion path
    (M-Pesa webhook, card checkout, WhatsApp bot) triggers exactly one alert.
    """
    seller = commerce_payment.user
    product = commerce_payment.product
    name = product.name if product else "an order"
    amount = commerce_payment.amount
    currency = commerce_payment.currency or "KES"
    receipt = commerce_payment.receipt_number or ""
    phone = (commerce_payment.phone_number or "").strip()
    buyer = f"...{phone[-4:]}" if len(phone) >= 4 else "a customer"

    message = (
        f"💰 Payment received: {currency} {amount:,.0f} for {name} from {buyer}."
        f"{f' Receipt {receipt}.' if receipt else ''} "
        f"Follow up on WhatsApp to confirm delivery. Reply MONEY for this week's total."
    )

    try:
        from apps.notifications.models import Notification

        Notification.create_for_user(seller, "system", message)
    except Exception:
        logger.exception("in-app seller payment notification failed for %s", commerce_payment.pk)

    _try_whatsapp_owner_alert(seller, message)


# Backwards-compatible alias (older callers)
notify_seller_mpesa_order = notify_seller_payment_received


def _try_whatsapp_owner_alert(seller_user, body: str) -> None:
    """Best-effort WhatsApp ping to the owner's phone.

    Tries the seller's own WhatsApp Business account first, then falls back
    to Kova's master number (same channel as the Daily Brief) so owners
    without a connected WA Business number still get operational alerts.
    """
    profile = getattr(seller_user, "profile", None)
    owner_phone = (getattr(seller_user, "phone_number", "") or "").strip()
    if not owner_phone and profile:
        owner_phone = (profile.mpesa_phone or profile.cta_whatsapp or "").strip()

    if owner_phone:
        from apps.whatsapp.services import WhatsAppSendError, send_text_message

        try:
            send_text_message(to=owner_phone, body=body, user=seller_user)
            return
        except WhatsAppSendError:
            pass
        except Exception:
            logger.exception("owner WA alert failed for user %s", seller_user.pk)

    # Fallback — Kova master number (Daily Brief channel), queued async
    try:
        from apps.briefs.owner_alerts import queue_owner_alert

        queue_owner_alert(seller_user, body)
    except Exception:
        logger.exception("master-number owner alert failed for user %s", seller_user.pk)


def resolve_whatsapp_order_redirect(request, token: str) -> HttpResponseRedirect:
    """Track click, notify seller, redirect buyer to wa.me."""
    token_data = parse_wa_order_token(token)
    seller_user, profile, product, campaign = _load_order_context(token_data)
    brand = brand_name(profile, seller_user)
    phone = resolve_shop_whatsapp(profile, seller_user)
    if not phone:
        raise Http404("WhatsApp ordering is not available for this shop.")

    text = _build_order_message(
        seller_user, profile, brand, product=product, campaign=campaign, request=request,
    )
    dest = whatsapp_checkout_url(phone, text)
    if not dest:
        raise Http404("Could not open WhatsApp.")

    record_whatsapp_order_click(
        request,
        seller_user=seller_user,
        product=product,
        campaign=campaign,
        source=token_data.get("source") or "shop",
    )
    notify_seller_whatsapp_order_intent(
        seller_user,
        product=product,
        campaign=campaign,
        source=token_data.get("source") or "shop",
    )

    return HttpResponseRedirect(dest)
