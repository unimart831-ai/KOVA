"""
AI Image Generation Service — carousel, story, and reel formats.

Provider chain (tries in order until one succeeds):
  1. Together AI  — FLUX.1-schnell (~$0.003/image) — set TOGETHER_API_KEY
  2. HuggingFace  — FLUX.1-schnell (free, rate-limited) — set HF_TOKEN
  3. Pollinations — Flux Schnell (free tier) — set POLLINATIONS_API_KEY

All providers run the same Black Forest Labs Flux Schnell model.

Usage:
    from apps.content.image_gen import generate_image, generate_carousel_images

    url = generate_image("A confident African business owner at her boutique, warm lighting")
    slides = generate_carousel_images([{"image_prompt": "Slide 1 prompt", "heading": "Title"}])
"""

import logging
import time
from base64 import b64decode
from typing import Optional
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


# ── Aspect ratio → pixel dimensions ──────────────────────────────────────────

ASPECT_DIMENSIONS = {
    "square":    (1024, 1024),   # Instagram feed, Facebook, LinkedIn
    "portrait":  (1024, 1280),   # Instagram portrait (4:5)
    "landscape": (1280, 720),    # LinkedIn / Facebook landscape (16:9)
    "story":     (1080, 1920),   # Instagram/Facebook Stories & Reels (9:16)
}


# ── Provider implementations ──────────────────────────────────────────────────

def _together(prompt: str, width: int, height: int) -> Optional[bytes]:
    api_key = getattr(settings, "TOGETHER_API_KEY", "")
    if not api_key:
        return None
    model = getattr(settings, "TOGETHER_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
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
    url = f"https://gen.pollinations.ai/image/{quote(prompt, safe='')}"
    resp = requests.get(
        url,
        params={"width": width, "height": height, "model": "flux", "nologo": "true"},
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


def _fetch_bytes(prompt: str, width: int, height: int) -> Optional[bytes]:
    for name, fn in _PROVIDERS:
        try:
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
    import uuid
    try:
        from apps.content.tasks import _public_url_for_file
        file_name = f"ai_images/{uuid.uuid4().hex}.jpg"
        default_storage.save(file_name, ContentFile(img_bytes))
        return _public_url_for_file(file_name)
    except Exception as exc:
        logger.warning("Failed to save generated image to storage: %s", exc)
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
