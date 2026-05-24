"""
Backwards-compatible shim — studio polish is implemented in photoroom.py.

Bria/fal.ai was replaced by Photoroom Basic (see docs/VISUAL_ENHANCEMENT_SPEC.md).
"""

from __future__ import annotations

from apps.products.photoroom import (
    photoroom_enabled,
    pick_background_color_hex,
    save_studio_polish_image,
    studio_polish_via_photoroom,
)

visual_enhance_enabled = photoroom_enabled
save_pro_scene_image = save_studio_polish_image


def build_scene_prompt(product, analysis: dict | None = None) -> str:
    """Legacy name — returns background hex for Photoroom Basic."""
    return pick_background_color_hex(product)


def generate_bria_product_shot(image_url: str, scene_description: str) -> bytes | None:
    """Legacy name — routes to Photoroom Basic v1/segment."""
    bg = scene_description.lstrip("#")[:6] if scene_description else "FFFFFF"
    if len(bg) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in bg):
        bg = "FFFFFF"
    return studio_polish_via_photoroom(image_url, background_color=bg)
