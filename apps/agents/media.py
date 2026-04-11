"""
AI Media Generation — generates images for social media posts.

Multi-provider support with automatic fallback:
  1. Together.ai  — FLUX.1-schnell-Free (truly free, fast)
  2. Pollinations.ai — Flux Schnell (free tier with API key)
  3. Hugging Face — FLUX.1-schnell (free Inference API)

Images are downloaded and saved to Django media storage so they persist
independently of the external service.
"""

import hashlib
import json
import logging
import uuid
from base64 import b64decode
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
    "youtube": (1280, 720),    # 16:9 — YouTube thumbnail
    "pinterest": (1000, 1500), # 2:3 — Pinterest pin
    "threads": (1080, 1080),   # 1:1 — Threads square
    "bluesky": (1200, 675),    # 16:9 — Bluesky card
}

DEFAULT_SIZE = (1200, 675)


# ─── PLATFORM-SPECIFIC PROMPT ENGINEERING ─────────────────────────────────────

PLATFORM_PROMPT_SUFFIX = {
    "instagram": "vibrant, eye-catching, social media style, centered composition, high contrast",
    "facebook":  "warm, relatable, community feel, lifestyle photography style",
    "linkedin":  "professional, clean, corporate editorial, subtle tones, business context",
    "tiktok":    "bold, energetic, vertical composition, youth-oriented, trending aesthetic",
    "twitter":   "striking, minimal, high-impact single subject, editorial",
    "pinterest": "aspirational, aesthetic, vertical layout, lifestyle inspiration",
    "youtube":   "cinematic, wide-angle, thumbnail-friendly, bold colors",
}

VISUAL_STYLE_PREFIX = {
    "photography":  "professional photography,",
    "illustration": "digital illustration style,",
    "flat_design":  "flat design, clean vectors,",
    "3d_render":    "3D rendered,",
    "collage":      "mixed media collage style,",
    "abstract":     "abstract art style,",
    "corporate":    "corporate professional stock photo style,",
    "vibrant":      "vibrant colorful,",
    "dark_moody":   "dark moody atmospheric,",
    "auto":         "",
}


def _enhance_prompt(prompt: str, platform: str, profile=None) -> str:
    """Inject visual_style prefix and platform-specific suffix into the image prompt."""
    parts = []

    # Prepend visual style from user profile
    visual_style = getattr(profile, "visual_style", "auto") if profile else "auto"
    style_prefix = VISUAL_STYLE_PREFIX.get(visual_style, "")
    if style_prefix:
        parts.append(style_prefix)

    parts.append(prompt.strip())

    # Append platform-specific aesthetics
    suffix = PLATFORM_PROMPT_SUFFIX.get(platform, "")
    if suffix:
        parts.append(suffix)

    return " ".join(parts)


# ─── PER-TIER IMAGE MODEL ROUTING ────────────────────────────────────────────

TIER_IMAGE_MODELS = {
    "starter": "black-forest-labs/FLUX.1-schnell",       # ~$0.003/img — fast, good quality
    "growth":  "black-forest-labs/FLUX.1-krea-dev",      # ~$0.025/img — significantly better detail
    "pro":     "black-forest-labs/FLUX.1.1-pro",         # $0.04/img  — best FLUX quality
    "agency":  "black-forest-labs/FLUX.1.1-pro",         # $0.04/img  — best FLUX quality
}


def _get_image_model_for_tier(profile) -> str:
    """Return the Together.ai model name based on user's plan tier."""
    plan = getattr(profile, "plan", "starter") if profile else "starter"
    return TIER_IMAGE_MODELS.get(plan, TIER_IMAGE_MODELS["starter"])


# ─── PROVIDER IMPLEMENTATIONS ────────────────────────────────────────────────

