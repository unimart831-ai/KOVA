"""
AI Image Generation Service.

Provider-agnostic wrapper that generates images from text prompts.
Default provider: fal.ai (Flux Schnell) — fast, high-quality, cost-effective.
Fallback: Stability AI (SDXL).

Usage:
    from apps.content.image_gen import generate_image, generate_carousel_images

    url = generate_image("A confident African business owner at her boutique, warm lighting")
    slides = generate_carousel_images([
        {"image_prompt": "Slide 1 prompt", "heading": "Title"},
        ...
    ])
"""

import logging
import time
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ── Aspect ratio → pixel dimensions ──────────────────────────────────────────

ASPECT_DIMENSIONS = {
    "square":    (1024, 1024),   # Instagram feed, Facebook, LinkedIn
    "portrait":  (1024, 1280),   # Instagram portrait (4:5)
    "landscape": (1280, 720),    # LinkedIn / Facebook landscape (16:9)
    "story":     (1080, 1920),   # Instagram/Facebook Stories & Reels (9:16)
}


def _get_provider() -> str:
    return getattr(settings, "IMAGE_GEN_PROVIDER", "fal")


def _get_api_key() -> str:
    return getattr(settings, "IMAGE_GEN_API_KEY", "") or getattr(settings, "FAL_API_KEY", "")


# ── fal.ai provider (Flux Schnell) ────────────────────────────────────────────

def _generate_fal(prompt: str, aspect_ratio: str = "square") -> Optional[str]:
    """
    Generate an image via fal.ai Flux Schnell.

    Returns a public HTTPS URL for the generated image, or None on failure.
    Flux Schnell is optimised for speed (~1-2 s per image) while maintaining
    commercial-grade quality — ideal for bulk content generation.
    """
    try:
        import fal_client
    except ImportError:
        logger.warning("fal_client not installed — run: pip install fal-client")
        return None

    api_key = _get_api_key()
    if not api_key:
        logger.warning("IMAGE_GEN_API_KEY / FAL_API_KEY not set — image generation skipped")
        return None

    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1024, 1024))

    try:
        import os
        os.environ["FAL_KEY"] = api_key

        result = fal_client.run(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "image_size": {"width": width, "height": height},
                "num_inference_steps": 4,
                "num_images": 1,
                "enable_safety_checker": True,
            },
        )
        images = result.get("images", [])
        if images:
            return images[0].get("url")
    except Exception as e:
        logger.warning("fal.ai image generation failed: %s", e)
    return None


# ── Stability AI fallback (SDXL) ─────────────────────────────────────────────

def _generate_stability(prompt: str, aspect_ratio: str = "square") -> Optional[str]:
    """Generate an image via Stability AI SDXL. Returns a public URL or None."""
    import base64
    import io

    api_key = getattr(settings, "STABILITY_API_KEY", "")
    if not api_key:
        return None

    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1024, 1024))
    # Stability AI SDXL supports: 1024×1024, 1152×896, 896×1152, 1216×832, etc.
    # Snap to supported SDXL dimensions
    if height > width:
        width, height = 896, 1152  # portrait
    elif width > height:
        width, height = 1216, 832  # landscape
    else:
        width, height = 1024, 1024

    try:
        import httpx
        resp = httpx.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "text_prompts": [{"text": prompt, "weight": 1.0}],
                "cfg_scale": 7,
                "height": height,
                "width": width,
                "samples": 1,
                "steps": 30,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        artifacts = data.get("artifacts", [])
        if artifacts:
            # Stability returns base64 — upload to storage and return URL
            img_b64 = artifacts[0]["base64"]
            return _upload_b64_to_storage(img_b64)
    except Exception as e:
        logger.warning("Stability AI image generation failed: %s", e)
    return None


def _upload_b64_to_storage(b64_data: str) -> Optional[str]:
    """Upload base64 image data to default storage and return public URL."""
    import base64
    import uuid
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from apps.content.tasks import _public_url_for_file

    try:
        img_bytes = base64.b64decode(b64_data)
        file_name = f"ai_images/{uuid.uuid4().hex}.jpg"
        default_storage.save(file_name, ContentFile(img_bytes))
        return _public_url_for_file(file_name)
    except Exception as e:
        logger.warning("Failed to upload generated image to storage: %s", e)
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def generate_image(prompt: str, aspect_ratio: str = "square") -> Optional[str]:
    """
    Generate a single image from a prompt.

    Tries the configured provider first, falls back to alternatives.
    Returns a public HTTPS URL or None if all providers fail.
    """
    if not prompt or not prompt.strip():
        return None

    provider = _get_provider()

    if provider == "fal":
        url = _generate_fal(prompt, aspect_ratio)
        if url:
            return url
        # Fallback to Stability if fal fails
        return _generate_stability(prompt, aspect_ratio)

    if provider == "stability":
        url = _generate_stability(prompt, aspect_ratio)
        if url:
            return url
        return _generate_fal(prompt, aspect_ratio)

    logger.warning("Unknown IMAGE_GEN_PROVIDER: %s", provider)
    return None


def generate_carousel_images(slides: list, aspect_ratio: str = "square") -> list:
    """
    Generate images for carousel slides that have an image_prompt but no image_url.

    Mutates each slide dict in-place, adding/updating ``image_url``.
    Returns the updated slides list.

    Each slide: {"heading": str, "body": str, "image_prompt": str, "image_url": str}
    """
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        if slide.get("image_url"):
            continue  # Already has an image
        prompt = slide.get("image_prompt", "").strip()
        if not prompt:
            continue
        logger.info("Generating image for carousel slide %d: %s...", i + 1, prompt[:60])
        url = generate_image(prompt, aspect_ratio)
        if url:
            slide["image_url"] = url
        else:
            logger.warning("Image generation failed for carousel slide %d", i + 1)
        # Brief pause to avoid hitting rate limits on bulk generation
        if i < len(slides) - 1:
            time.sleep(0.5)

    return slides
