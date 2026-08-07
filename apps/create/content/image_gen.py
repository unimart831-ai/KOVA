"""
AI Image Generation Service — post, carousel, story, and reel formats.

Provider chain (tries in order until one succeeds):
  1. Together AI  — FLUX (tier-routed for posts) — set TOGETHER_API_KEY
  2. HuggingFace  — FLUX.1-schnell (free, rate-limited) — set HF_TOKEN
  3. Pollinations — Flux Schnell (free tier) — set POLLINATIONS_API_KEY

Usage:
    from apps.create.content.image_gen import generate_image, generate_post_image

    url = generate_image("A confident African business owner at her boutique, warm lighting")
    post_url = generate_post_image(post, "Boutique storefront at golden hour")
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from base64 import b64decode
from typing import Optional
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.create.content.models import MediaAttachment

logger = logging.getLogger(__name__)


# ── Aspect ratio → pixel dimensions ──────────────────────────────────────────

ASPECT_DIMENSIONS = {
    "square":    (1024, 1024),   # Instagram feed, Facebook, LinkedIn
    "portrait":  (1024, 1280),   # Instagram portrait (4:5)
    "landscape": (1280, 720),    # LinkedIn / Facebook landscape (16:9)
    "story":     (1080, 1920),   # Instagram/Facebook Stories & Reels (9:16)
}

# Optimal image dimensions per platform (post generation)
PLATFORM_IMAGE_SIZES = {
    "twitter": (1200, 675),
    "linkedin": (1200, 627),
    "instagram": (1080, 1080),
    "facebook": (1200, 630),
    "tiktok": (1080, 1920),
    "youtube": (1280, 720),
    "pinterest": (1000, 1500),
    "threads": (1080, 1080),
    "bluesky": (1200, 675),
}

DEFAULT_SIZE = (1200, 675)

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

TIER_IMAGE_MODELS = {
    "starter": "black-forest-labs/FLUX.1-schnell",
    "growth":  "black-forest-labs/FLUX.1-krea-dev",
    "pro":     "black-forest-labs/FLUX.1.1-pro",
    "agency":  "black-forest-labs/FLUX.1.1-pro",
}


def _enhance_prompt(prompt: str, platform: str, profile=None) -> str:
    """Inject visual_style prefix and platform-specific suffix into the image prompt."""
    parts = []
    visual_style = getattr(profile, "visual_style", "auto") if profile else "auto"
    style_prefix = VISUAL_STYLE_PREFIX.get(visual_style, "")
    if style_prefix:
        parts.append(style_prefix)
    parts.append(prompt.strip())
    suffix = PLATFORM_PROMPT_SUFFIX.get(platform, "")
    if suffix:
        parts.append(suffix)
    return " ".join(parts)


def _get_image_model_for_tier(profile) -> str:
    """Return the image model name based on user's plan tier."""
    plan = getattr(profile, "plan", "starter") if profile else "starter"
    try:
        from apps.create.agents.models import LLMConfig
        config = LLMConfig.load()
        if config.pk:
            model, _provider = config.get_image_model(plan)
            if model:
                return model
    except Exception:
        pass
    return TIER_IMAGE_MODELS.get(plan, TIER_IMAGE_MODELS["starter"])


# ── Provider implementations ──────────────────────────────────────────────────

def _together(prompt: str, width: int, height: int, *, model_override: str = "") -> Optional[bytes]:
    api_key = getattr(settings, "TOGETHER_API_KEY", "")
    if not api_key:
        return None
    model = model_override or getattr(settings, "TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    resp = requests.post(
        "https://api.together.xyz/v1/images/generations",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "prompt": prompt, "width": width, "height": height,
              "n": 1, "response_format": "b64_json"},
        timeout=45,
    )
    resp.raise_for_status()
    b64 = resp.json()["data"][0]["b64_json"]
    return b64decode(b64)


def _huggingface(prompt: str, width: int, height: int) -> Optional[bytes]:
    api_key = getattr(settings, "HF_TOKEN", "")
    if not api_key:
        return None
    resp = requests.post(
        "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"inputs": prompt, "parameters": {"width": width, "height": height}},
        timeout=60,
    )
    resp.raise_for_status()
    if "image" not in resp.headers.get("content-type", "") or len(resp.content) < 1024:
        return None
    return resp.content


