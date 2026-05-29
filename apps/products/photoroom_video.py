"""
Photoroom Video API — generates product videos from static images.
Used for auto-generating Reels/TikTok content from Snap2sell photos.

API: POST https://image-api.photoroom.com/v1/animate
- Input: product image (background-removed preferred)
- Output: MP4 video (3-7 seconds)
- Cost: 1 video credit per call

Docs: https://docs.photoroom.com/video-api/
"""
from __future__ import annotations

import logging
import uuid
from io import BytesIO

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

PHOTOROOM_VIDEO_URL = "https://image-api.photoroom.com/v1/animate"
VIDEO_FOLDER = "product_videos"


def video_generation_enabled() -> bool:
    """Check if video generation is available."""
    if not getattr(settings, "PHOTOROOM_VIDEO_ENABLED", False):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def generate_product_video(
    image_url: str,
    prompt: str = "Slowly rotate the product with soft lighting",
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16",
) -> str | None:
    """
    Generate a product video from a static image via Photoroom Video API.

    Args:
        image_url: URL of the product image (ideally background-removed)
        prompt: Motion/style instruction for the video
        duration_seconds: Video length (3-7 seconds)
        aspect_ratio: "9:16" for reels, "1:1" for feed, "16:9" for landscape

    Returns:
        Storage path to the saved MP4 file, or None on failure.
    """
    api_key = getattr(settings, "PHOTOROOM_API_KEY", "")
    if not api_key:
        logger.warning("Photoroom API key not configured for video generation")
        return None

    headers = {
        "x-api-key": api_key,
        "Accept": "video/mp4",
    }

    payload = {
        "imageUrl": image_url,
        "prompt": prompt,
        "durationSeconds": min(max(duration_seconds, 3), 7),
        "aspectRatio": aspect_ratio,
    }

    try:
        resp = requests.post(
            PHOTOROOM_VIDEO_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            logger.error(
                "Photoroom Video API error %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return None

        video_bytes = resp.content
        if not video_bytes or len(video_bytes) < 1000:
            logger.warning("Photoroom returned empty or tiny video response")
            return None

        filename = f"{VIDEO_FOLDER}/{uuid.uuid4().hex}.mp4"
        saved_path = default_storage.save(filename, ContentFile(video_bytes))
        logger.info("Product video saved: %s (%d bytes)", saved_path, len(video_bytes))
        return saved_path

    except requests.Timeout:
        logger.error("Photoroom Video API timed out (120s)")
        return None
    except Exception:
        logger.exception("Photoroom Video API unexpected error")
        return None


def generate_product_reel_video(product, image_url: str = None) -> str | None:
    """
    Generate a reel-ready video for a product.
    Selects the best image and crafts an appropriate prompt.
    """
    if not video_generation_enabled():
        return None

    if not image_url:
        image_url = _get_best_product_image_url(product)
    if not image_url:
        return None

    prompt = _build_video_prompt(product)

    path = generate_product_video(
        image_url=image_url,
        prompt=prompt,
        duration_seconds=5,
        aspect_ratio="9:16",
    )

    if path:
        try:
            from apps.agents.models import AgentAction

            AgentAction.objects.create(
                user=product.user,
                agent_type="create",
                action_type="commerce.video_generation",
                description=f"Generated product video for {product.name}",
                status=AgentAction.ActionStatus.COMPLETED,
                input_data={"product_id": str(product.pk), "prompt": prompt},
                output_data={"video_path": path},
            )
        except Exception:
            pass

    return path


def _get_best_product_image_url(product) -> str | None:
    """Get the best available product image URL for video generation."""
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


def _build_video_prompt(product) -> str:
    """Build an appropriate video motion prompt based on product type."""
    from apps.products.models import Product

    offering = getattr(product, "offering_type", Product.OfferingType.PRODUCT)
    category = ""
    if product.category:
        category = product.category.name.lower()

    if offering == Product.OfferingType.SERVICE:
        return "Gently animate with a professional motion effect, subtle zoom and lighting shift"

    if offering == Product.OfferingType.DIGITAL:
        return "Smooth reveal animation with a gentle glow effect and modern transitions"

    if "food" in category or "restaurant" in category:
        return "Slow appetizing reveal with steam or warmth effect, soft lighting"
    if "fashion" in category or "apparel" in category or "shoe" in category:
        return "Elegant slow rotation showcasing details, with soft studio lighting"
    if "beauty" in category or "cosmetic" in category:
        return "Luxurious slow zoom with sparkle highlights and soft reflections"
    if "electronics" in category or "tech" in category:
        return "Sleek modern rotation with subtle light reflections on the surface"
    if "jewelry" in category:
        return "Slow glamorous rotation with sparkle and light play"

    return "Professional product showcase with gentle rotation and studio lighting"
