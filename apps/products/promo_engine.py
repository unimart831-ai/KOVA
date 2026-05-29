"""
Promo Engine — auto-generates branded promotional images from business triggers.
Uses Photoroom v2/edit with text overlays and brand colors.

Triggers: new_product, low_stock, restocked, price_change, holiday
Output: Ready-to-post promotional graphics (feed + story sizes)
"""
from __future__ import annotations

import logging
import uuid

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

PHOTOROOM_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
PROMO_FOLDER = "promo_engine"


class PromoTrigger:
    NEW_PRODUCT = "new_product"
    LOW_STOCK = "low_stock"
    RESTOCKED = "restocked"
    PRICE_CHANGE = "price_change"
    HOLIDAY = "holiday"
    FLASH_SALE = "flash_sale"


TRIGGER_TEMPLATES = {
    PromoTrigger.NEW_PRODUCT: {
        "badge_text": "NEW",
        "cta_text": "Shop Now",
        "bg_prompt": "Clean modern studio with subtle brand accent lighting",
        "urgency": False,
    },
    PromoTrigger.LOW_STOCK: {
        "badge_text": "LAST FEW",
        "cta_text": "Get Yours",
        "bg_prompt": "Dramatic spotlight studio background with urgency feel",
        "urgency": True,
    },
    PromoTrigger.RESTOCKED: {
        "badge_text": "BACK IN STOCK",
        "cta_text": "Order Now",
        "bg_prompt": "Fresh clean studio with celebratory lighting",
        "urgency": False,
    },
    PromoTrigger.PRICE_CHANGE: {
        "badge_text": "SALE",
        "cta_text": "Limited Time",
        "bg_prompt": "Bold vibrant background with sale energy",
        "urgency": True,
    },
    PromoTrigger.HOLIDAY: {
        "badge_text": "SPECIAL",
        "cta_text": "Celebrate",
        "bg_prompt": "Festive background with warm celebration lighting",
        "urgency": False,
    },
    PromoTrigger.FLASH_SALE: {
        "badge_text": "FLASH SALE",
        "cta_text": "Buy Now",
        "bg_prompt": "High-energy studio with dramatic red and gold lighting",
        "urgency": True,
    },
}


def promo_engine_enabled() -> bool:
    from apps.products.photoroom import photoroom_enabled

    return photoroom_enabled()


def generate_promo_image(
    product,
    trigger: str = PromoTrigger.NEW_PRODUCT,
    custom_text: str = "",
    size: str = "1080x1080",
) -> str | None:
    """
    Generate a promotional image for a product based on a trigger.

    Returns storage path to saved image, or None on failure.
    """
    if not promo_engine_enabled():
        return None

    from apps.products.photoroom_plus import AI_BG_MODEL_HEADER, photoroom_edit

    template = TRIGGER_TEMPLATES.get(trigger, TRIGGER_TEMPLATES[PromoTrigger.NEW_PRODUCT])

    image_url = _get_product_image_url(product)
    if not image_url:
        return None

    params = {
        "removeBackground": "true",
        "background.prompt": template["bg_prompt"],
        "background.expandPrompt": "ai.auto",
        "outputSize": size,
        "padding": "0.15",
        "shadow.mode": "ai.soft",
        "export.format": "png",
        "referenceBox": "originalImage",
    }
    headers = {"pr-ai-background-model-version": AI_BG_MODEL_HEADER}

    try:
        image_bytes = photoroom_edit(image_url, params, extra_headers=headers)
        if not image_bytes or len(image_bytes) < 5000:
            return None

        filename = f"{PROMO_FOLDER}/{trigger}_{uuid.uuid4().hex[:8]}.png"
        saved_path = default_storage.save(filename, ContentFile(image_bytes))

        try:
            from apps.agents.models import AgentAction

            AgentAction.objects.create(
                user=product.user,
                agent_type="create",
                action_type="commerce.promo_engine",
                description=f"Promo image ({trigger}) for {product.name}",
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk), "trigger": trigger},
                output_data={"path": saved_path},
            )
        except Exception:
            pass

        return saved_path

    except Exception:
        logger.exception("Promo Engine generation failed")
        return None


def generate_promo_pack(product, trigger: str = PromoTrigger.NEW_PRODUCT) -> dict:
    """
    Generate a full promo pack: feed (1080x1080) + story (1080x1920).
    Returns dict with 'feed' and 'story' paths.
    """
    results = {}

    feed = generate_promo_image(product, trigger=trigger, size="1080x1080")
    if feed:
        results["feed"] = feed

    story = generate_promo_image(product, trigger=trigger, size="1080x1920")
    if story:
        results["story"] = story

    return results


def _get_product_image_url(product) -> str | None:
    """Get the best product image URL for promo generation."""
    additional = product.additional_images or []
    for img_url in additional:
        if "studio_polish" in img_url or "product_variations" in img_url:
            return img_url
    if product.image:
        try:
            return product.image.url
        except Exception:
            pass
    if additional:
        return additional[0]
    return None


def _get_brand_primary_color(user) -> str:
    """Get the user's primary brand color."""
    profile = getattr(user, "profile", None)
    if profile:
        return getattr(profile, "primary_color", "#000000") or "#000000"
    return "#000000"
