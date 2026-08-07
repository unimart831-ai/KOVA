"""
Photoroom Image Editing API (Plus) — cutout, studio background, shadow, resize.

Uses https://image-api.photoroom.com/v2/edit (NOT Basic v1/segment).

See docs/VISUAL_ENHANCEMENT_SPEC.md and:
https://docs.photoroom.com/image-editing-api-plus-plan/quickstart-guide
"""

from __future__ import annotations

import logging
import uuid
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

STUDIO_POLISH_FOLDER = "studio_polish"
PHOTOROOM_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
CANVAS_SIZE = (1080, 1080)
JPEG_QUALITY = 92


def photoroom_enabled() -> bool:
    if not getattr(settings, "VISUAL_ENHANCE_ENABLED", True):
        return False
    return bool(getattr(settings, "PHOTOROOM_API_KEY", ""))


def studio_polish_unavailable_message() -> str | None:
    """Short UI copy when Studio polish cannot call Photoroom."""
    if not getattr(settings, "VISUAL_ENHANCE_ENABLED", True):
        return "Studio polish is off on this server — use as-is or try again later."
    if not photoroom_enabled():
        return "Photoroom is not configured — use as-is or contact support."
    return None


def studio_polish_failure_message(reason: str | None) -> str | None:
    """User-facing copy when Studio polish could not complete."""
    messages = {
        "photoroom_not_configured": "Studio polish isn’t configured — your original photo was kept.",
        "photoroom_failed": "Studio polish failed — your original photo was kept.",
        "save_failed": "Couldn’t save studio polish — your original photo was kept.",
        "at_limit": "Studio polish credits used up — your original photo was kept.",
        "platform_blocked": "Studio polish is at capacity — your original photo was kept.",
    }
    return messages.get(reason or "")


def pick_background_color_hex(product, brand_colors: dict | None = None) -> str:
    """Solid studio background for Plus static background."""
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


def _api_key_headers() -> tuple[str, dict] | tuple[None, dict]:
    api_key = getattr(settings, "PHOTOROOM_API_KEY", "").strip()
    if not api_key:
        return None, {}
    if getattr(settings, "PHOTOROOM_SANDBOX", False) and not api_key.startswith("sandbox_"):
        api_key = f"sandbox_{api_key}"
    return api_key, {"x-api-key": api_key}


def _resolve_public_image_url(image_url: str) -> str | None:
    if image_url.startswith(("http://", "https://")):
        return image_url

    from apps.create.content.tasks import _public_url_for_file

    path = image_url.lstrip("/")
    if path.startswith("media/"):
        path = path[6:]
    public = _public_url_for_file(path)
    if public.startswith("http"):
        return public
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    if site:
        return f"{site}/{public.lstrip('/')}"
    return None


def _load_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    from apps.create.agents.carousel import _load_product_image

    if image_url.startswith(("http://", "https://")):
        try:
            import httpx

            resp = httpx.get(image_url, timeout=60, follow_redirects=True)
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


def _download_bytes_for_preflight(image_url: str) -> bytes | None:
    """Load raw bytes for local quality metrics."""
    loaded = _load_image_bytes(image_url)
    return loaded[0] if loaded else None


def _edit_params(
    *,
    background_color: str,
    output_size: str,
    padding: str,
    shadow_mode: str,
    export_format: str,
) -> dict:
    bg = background_color.lstrip("#").upper()[:6]
    return {
        "removeBackground": "true",
        "background.color": bg,
        "outputSize": output_size,
        "padding": padding,
        "shadow.mode": shadow_mode,
        "export.format": export_format,
    }


def studio_polish_via_photoroom(
    image_url: str,
    *,
    background_color: str = "FFFFFF",
    output_size: str | None = None,
    padding: str | None = None,
    shadow_mode: str | None = None,
    export_format: str = "jpeg",
) -> bytes | None:
    """Single studio Plus call (legacy helper / tests)."""
    from apps.commerce.products.photoroom_plus import photoroom_edit

    output_size = output_size or getattr(settings, "PHOTOROOM_OUTPUT_SIZE", "1080x1080")
    padding = padding if padding is not None else str(getattr(settings, "PHOTOROOM_PADDING", 0.12))
    shadow_mode = shadow_mode or getattr(settings, "PHOTOROOM_DEFAULT_SHADOW", "ai.soft")
    params = _edit_params(
        background_color=background_color,
        output_size=output_size,
        padding=padding,
        shadow_mode=shadow_mode,
        export_format=export_format,
    )
    params["referenceBox"] = "originalImage"
    result = photoroom_edit(image_url, params)
    return result.content if result.ok else None


def save_studio_polish_image(product_id, image_bytes: bytes, suffix: str = "hero") -> str:
    from apps.create.content.tasks import _public_url_for_file

    ext = "jpg" if image_bytes[:3] == b"\xff\xd8\xff" else "png"
    filename = f"{STUDIO_POLISH_FOLDER}/{product_id}/{suffix}_{uuid.uuid4().hex[:10]}.{ext}"
    saved = default_storage.save(filename, ContentFile(image_bytes))
    return _public_url_for_file(saved)


# Legacy alias — Basic routing lives in photoroom_basic.py (Phase 2)
studio_polish_via_photoroom_basic = studio_polish_via_photoroom
