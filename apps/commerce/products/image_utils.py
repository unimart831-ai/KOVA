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
    if not data or len(data) < 16:
        raise ValueError("Image file is empty or too small to process.")

    try:
        img = Image.open(BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError("Could not read image file — try JPEG or PNG.") from exc

    img = apply_exif_orientation(img)
    if format.upper() == "JPEG":
        img = img.convert("RGB")
    out = BytesIO()
    save_kwargs = {"optimize": True}
    if format.upper() == "JPEG":
        save_kwargs["quality"] = 92
    img.save(out, format=format, **save_kwargs)
    return out.getvalue()


def validate_uploaded_images(uploaded_files) -> str | None:
    """Return a user-facing error message if any upload is empty or unreadable."""
    for uploaded in uploaded_files:
        if hasattr(uploaded, "seek"):
            uploaded.seek(0)
        raw = uploaded.read()
        if hasattr(uploaded, "seek"):
            uploaded.seek(0)
        if not raw:
            return "Uploaded image is empty — please retake or choose another photo."
        try:
            normalize_image_bytes(raw)
        except ValueError as exc:
            return str(exc)
    return None


def normalize_uploaded_image(uploaded_file) -> ContentFile:
    """Normalize an uploaded image file (EXIF upright, JPEG)."""
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    raw = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    if not raw:
        raise ValueError("Uploaded image is empty — please retake or choose another photo.")
    normalized = normalize_image_bytes(raw)
    base = (getattr(uploaded_file, "name", None) or "photo").rsplit(".", 1)[0]
    return ContentFile(normalized, name=f"{base}.jpg")