def _pollinations(prompt: str, width: int, height: int) -> Optional[bytes]:
    api_key = getattr(settings, "POLLINATIONS_API_KEY", "")
    if not api_key:
        return None
    model = getattr(settings, "AI_IMAGE_MODEL", "flux")
    url = f"https://gen.pollinations.ai/image/{quote(prompt, safe='')}"
    resp = requests.get(
        url,
        params={
            "width": width,
            "height": height,
            "model": model,
            "nologo": "true",
            "seed": _prompt_seed(prompt),
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=45,
    )
    resp.raise_for_status()
    if "image" not in resp.headers.get("content-type", "") or len(resp.content) < 1024:
        return None
    return resp.content


_PROVIDERS = [
    ("together",     _together),
    ("huggingface",  _huggingface),
    ("pollinations", _pollinations),
]


def _prompt_seed(prompt: str) -> int:
    return int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)


def _fetch_bytes(prompt: str, width: int, height: int, *, model_override: str = "") -> Optional[bytes]:
    for name, fn in _PROVIDERS:
        try:
            if name == "together" and model_override:
                result = fn(prompt, width, height, model_override=model_override)
            else:
                result = fn(prompt, width, height)
            if result:
                logger.info("Image generated via %s (%dx%d)", name, width, height)
                return result
        except requests.exceptions.HTTPError as exc:
            logger.warning("Provider %s HTTP %s", name, exc.response.status_code if exc.response else exc)
        except requests.exceptions.Timeout:
            logger.warning("Provider %s timed out", name)
        except Exception as exc:
            logger.warning("Provider %s failed: %s", name, exc)
    return None


def _save_bytes_to_storage(img_bytes: bytes) -> Optional[str]:
    try:
        from apps.create.content.tasks import _public_url_for_file
        file_name = f"ai_images/{uuid.uuid4().hex}.jpg"
        default_storage.save(file_name, ContentFile(img_bytes))
        return _public_url_for_file(file_name)
    except Exception as exc:
        logger.warning("Failed to save generated image to storage: %s", exc)
    return None


def _get_public_url(file_name: str) -> str | None:
    """Generate a public URL for a storage file, avoiding circular imports."""
    import os

    try:
        url = default_storage.url(file_name)
        if url.startswith(("http://", "https://")):
            return url
        custom_domain = (
            getattr(settings, "AWS_S3_CUSTOM_DOMAIN", "")
            or os.environ.get("AWS_S3_CUSTOM_DOMAIN", "")
        )
        if custom_domain:
            location = (
                getattr(settings, "AWS_LOCATION", "")
                or os.environ.get("AWS_LOCATION", "media")
            )
            prefix = f"{location}/" if location else ""
            return f"https://{custom_domain}/{prefix}{file_name}"
    except Exception:
        pass
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def generate_image(prompt: str, aspect_ratio: str = "square") -> Optional[str]:
    """
    Generate a single image and return a public HTTPS URL, or None on failure.
    """
    if not prompt or not prompt.strip():
        return None
    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1024, 1024))
    img_bytes = _fetch_bytes(prompt, width, height)
    if not img_bytes:
        return None
    return _save_bytes_to_storage(img_bytes)


