"""
Image utilities for the Media Queue.

Handles platform-specific auto-cropping so users don't have to think
about aspect ratios — they upload, Kova adapts.
"""

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

# Recommended aspect ratios (width : height) per platform
PLATFORM_CROPS = {
    "instagram": (1, 1),       # Square 1080×1080
    "facebook":  (1.91, 1),    # Landscape 1200×628
    "twitter":   (16, 9),      # Landscape 1200×675
    "linkedin":  (1.91, 1),    # Landscape 1200×628
    "tiktok":    (9, 16),      # Portrait 1080×1920
    "pinterest": (2, 3),       # Portrait 1000×1500
    "youtube":   (16, 9),      # Landscape
}

# Max pixel dimensions after crop
PLATFORM_MAX_SIZE = {
    "instagram": (1080, 1080),
    "facebook":  (1200, 628),
    "twitter":   (1200, 675),
    "linkedin":  (1200, 628),
    "tiktok":    (1080, 1920),
    "pinterest": (1000, 1500),
    "youtube":   (1280, 720),
}

DEFAULT_CROP = (1, 1)
DEFAULT_SIZE = (1080, 1080)


def auto_crop(image_file, platform: str) -> bytes:
    """
    Center-crop an image to the platform's aspect ratio and resize.

    Args:
        image_file: File-like object or path to the image.
        platform: Target social platform (instagram, facebook, etc.)

    Returns:
        JPEG bytes of the cropped image.
    """
    img = Image.open(image_file)
    img = img.convert("RGB")  # Ensure RGB for JPEG

    target_ratio_w, target_ratio_h = PLATFORM_CROPS.get(platform, DEFAULT_CROP)
    target_ratio = target_ratio_w / target_ratio_h

    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h

    if abs(orig_ratio - target_ratio) < 0.01:
        # Already close enough — no crop needed
        cropped = img
    elif orig_ratio > target_ratio:
        # Image is wider than target — crop sides
        new_w = int(orig_h * target_ratio)
        left = (orig_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, orig_h))
    else:
        # Image is taller than target — crop top/bottom
        new_h = int(orig_w / target_ratio)
        top = (orig_h - new_h) // 2
        cropped = img.crop((0, top, orig_w, top + new_h))

    # Resize to platform's recommended max size
    max_w, max_h = PLATFORM_MAX_SIZE.get(platform, DEFAULT_SIZE)
    if cropped.width > max_w or cropped.height > max_h:
        cropped.thumbnail((max_w, max_h), Image.LANCZOS)

    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()
