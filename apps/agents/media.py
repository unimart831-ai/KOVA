"""
AI Media Generation — generates images for social media posts.

Uses Pollinations.ai API (Flux Schnell model) for fast, free image generation.
Images are downloaded and saved to Django media storage so they persist
independently of the external service.
"""

import hashlib
import logging
import uuid
from pathlib import Path
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile

from apps.content.models import MediaAttachment

logger = logging.getLogger(__name__)

# Optimal image dimensions per platform
PLATFORM_IMAGE_SIZES = {
    "twitter": (1200, 675),    # 16:9 — Twitter card
    "linkedin": (1200, 627),   # ~1.91:1 — LinkedIn feed
    "instagram": (1080, 1080), # 1:1 — Instagram square
    "facebook": (1200, 630),   # ~1.91:1 — Facebook share
    "tiktok": (1080, 1920),    # 9:16 — TikTok vertical
}

DEFAULT_SIZE = (1200, 675)

POLLINATIONS_BASE_URL = "https://gen.pollinations.ai/image"


def generate_post_image(post, image_prompt: str) -> str | None:
    """
    Generate an AI image for a post and save it as a MediaAttachment.

    Args:
        post: Post instance to attach the image to.
        image_prompt: Text description for image generation.

    Returns:
        URL of the saved image, or None if generation failed.
    """
    if not getattr(settings, "AI_IMAGE_GENERATION_ENABLED", False):
        return None

    if not image_prompt or not image_prompt.strip():
        return None

    platform = post.social_account.platform
    width, height = PLATFORM_IMAGE_SIZES.get(platform, DEFAULT_SIZE)

    try:
        image_bytes = _fetch_image(image_prompt, width, height)
        if not image_bytes:
            return None

        # Save to Django storage via MediaAttachment
        filename = f"ai_{uuid.uuid4().hex[:12]}.jpg"
        filepath = f"post_media/ai/{filename}"

        attachment = MediaAttachment(
            post=post,
            file_type="image",
            alt_text=image_prompt[:500],
            order=0,
        )
        attachment.file.save(filepath, ContentFile(image_bytes), save=True)

        # Also add to post.media_urls for the publishing pipeline
        media_url = attachment.file.url
        if not post.media_urls:
            post.media_urls = []
        post.media_urls.append(media_url)
        post.save(update_fields=["media_urls", "updated_at"])

        logger.info(
            "Generated AI image for post %s (%s): %s",
            post.id, platform, media_url,
        )
        return media_url

    except Exception as exc:
        logger.warning(
            "AI image generation failed for post %s: %s", post.id, exc,
        )
        return None


def _fetch_image(prompt: str, width: int, height: int) -> bytes | None:
    """
    Fetch generated image bytes from Pollinations.ai.

    Uses the GET endpoint with Flux Schnell model (fast, high quality).
    """
    api_key = getattr(settings, "POLLINATIONS_API_KEY", "")
    model = getattr(settings, "AI_IMAGE_MODEL", "flux")

    # Build URL with encoded prompt
    encoded_prompt = quote(prompt, safe="")
    url = f"{POLLINATIONS_BASE_URL}/{encoded_prompt}"

    params = {
        "width": width,
        "height": height,
        "model": model,
        "nologo": "true",
        "seed": _prompt_seed(prompt),
    }

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    logger.debug("Fetching AI image: %s (%dx%d)", prompt[:80], width, height)

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "image" not in content_type:
        logger.warning("Pollinations returned non-image content-type: %s", content_type)
        return None

    if len(response.content) < 1024:
        logger.warning("Pollinations returned suspiciously small image (%d bytes)", len(response.content))
        return None

    return response.content


def _prompt_seed(prompt: str) -> int:
    """Generate a deterministic seed from the prompt for consistent results."""
    return int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
