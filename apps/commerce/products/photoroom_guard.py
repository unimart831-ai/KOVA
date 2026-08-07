"""
Guardrails for Photoroom cutouts — preserve product value when segmentation fails.

Thin rings, jewelry, reflective goods, and busy backgrounds often get destroyed by
aggressive background removal. We probe uncertainty, validate output pixels, and
fall back to no-cutout studio treatments (blur + relight) instead of shipping garbage.
"""

from __future__ import annotations

import logging
from io import BytesIO

from django.conf import settings

logger = logging.getLogger(__name__)

# Categories where cutout errors are common — lower uncertainty bar, safer hero.
FRAGILE_CATEGORIES = frozenset({
    "jewelry",
    "beauty",
    "watches",
    "accessories",
})

# Variants that run background removal (subject to validation + safe fallback).
CUTOUT_VARIANT_IDS = frozenset({
    "studio_white",
    "studio_brand",
    "studio_dark",
    "relight",
    "beautify",
    "photofix",
    "flat_lay",
    "ghost_mannequin",
    "virtual_model",
    "outline",
    "marketplace_white",
    "marketplace_jpeg",
})

# Never use beautify on these — it alters product appearance.
BEAUTIFY_BLOCK_CATEGORIES = frozenset({"jewelry", "watches", "accessories"})

SAFE_HERO_VARIANT_ID = "studio_safe"


def normalize_category(category: str | None) -> str:
    return (category or "general").strip().lower()


def uncertainty_threshold_for_category(category: str | None) -> float:
    """Lower threshold for fragile goods → earlier switch to safe mode."""
    cat = normalize_category(category)
    if cat in FRAGILE_CATEGORIES:
        return float(getattr(settings, "PHOTOROOM_FRAGILE_UNCERTAINTY_THRESHOLD", 0.42))
    return float(getattr(settings, "PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD", 0.6))


def uncertainty_is_high_for_category(
    score: float | None,
    category: str | None,
) -> bool:
    if score is None:
        return False
    return score >= uncertainty_threshold_for_category(category)


def is_cutout_variant(variant_id: str) -> bool:
    vid = (variant_id or "").strip()
    if vid in CUTOUT_VARIANT_IDS:
        return True
    return vid.startswith(("ai_scene_", "ai_creative_", "ai_lifestyle"))


def should_block_beautify(category: str | None) -> bool:
    return normalize_category(category) in BEAUTIFY_BLOCK_CATEGORIES


def _subject_fill_ratio(image_bytes: bytes) -> float | None:
    """Share of center crop pixels that are not near-white (rough product mass)."""
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    w, h = img.size
    if w < 8 or h < 8:
        return None

    margin_x = int(w * 0.12)
    margin_y = int(h * 0.12)
    crop = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))
    pixels = crop.getdata()
    total = crop.width * crop.height
    if total <= 0:
        return None

    non_white = 0
    for r, g, b in pixels:
        if r < 232 or g < 232 or b < 232:
            non_white += 1
    return non_white / total


def validate_cutout_output(
    original_bytes: bytes,
    edited_bytes: bytes,
    *,
    category: str | None = None,
) -> tuple[bool, str]:
    """
    Return (ok, reason). Reject cutouts that erased most of the product.
    """
    if not getattr(settings, "PHOTOROOM_CUTOUT_VALIDATION_ENABLED", True):
        return True, ""

    orig_ratio = _subject_fill_ratio(original_bytes)
    edit_ratio = _subject_fill_ratio(edited_bytes)
    if orig_ratio is None or edit_ratio is None:
        return True, ""

    cat = normalize_category(category)
    min_edit = 0.06 if cat in FRAGILE_CATEGORIES else 0.04

    # Original had clear subject; edit lost it → bad cutout.
    if orig_ratio >= 0.18 and edit_ratio < min_edit:
        return False, "subject_erased"

    # Dramatic drop in visible product mass.
    if orig_ratio >= 0.12 and edit_ratio < orig_ratio * 0.35:
        return False, "subject_shrank"

    # Mostly empty white frame (classic destroyed ring/bracelet).
    if edit_ratio < 0.03 and orig_ratio > 0.08:
        return False, "empty_frame"

    return True, ""


def hero_variant_ids_for_context(
    *,
    category: str | None,
    uncertainty_score: float | None,
    hero_studio_ids: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Prefer safe hero when cutout confidence is low."""
    base = hero_studio_ids or ("studio_white", "studio_brand")
    if uncertainty_is_high_for_category(uncertainty_score, category):
        return (SAFE_HERO_VARIANT_ID, "background_blur", "relight_nocutout") + tuple(
            v for v in base if v not in CUTOUT_VARIANT_IDS
        )
    cat = normalize_category(category)
    if cat in FRAGILE_CATEGORIES:
        return (SAFE_HERO_VARIANT_ID,) + base
    return base
