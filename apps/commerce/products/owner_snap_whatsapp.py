"""Owner Snap-to-Sell via Kova's master WhatsApp number."""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.commerce.products.business_assets import sync_asset_from_product
from apps.commerce.products.commerce_autopilot import sanitize_product_name, unique_placeholder_name
from apps.commerce.products.image_utils import normalize_image_bytes
from apps.commerce.products.models import BusinessAsset, Product

logger = logging.getLogger(__name__)

_PENDING_CACHE_TTL = 3600
_PENDING_KEY = "wa_owner_snap:{user_id}"


def parse_snap_caption(caption: str) -> tuple[str, Decimal | None]:
    """Parse 'Blue dress 2500' or 'Blue dress KES 2500' into name + price."""
    text = (caption or "").strip()
    if not text:
        return "", None

    price_match = re.search(
        r"(?:kes|ksh|/=)?\s*([\d][\d,]*(?:\.\d{1,2})?)\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if not price_match:
        return text, None

    price_raw = price_match.group(1).replace(",", "")
    try:
        price = Decimal(price_raw)
    except InvalidOperation:
        return text, None

    if price <= 0:
        return text, None

    name = text[: price_match.start()].strip(" -|,")
    return name, price


def _pending_cache_key(user_id) -> str:
    return _PENDING_KEY.format(user_id=user_id)


def _set_pending_snap(user, *, media_id: str, mime_type: str, caption: str = "") -> None:
    cache.set(
        _pending_cache_key(user.pk),
        {
            "media_id": media_id,
            "mime_type": mime_type or "image/jpeg",
            "caption": caption,
        },
        _PENDING_CACHE_TTL,
    )


def _get_pending_snap(user) -> dict | None:
    return cache.get(_pending_cache_key(user.pk))


def _clear_pending_snap(user) -> None:
    cache.delete(_pending_cache_key(user.pk))


def _download_owner_media(media_id: str) -> tuple[bytes, str]:
    from apps.core.platforms.providers.whatsapp import WhatsAppProvider

    token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", "") or ""
    if not token:
        raise ValueError("WhatsApp master credentials are not configured")

    provider = WhatsAppProvider()
    return provider.download_media_bytes(token, media_id)


def _save_product_image(product: Product, image_bytes: bytes, mime_type: str) -> None:
    ext = "jpg"
    if "png" in (mime_type or "").lower():
        ext = "png"
    elif "webp" in (mime_type or "").lower():
        ext = "webp"

    normalized = normalize_image_bytes(image_bytes)
    filename = f"product_images/wa_snap_{product.pk}.{ext}"
    saved_path = default_storage.save(filename, ContentFile(normalized))
    product.image = saved_path
    product.save(update_fields=["image"])


def _product_limit_message(user) -> str | None:
    from apps.core.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(user)
    current_count = Product.objects.filter(user=user, is_active=True).count()
    max_products = limits.get("max_products", 5)
    if current_count >= max_products:
        site = getattr(settings, "SITE_URL", "").rstrip("/")
        return (
            f"Your plan allows up to {max_products} offers. "
            f"Upgrade to add more: {site}/billing/"
        )
    return None


def _snap_policy_block_message(user) -> str | None:
    from apps.create.content.safety import is_snap_blocked

    blocked, reason = is_snap_blocked(user)
    if blocked:
        return reason
    return None


def launch_owner_snap(
    user,
    *,
    media_id: str,
    mime_type: str = "image/jpeg",
    caption: str = "",
    photo_context: str = "",
) -> tuple[str, str, bool, dict]:
    """Create a product from WhatsApp media and start Snap pipeline."""
    from apps.create.content.safety import check_uploaded_images_safe, record_content_safety_incident
    from apps.create.content.models import ContentSafetyIncident
    from apps.commerce.products.tasks import snap_to_sell_analyze
    from apps.core.utils import fire_task

    metadata: dict = {"media_id": media_id}

    limit_msg = _product_limit_message(user)
    if limit_msg:
        return limit_msg, "snap_limit", False, metadata

    policy_msg = _snap_policy_block_message(user)
    if policy_msg:
        return policy_msg, "snap_blocked", False, metadata

    name, price = parse_snap_caption(caption)
    if not name and not price:
        _set_pending_snap(user, media_id=media_id, mime_type=mime_type, caption=caption)
        return (
            "Got your photo! Reply with name and price.\n"
            "Example: Blue dress 2500",
            "snap_awaiting_details",
            True,
            metadata,
        )

    if not price:
        _set_pending_snap(user, media_id=media_id, mime_type=mime_type, caption=caption or name)
        label = name or "your item"
        return (
            f"Got it — {label}. What's the price in KES?\n"
            "Reply like: 2500",
            "snap_awaiting_price",
            True,
            metadata,
        )

    if not name:
        name = unique_placeholder_name(user, "product")

    name = sanitize_product_name(name) or unique_placeholder_name(user, "product")

    try:
        image_bytes, resolved_mime = _download_owner_media(media_id)
    except Exception as exc:
        logger.exception("Owner WA snap media download failed: %s", exc)
        return (
            "Couldn't download that photo. Please try sending it again.",
            "snap_download_failed",
            False,
            metadata,
        )

    upload_check = check_uploaded_images_safe(
        [ContentFile(image_bytes, name="wa_snap.jpg")],
        user,
    )
    if not upload_check.safe:
        record_content_safety_incident(
            user=user,
            source=ContentSafetyIncident.Source.UPLOAD,
            result=upload_check,
            action_taken="wa_snap_blocked",
        )
        return (
            "That photo can't be used for Snap to Sell (policy).",
            "snap_policy_blocked",
            False,
            metadata,
        )

    product = Product.objects.create(
        user=user,
        name=name,
        offering_type=Product.OfferingType.PRODUCT,
        price=price,
        currency="KES",
        stock_status=Product.StockStatus.IN_STOCK,
        source=Product.Source.SNAP,
        visual_mode=Product.VisualMode.PRO_SCENE,
    )
    _save_product_image(product, image_bytes, resolved_mime or mime_type)

    asset = sync_asset_from_product(
        product,
        source=BusinessAsset.Source.WHATSAPP,
        status=BusinessAsset.Status.PENDING_APPROVAL,
    )
    _clear_pending_snap(user)

    fire_task(
        snap_to_sell_analyze,
        str(product.pk),
        photo_context=photo_context or caption,
        proposals_only=True,
    )

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    proposals_url = f"{site}/content/campaigns/asset/{asset.pk}/proposals/" if site else ""
    metadata.update({
        "product_id": str(product.pk),
        "asset_id": str(asset.pk),
        "price": str(price),
        "proposals_url": proposals_url,
    })
    lines = [
        f"Snap ready for *{name}* — KES {price:,.0f}.",
        "",
        "Kova found marketing angles for this. Pick one to build your full campaign (reel + carousel + posts + shop page).",
    ]
    if proposals_url:
        lines.append(f"\nChoose your angle:\n{proposals_url}")
    lines.append("\nReply CAMPAIGNS when your package is ready to approve.")
    return (
        "\n".join(lines),
        "snap_launched",
        True,
        metadata,
    )


def handle_owner_snap_image(user, msg_data: dict) -> tuple[str, str, bool, dict]:
    image = msg_data.get("image", {})
    media_id = image.get("id", "")
    if not media_id:
        return "Couldn't read that image. Please try again.", "snap_no_media", False, {}

    caption = image.get("caption", "") or ""
    mime_type = image.get("mime_type", "image/jpeg")
    return launch_owner_snap(
        user,
        media_id=media_id,
        mime_type=mime_type,
        caption=caption,
    )


def try_complete_pending_snap(user, text: str) -> tuple[str, str, bool, dict] | None:
    pending = _get_pending_snap(user)
    if not pending:
        return None

    media_id = pending.get("media_id", "")
    if not media_id:
        _clear_pending_snap(user)
        return None

    base_caption = (pending.get("caption") or "").strip()
    combined = f"{base_caption} {text}".strip() if base_caption else text.strip()
    name, price = parse_snap_caption(combined)

    if not price and text.strip().replace(",", "").isdigit():
        try:
            price = Decimal(text.strip().replace(",", ""))
            name = base_caption or name
        except InvalidOperation:
            pass

    if not price:
        return (
            "Still need a price in KES. Reply like: 2500",
            "snap_awaiting_price",
            True,
            {"media_id": media_id},
        )

    if not name:
        name = sanitize_product_name(base_caption) or ""

    caption = f"{name} {price}".strip()
    return launch_owner_snap(
        user,
        media_id=media_id,
        mime_type=pending.get("mime_type", "image/jpeg"),
        caption=caption,
        photo_context=text.strip(),
    )
