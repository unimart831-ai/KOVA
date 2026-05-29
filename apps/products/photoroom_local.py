"""
Local image fallbacks when Photoroom expand/uncrop is unavailable.

Keeps Snap usable with letterboxed story/banner assets from the hero JPEG.
"""

from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def _parse_size(size: str) -> tuple[int, int]:
    parts = (size or "1080x1080").lower().split("x")
    if len(parts) != 2:
        return 1080, 1080
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 1080, 1080


def letterbox_image_bytes(image_bytes: bytes, target_size: str, *, bg_rgb=(255, 255, 255)) -> bytes | None:
    """Fit image into target WxH canvas with white letterboxing (no AI)."""
    try:
        target_w, target_h = _parse_size(target_size)
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        fitted = ImageOps.contain(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), bg_rgb)
        x = (target_w - fitted.width) // 2
        y = (target_h - fitted.height) // 2
        canvas.paste(fitted, (x, y))
        buf = BytesIO()
        canvas.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Local letterbox failed: %s", exc)
        return None


def letterbox_from_url(image_url: str, target_size: str) -> bytes | None:
    from apps.products.photoroom import _load_image_bytes

    loaded = _load_image_bytes(image_url)
    if not loaded:
        return None
    return letterbox_image_bytes(loaded[0], target_size)
