"""
Photoroom Remove Background API (Basic plan) — cutout + color background.

Uses POST https://sdk.photoroom.com/v1/segment (NOT Image Editing v2 / Plus).

See:
- https://docs.photoroom.com/remove-background-api-basic-plan/quickstart-guide
- https://docs.photoroom.com/remove-background-api-basic-plan/background-color-size-and-crop
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

logger = logging.getLogger(__name__)

STUDIO_POLISH_FOLDER = "studio_polish"
PHOTOROOM_SEGMENT_URL = "https://sdk.photoroom.com/v1/segment"
CANVAS_SIZE = (1080, 1080)
JPEG_QUALITY = 92


def photoroom_enabled() -> bool:
    if not getattr(settings, "VISUAL_ENHANCE_ENABLED", True):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def pick_background_color_hex(product, brand_colors: dict | None = None) -> str:
    """Solid studio background for Basic tier (no AI scenes)."""
    brand_colors = brand_colors or {}
    primary = (brand_colors.get("primary") or "#FFFFFF").lstrip("#").upper()
    if len(primary) == 6 and primary not in ("FFFFFF", "FFF"):
        return primary

    name = (product.name or "").lower()
    tags = " ".join(product.tags or []).lower()
    blob = f"{name} {tags}"
    if any(w in blob for w in ("luxury", "premium", "gold", "watch", "jewel")):
        return "1A1A2E"
    if any(w in blob for w in ("beauty", "cream", "lotion", "skin", "cosmetic")):
        return "E8F4FC"
    return "FFFFFF"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#").upper()[:6]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _load_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    """Load image bytes for multipart upload (Basic API requires image_file)."""
    from apps.agents.carousel import _load_product_image

    if image_url.startswith(("http://", "https://")):
        try:
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
            return resp.content, "image.jpg"
        except Exception as exc:
            logger.warning("Photoroom source download failed: %s", exc)
            return None

    rgb = _load_product_image(image_url)
    if rgb is None:
        return None
    buf = BytesIO()
    rgb.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), "product.jpg"


def _fit_to_square_jpeg(image_bytes: bytes, *, background_color: str) -> bytes:
    """Basic API has no outputSize — normalize to 1080×1080 locally (free)."""
    bg = _hex_to_rgb(background_color)
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail(CANVAS_SIZE, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", CANVAS_SIZE, bg)
    x = (CANVAS_SIZE[0] - img.width) // 2
    y = (CANVAS_SIZE[1] - img.height) // 2
    canvas.paste(img, (x, y))
    out = BytesIO()
    canvas.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def studio_polish_via_photoroom(
    image_url: str,
    *,
    background_color: str = "FFFFFF",
    size: str = "hd",
) -> bytes | None:
    """
    Photoroom Basic v1/segment: remove background + solid color background.

    Params per docs: bg_color, size (preview|medium|hd|full), format, crop.
    Returns 1080×1080 JPEG bytes or None.
    """
    api_key = getattr(settings, "PHOTOROOM_API_KEY", "")
    if not api_key:
        logger.info("Studio polish skipped: PHOTOROOM_API_KEY not set")
        return None

    bg = background_color.lstrip("#").upper()[:6]
    bg_color_param = f"#{bg}"
    api_key = api_key.strip()
    if getattr(settings, "PHOTOROOM_SANDBOX", False) and not api_key.startswith("sandbox_"):
        api_key = f"sandbox_{api_key}"
    headers = {"x-api-key": api_key}

    loaded = _load_image_bytes(image_url)
    if not loaded:
        logger.warning("Studio polish: could not load source image")
        return None
    file_bytes, filename = loaded

    try:
        resp = requests.post(
            PHOTOROOM_SEGMENT_URL,
            headers=headers,
            files={"image_file": (filename, file_bytes, "image/jpeg")},
            data={
                "bg_color": bg_color_param,
                "size": size,
                "format": "jpg",
                "crop": "false",
            },
            timeout=120,
        )
        resp.raise_for_status()
        if not resp.content:
            return None
        return _fit_to_square_jpeg(resp.content, background_color=bg)
    except Exception as exc:
        logger.error("Photoroom v1/segment failed: %s", exc)
        return None


def save_studio_polish_image(product_id, image_bytes: bytes, suffix: str = "hero") -> str:
    from apps.content.tasks import _public_url_for_file

    filename = f"{STUDIO_POLISH_FOLDER}/{product_id}/{suffix}_{uuid.uuid4().hex[:10]}.jpg"
    saved = default_storage.save(filename, ContentFile(image_bytes))
    return _public_url_for_file(saved)
