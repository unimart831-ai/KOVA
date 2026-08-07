"""Tests for Photoroom cutout guardrails and reel curation."""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from apps.commerce.products.photoroom_guard import (
    SAFE_HERO_VARIANT_ID,
    validate_cutout_output,
    uncertainty_is_high_for_category,
    should_block_beautify,
)
from apps.commerce.products.reel_curation import curate_reel_image_urls


def _jpeg_with_subject(*, subject_ratio: float = 0.4) -> bytes:
    """Square image with a dark subject blob in the center."""
    img = Image.new("RGB", (400, 400), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    size = int(400 * subject_ratio)
    offset = (400 - size) // 2
    draw.ellipse(
        [offset, offset, offset + size, offset + size],
        fill=(120, 90, 40),
    )
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_validate_cutout_rejects_erased_subject():
    original = _jpeg_with_subject(subject_ratio=0.45)
    destroyed = _jpeg_with_subject(subject_ratio=0.0)
    ok, reason = validate_cutout_output(original, destroyed, category="jewelry")
    assert not ok
    assert reason in {"subject_erased", "empty_frame", "subject_shrank"}


def test_validate_cutout_accepts_good_edit():
    original = _jpeg_with_subject(subject_ratio=0.4)
    edited = _jpeg_with_subject(subject_ratio=0.35)
    ok, reason = validate_cutout_output(original, edited, category="general")
    assert ok
    assert reason == ""


def test_fragile_category_lower_uncertainty_threshold():
    assert uncertainty_is_high_for_category(0.44, "jewelry")
    assert not uncertainty_is_high_for_category(0.44, "general")


def test_beautify_blocked_for_jewelry():
    assert should_block_beautify("jewelry")
    assert not should_block_beautify("food")


def test_curate_reel_prefers_studio_and_caps_slides():
    urls = [
        "https://cdn.example.com/studio_polish/p1/preflight_relight.jpg",
        "https://cdn.example.com/studio_polish/p1/studio_white.jpg",
        "https://cdn.example.com/studio_polish/p1/ai_scene_marble.jpg",
        "https://cdn.example.com/studio_polish/p1/ai_scene_wall.jpg",
        "https://cdn.example.com/studio_polish/p1/ai_creative_podium.jpg",
        "https://cdn.example.com/studio_polish/p1/promo_frame.jpg",
    ]
    curated = curate_reel_image_urls(urls, max_slides=5)
    assert "preflight_relight" not in curated[0]
    assert any("studio_white" in u for u in curated)
    assert len(curated) <= 5
    assert sum(1 for u in curated if "ai_" in u) <= 2


def test_curate_single_product_returns_one_slide():
    urls = ["https://cdn.example.com/studio_polish/p1/studio_white.jpg"]
    assert curate_reel_image_urls(urls) == urls


def test_studio_safe_variant_in_catalog():
    from apps.commerce.products.photoroom_plus import PLUS_VARIANT_CATALOG

    spec = PLUS_VARIANT_CATALOG[SAFE_HERO_VARIANT_ID]
    assert spec.params.get("removeBackground") == "false"