def _fetch_together(prompt: str, width: int, height: int, *, model_override: str = "") -> bytes | None:
    """Together.ai — FLUX.1 (paid, tier-routed).

    Model controlled by model_override param or TOGETHER_IMAGE_MODEL setting:
      - "black-forest-labs/FLUX.1-schnell"           — ~$0.003/image (Starter)
      - "black-forest-labs/FLUX.1-krea-dev"          — ~$0.025/image (Growth)
      - "black-forest-labs/FLUX.1.1-pro"             — $0.04/image   (Pro/Agency)
    """
    api_key = getattr(settings, "TOGETHER_API_KEY", "")
    if not api_key:
        return None

    model = model_override or getattr(settings, "TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")

    response = requests.post(
        "https://api.together.xyz/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "n": 1,
            "response_format": "b64_json",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    b64 = data["data"][0]["b64_json"]
    return b64decode(b64)


def _fetch_pollinations(prompt: str, width: int, height: int) -> bytes | None:
    """Pollinations.ai — Flux Schnell via GET URL."""
    api_key = getattr(settings, "POLLINATIONS_API_KEY", "")
    if not api_key:
        return None

    model = getattr(settings, "AI_IMAGE_MODEL", "flux")
    encoded_prompt = quote(prompt, safe="")
    url = f"https://gen.pollinations.ai/image/{encoded_prompt}"

    params = {
        "width": width,
        "height": height,
        "model": model,
        "nologo": "true",
        "seed": _prompt_seed(prompt),
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "image" not in content_type:
        logger.warning("Pollinations returned non-image content-type: %s", content_type)
        return None

    if len(response.content) < 1024:
        logger.warning("Pollinations returned small image (%d bytes)", len(response.content))
        return None

    return response.content


def _fetch_huggingface(prompt: str, width: int, height: int) -> bytes | None:
    """Hugging Face Inference API — FLUX.1-schnell (free tier)."""
    api_key = getattr(settings, "HF_TOKEN", "")
    if not api_key:
        return None

    response = requests.post(
        "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "inputs": prompt,
            "parameters": {"width": width, "height": height},
        },
        timeout=45,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "image" not in content_type:
        logger.warning("HuggingFace returned non-image content-type: %s", content_type)
        return None

    if len(response.content) < 1024:
        logger.warning("HuggingFace returned small image (%d bytes)", len(response.content))
        return None

    return response.content


# Provider registry — tried in order (Together first: most reliable when configured)
PROVIDERS = [
    ("together", _fetch_together),
    ("huggingface", _fetch_huggingface),
    ("pollinations", _fetch_pollinations),
]


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def generate_post_image(post, image_prompt: str) -> str | None:
    """
    Generate an AI image for a post and save it as a MediaAttachment.
    Tries each configured provider in order until one succeeds.

    Returns:
        URL of the saved image, or None if all providers failed.
    """
    if not getattr(settings, "AI_IMAGE_GENERATION_ENABLED", False):
        return None

    if not image_prompt or not image_prompt.strip():
        return None

    # Store prompt for retry capability
    if not post.media_prompt:
        post.media_prompt = image_prompt
        post.save(update_fields=["media_prompt", "updated_at"])

    platform = post.platform or (post.social_account.platform if post.social_account else "twitter")
    width, height = PLATFORM_IMAGE_SIZES.get(platform, DEFAULT_SIZE)

    # Enhance prompt with visual style + platform-specific aesthetics
    profile = getattr(post.user, "profile", None)
    enhanced_prompt = _enhance_prompt(image_prompt, platform, profile)

    # Route to tier-appropriate image model
    tier_model = _get_image_model_for_tier(profile)

    image_bytes = _fetch_image_with_fallback(enhanced_prompt, width, height, model_override=tier_model)
    if not image_bytes:
        logger.warning("All image providers failed for post %s", post.id)
        post.media_status = "failed"
        post.media_prompt = image_prompt
        post.save(update_fields=["media_status", "media_prompt", "updated_at"])
        # Notify user so failure isn't silent
        try:
            from apps.notifications.models import Notification
            Notification.create_for_user(
                user=post.user,
                notification_type=Notification.NotificationType.SYSTEM,
                message="Image generation failed for your post. You can retry or upload an image manually.",
                related_post=post,
            )
        except Exception:
            pass  # notification is best-effort
        return None

    try:
        # Save to Django storage via MediaAttachment
        filename = f"ai_{uuid.uuid4().hex[:12]}.jpg"
        filepath = f"ai/{filename}"
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
        post.media_status = "generated"
        post.save(update_fields=["media_urls", "media_status", "updated_at"])

        logger.info(
            "Generated AI image for post %s (%s): %s",
            post.id, platform, media_url,
        )
        return media_url

    except Exception as exc:
        logger.warning(
            "AI image save failed for post %s: %s", post.id, exc,
        )
        return None


# ─── INTERNAL HELPERS ─────────────────────────────────────────────────────────

def _fetch_image_with_fallback(prompt: str, width: int, height: int, *, model_override: str = "") -> bytes | None:
    """Try each provider in order, return first successful result."""
    for name, fetcher in PROVIDERS:
        try:
            logger.debug("Trying image provider: %s", name)
            if name == "together" and model_override:
                result = fetcher(prompt, width, height, model_override=model_override)
            else:
                result = fetcher(prompt, width, height)
            if result:
                logger.info("Image generated via %s (%dx%d)", name, width, height)
                return result
        except requests.exceptions.HTTPError as exc:
            logger.warning("Provider %s HTTP error: %s", name, exc)
        except requests.exceptions.Timeout:
            logger.warning("Provider %s timed out", name)
        except Exception as exc:
            logger.warning("Provider %s failed: %s", name, exc)
    return None


def _prompt_seed(prompt: str) -> int:
    """Generate a deterministic seed from the prompt for consistent results."""
    return int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
