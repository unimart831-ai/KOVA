"""Product image loading — EXIF orientation and upload normalization."""

from __future__ import annotations

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def apply_exif_orientation(image: Image.Image) -> Image.Image:
    """Rotate image to upright using EXIF metadata (phone camera photos)."""
    try:
        return ImageOps.exif_transpose(image)
    except Exception as exc:
        logger.debug("EXIF transpose skipped: %s", exc)
        return image


def normalize_image_bytes(data: bytes, *, format: str = "JPEG") -> bytes:
    """Return upright image bytes suitable for storage / processing."""
    img = Image.open(BytesIO(data))
    img = apply_exif_orientation(img)
    if format.upper() == "JPEG":
        img = img.convert("RGB")
    out = BytesIO()
    save_kwargs = {"optimize": True}
    if format.upper() == "JPEG":
        save_kwargs["quality"] = 92
    img.save(out, format=format, **save_kwargs)
    return out.getvalue()


def normalize_uploaded_image(uploaded_file) -> ContentFile:
    """Normalize an uploaded image file (EXIF upright, JPEG)."""
    raw = uploaded_file.read()
    uploaded_file.seek(0)
    normalized = normalize_image_bytes(raw)
    base = (uploaded_file.name or "photo").rsplit(".", 1)[0]
    return ContentFile(normalized, name=f"{base}.jpg")
