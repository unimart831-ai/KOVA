"""
Seasonal Variant Generator — auto-creates themed product visuals for holidays/events.

Uses Photoroom v2/edit with "Edit With AI" (editPrompt) to add seasonal context
to existing product photos without re-shooting.

Integration: Called from calendar_intel holiday watcher when upcoming events are
detected for users with active commerce products.

Examples:
  - December → "Add festive Christmas decorations around the product"
  - Valentine's → "Place product with red roses and hearts"
  - Eid → "Add crescent moon and warm lantern lighting"
  - Mashujaa Day → "Incorporate Kenyan flag colors subtly in background"
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
SEASONAL_FOLDER = "seasonal_variants"

HOLIDAY_PROMPTS: dict[str, str] = {
    # Major international
    "christmas": "Add subtle festive Christmas decorations, warm golden lighting and a hint of snow",
    "new_year": "Add celebratory golden confetti and sparkles with premium new year feel",
    "valentines": "Place with elegant red roses, hearts, and romantic soft pink lighting",
    "easter": "Add pastel spring colors, flowers, and warm Easter morning light",
    "mothers_day": "Surround with beautiful flowers and warm maternal soft lighting",
    "fathers_day": "Place in a refined masculine setting with warm leather tones",
    "black_friday": "Dramatic dark background with bold gold accents and premium urgency feel",
    "cyber_monday": "Futuristic tech-inspired neon blue lighting with digital elements",

    # African / Kenyan
    "jamhuri_day": "Incorporate Kenyan flag colors (black, red, green) subtly in the background with pride",
    "mashujaa_day": "Add Kenyan patriotic elements with warm earthy African tones",
    "madaraka_day": "Subtle Kenyan flag-inspired background with dignified presentation",
    "eid_al_fitr": "Add crescent moon, warm lantern lighting, and elegant Islamic geometric patterns",
    "eid_al_adha": "Warm golden crescent and star motifs with rich festive Arabic lighting",
    "diwali": "Add warm diyas, rangoli patterns, and rich golden festive lighting",
    "kwanzaa": "Incorporate Pan-African colors with kinara candles and warm cultural lighting",

    # Seasonal
    "back_to_school": "Add school supplies context, fresh start energy, bright organized feel",
    "rainy_season": "Add cozy indoor warmth, rain drops on window, comfort lighting",
    "harvest_season": "Rich earthy harvest tones, warm golden autumn lighting",
    "summer_sale": "Bright vibrant summer colors, sunshine, and energetic beach vibes",

    # Generic
    "celebration": "Add festive balloons, confetti, and celebration lighting",
    "premium": "Ultra-premium luxury presentation with marble and gold accents",
    "flash_sale": "Bold red urgency background with countdown energy",
}


def seasonal_variants_enabled() -> bool:
    """Check if seasonal variant generation is available."""
    from apps.commerce.products.photoroom import photoroom_enabled

    return photoroom_enabled()


def generate_seasonal_variant(
    image_url: str,
    holiday_key: str,
    custom_prompt: str = "",
    output_size: str = "1080x1080",
) -> str | None:
    """
    Generate a seasonal variant of a product image using Photoroom's Edit With AI.

    Args:
        image_url: URL of the original product image
        holiday_key: Key from HOLIDAY_PROMPTS or custom holiday name
        custom_prompt: Override prompt (used for custom events)
        output_size: Output dimensions

    Returns:
        Storage path to saved seasonal image, or None on failure.
    """
    if not seasonal_variants_enabled():
        return None

    prompt = custom_prompt or HOLIDAY_PROMPTS.get(
        holiday_key, HOLIDAY_PROMPTS.get("celebration", "")
    )
    if not prompt:
        return None

    from apps.commerce.products.photoroom_plus import photoroom_edit

    params = {
        "removeBackground": "false",
        "editWithAI.mode": "ai.auto",
        "editWithAI.prompt": prompt,
        "editWithAI.seed": str(getattr(settings, "EDIT_WITH_AI_SEED_DEFAULT", 2016886668)),
        "outputSize": output_size,
        "shadow.mode": "ai.soft",
        "export.format": "png",
        "referenceBox": "originalImage",
    }

    try:
        result = photoroom_edit(image_url, params)
        if not result.ok or not result.content or len(result.content) < 5000:
            return None

        filename = f"{SEASONAL_FOLDER}/{holiday_key}_{uuid.uuid4().hex[:8]}.png"
        saved_path = default_storage.save(filename, ContentFile(result.content))
        logger.info("Seasonal variant saved: %s (%s)", saved_path, holiday_key)
        return saved_path

    except requests.Timeout:
        logger.error("Seasonal variant generation timed out")
        return None
    except Exception:
        logger.exception("Seasonal variant generation failed")
        return None


def generate_seasonal_product_pack(product, holiday_key: str) -> list[str]:
    """
    Generate seasonal variants for a product's images (feed + story).

    Returns list of saved image paths.
    """
    if not seasonal_variants_enabled():
        return []

    image_url = _get_product_image_url(product)
    if not image_url:
        return []

    results = []

    # Feed size (1080x1080)
    feed_path = generate_seasonal_variant(image_url, holiday_key, output_size="1080x1080")
    if feed_path:
        results.append(feed_path)

    # Story size (1080x1920)
    story_path = generate_seasonal_variant(image_url, holiday_key, output_size="1080x1920")
    if story_path:
        results.append(story_path)

    if results:
        try:
            from apps.create.agents.models import AgentAction
            AgentAction.objects.create(
                user=product.user,
                agent_type="create",
                action_type="commerce.seasonal_variant",
                description=f"Seasonal ({holiday_key}) variants for {product.name}",
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk), "holiday": holiday_key},
                output_data={"paths": results, "credits_used": len(results)},
            )
        except Exception:
            pass

    return results


def auto_seasonal_for_user(user, holiday_key: str, max_products: int = 3) -> int:
    """
    Auto-generate seasonal variants for a user's top products.
    Called by the holiday watcher when an upcoming event is detected.

    Returns number of products processed.
    """
    from apps.commerce.products.models import Product

    products = (
        Product.objects.filter(user=user, is_active=True)
        .exclude(stock_status="out_of_stock")
        .order_by("-is_featured", "-created_at")[:max_products]
    )

    processed = 0
    for product in products:
        paths = generate_seasonal_product_pack(product, holiday_key)
        if paths:
            processed += 1

    return processed


def _get_product_image_url(product) -> str | None:
    """Get the best available product image URL."""
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
