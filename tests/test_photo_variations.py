"""Tests for zero-cost product photo expansion."""

from unittest.mock import patch

import pytest
from PIL import Image

from apps.commerce.products.photo_variations import (
    PRESET_PROMO_FRAME,
    PRESET_SOFT_PASTEL,
    PRESET_WHITE_STUDIO,
    _dominant_hex_colors,
    _render_preset,
    _render_promo_from_hero,
    remove_product_background,
    select_presets,
    variation_storage_marker,
)


class _FakeProduct:
    def __init__(self, name="Amara Body Lotion", tags=None, offering_type="product"):
        self.name = name
        self.tags = tags or ["beauty", "skincare"]
        self.offering_type = offering_type


def test_select_presets_beauty_product():
    presets = select_presets(_FakeProduct())
    assert PRESET_SOFT_PASTEL in presets
    assert PRESET_PROMO_FRAME in presets
    assert len(presets) == 4


def test_select_presets_generic_product():
    presets = select_presets(_FakeProduct(name="USB Cable", tags=["electronics"]))
    assert PRESET_WHITE_STUDIO in presets
    assert PRESET_SOFT_PASTEL not in presets


def test_dominant_hex_colors():
    img = Image.new("RGB", (200, 200), (30, 120, 200))
    colors = _dominant_hex_colors(img)
    assert len(colors) >= 1
    assert colors[0].startswith("#")


def test_variation_storage_marker():
    pid = "abc-123"
    assert variation_storage_marker(pid) == f"product_variations/{pid}/"


def test_remove_background_fallback_without_rembg():
    img = Image.new("RGB", (100, 100), (200, 50, 50))
    with patch.dict("sys.modules", {"rembg": None}):
        rgba = remove_product_background(img)
    assert rgba.mode == "RGBA"
    assert rgba.getbbox() is not None


def test_render_white_studio_preset():
    fg = Image.new("RGBA", (80, 120), (0, 0, 200, 255))
    rgb = Image.new("RGB", (100, 100), (200, 200, 200))
    out = _render_preset(
        PRESET_WHITE_STUDIO,
        fg,
        rgb,
        product_name="Test Product",
        display_price="KES 350",
        shop_hint="Shop link",
        dominant_colors=["#336699", "#112233"],
        brand_colors={
            "primary": "#1A1A2E",
            "secondary": "#16213E",
            "accent": "#E94560",
            "text": "#FFFFFF",
            "text_muted": "#B0B0B0",
        },
    )
    assert out.size == (1080, 1080)
    assert out.mode == "RGB"


def test_render_promo_from_hero_long_title():
    hero = Image.new("RGB", (800, 800), (255, 255, 255))
    colors = {
        "primary": "#1A1A2E",
        "secondary": "#16213E",
        "accent": "#E94560",
        "text": "#FFFFFF",
        "text_muted": "#B0B0B0",
    }
    out = _render_promo_from_hero(
        hero,
        product_name="ORAIMO Power Bank 20000mAh Fast Charge",
        display_price="KES 4,300",
        shop_hint="Shop link in bio",
        colors=colors,
    )
    assert out.size == (1080, 1080)
    # Product stays in left column — right side should remain dark (text area).
    right_px = out.getpixel((950, 200))
    assert sum(right_px) < 400