def generate_post_image(post, image_prompt: str) -> str | None:
    """
    Generate an AI image for a post and save it as a MediaAttachment.
    Tries each configured provider in order until one succeeds.

    Returns:
        URL of the saved image, or None if all providers failed.
    """
    if not getattr(settings, "AI_IMAGE_GENERATION_ENABLED", False):
        return None

    try:
        from apps.create.agents.models import LLMConfig
        config = LLMConfig.load()
        if config.pk and not config.image_enabled:
            logger.info("Image generation disabled via admin dashboard")
            return None
    except Exception:
        pass

    if not image_prompt or not image_prompt.strip():
        return None

    if not post.media_prompt:
        post.media_prompt = image_prompt
        post.save(update_fields=["media_prompt", "updated_at"])

    platform = post.platform or (post.social_account.platform if post.social_account else "twitter")
    width, height = PLATFORM_IMAGE_SIZES.get(platform, DEFAULT_SIZE)

    profile = getattr(post.user, "profile", None)
    enhanced_prompt = _enhance_prompt(image_prompt, platform, profile)
    tier_model = _get_image_model_for_tier(profile)

    image_bytes = _fetch_bytes(enhanced_prompt, width, height, model_override=tier_model)
    if not image_bytes:
        logger.warning("All image providers failed for post %s", post.id)
        post.media_status = "failed"
        post.media_prompt = image_prompt
        post.save(update_fields=["media_status", "media_prompt", "updated_at"])
        try:
            from apps.messaging.notifications.models import Notification
            Notification.create_for_user(
                user=post.user,
                notification_type=Notification.NotificationType.SYSTEM,
                message="Image generation failed for your post. You can retry or upload an image manually.",
                related_post=post,
            )
        except Exception:
            pass
        return None

    try:
        filename = f"ai_{uuid.uuid4().hex[:12]}.jpg"
        filepath = f"ai/{filename}"
        attachment = MediaAttachment(
            post=post,
            file_type="image",
            alt_text=image_prompt[:500],
            order=0,
        )
        attachment.file.save(filepath, ContentFile(image_bytes), save=True)

        media_url = _get_public_url(attachment.file.name) or attachment.file.url
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
        post.media_status = "failed"
        post.save(update_fields=["media_status", "updated_at"])
        return None


# ── Reel scene prompts — clean, minimal, scroll-stopping ─────────────────────

REEL_SCENE_SUFFIX = (
    "Ultra-clean composition, soft diffused natural light, uncluttered background, "
    "premium e-commerce quality, shallow depth of field, no text, no watermark, no logos."
)

REEL_SCENE_VARIANTS = (
    "Hero close-up, product centered, soft studio lighting",
    "Lifestyle context, product on a clean minimal surface, warm natural daylight",
    "Alternate angle, three-quarter view, airy negative space, editorial product photography",
    "Detail or use-context shot, subtle environment blur, polished marketing aesthetic",
)


def build_reel_scene_prompts(
    subject: str,
    base_prompt: str = "",
    *,
    count: int = 4,
) -> list[str]:
    """Build distinct 9:16 scene prompts for a multi-slide reel."""
    subject = (subject or "the product").strip()
    base = (base_prompt or f"Vertical 9:16 cinematic product photo of {subject}").strip().rstrip(".")
    prompts: list[str] = []
    for i in range(min(count, len(REEL_SCENE_VARIANTS))):
        variant = REEL_SCENE_VARIANTS[i]
        prompts.append(f"{base}. {variant}. {REEL_SCENE_SUFFIX}")
    while len(prompts) < count:
        prompts.append(f"{base}. Scene {len(prompts) + 1}. {REEL_SCENE_SUFFIX}")
    return prompts[:count]


def generate_reel_images(
    subject: str,
    base_prompt: str = "",
    *,
    count: int = 4,
) -> list[str]:
    """Generate multiple 9:16 frames for a motion reel."""
    urls: list[str] = []
    for i, prompt in enumerate(build_reel_scene_prompts(subject, base_prompt, count=count)):
        logger.info("Generating reel frame %d/%d: %s…", i + 1, count, prompt[:70])
        url = generate_image(prompt, aspect_ratio="story")
        if url:
            urls.append(url)
        if i < count - 1:
            time.sleep(0.5)
    return urls


def generate_carousel_images(slides: list, aspect_ratio: str = "square") -> list:
    """
    Generate images for carousel slides that have an image_prompt but no image_url.

    Mutates each slide dict in-place (adds/updates ``image_url``).
    Each slide: {"heading": str, "body": str, "image_prompt": str, "image_url": str}
    """
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        if slide.get("image_url"):
            continue
        prompt = slide.get("image_prompt", "").strip()
        if not prompt:
            continue
        logger.info("Generating carousel slide %d image: %s…", i + 1, prompt[:60])
        url = generate_image(prompt, aspect_ratio)
        if url:
            slide["image_url"] = url
        else:
            logger.warning("Image generation failed for carousel slide %d", i + 1)
        if i < len(slides) - 1:
            time.sleep(0.5)
    return slides
