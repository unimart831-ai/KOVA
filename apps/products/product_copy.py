"""
Product copy enrichment — improved names, multi-sentence descriptions, carousel story plans.
"""

from __future__ import annotations

import re

from apps.products.commerce_autopilot import (
    is_placeholder_product_name,
    sanitize_product_name,
)

VAGUE_CATEGORY_WORDS = frozenset({
    "tv", "television", "phone", "laptop", "shoes", "shoe", "bag", "watch",
    "cream", "lotion", "charger", "speaker", "headphones", "headphone", "tablet",
    "monitor", "fridge", "cooker", "microwave", "sofa", "bed", "dress", "shirt",
    "powerbank", "power", "bank", "cable", "usb", "fan", "iron", "blender",
})

SIZE_HINT_RE = re.compile(
    r"^(\d+\s*[\"']?\s*(inch|in|cm|mm)?\s*)?[a-z0-9\s\"']{1,40}$",
    re.I,
)


def split_description_sentences(text: str) -> list[str]:
    """Split prose into sentence chunks."""
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def should_improve_product_name(name: str, analysis: dict | None = None) -> bool:
    """True when the seller title is placeholder-like or too vague for catalog/search."""
    if is_placeholder_product_name(name):
        return True
    n = sanitize_product_name(name)
    if not n:
        return True

    analysis = analysis or {}
    if sanitize_product_name(analysis.get("improved_name")):
        return True

    lower = n.lower()
    words = [w for w in re.split(r"\s+", lower) if w]
    if len(n) <= 18 and len(words) <= 3:
        if any(w in VAGUE_CATEGORY_WORDS for w in words):
            return True
        if re.match(r"^\d+\s*[\"']?\s*\w+$", lower):
            return True
        if SIZE_HINT_RE.match(lower) and len(words) <= 2:
            return True

    detected = sanitize_product_name(analysis.get("detected_name") or "")
    if detected and len(detected) > len(n) + 8:
        return True

    return False


def improve_product_name(current_name: str, analysis: dict | None) -> str:
    """Build a polished catalog title from seller hint + vision analysis."""
    analysis = analysis or {}
    user_hint = sanitize_product_name(current_name)

    improved = sanitize_product_name(analysis.get("improved_name") or "")
    if improved:
        return improved[:200]

    detected = sanitize_product_name(
        analysis.get("detected_name")
        or analysis.get("product_name")
        or analysis.get("name_on_package")
        or ""
    )
    brand = sanitize_product_name(analysis.get("brand") or analysis.get("brand_name") or "")

    if not detected and brand:
        variant = sanitize_product_name(analysis.get("variant") or analysis.get("product_line") or "")
        detected = sanitize_product_name(f"{brand} {variant}".strip())

    if detected:
        if user_hint and user_hint.lower() in detected.lower():
            return detected[:200]
        if len(detected) >= len(user_hint) + 5:
            return detected[:200]
        if brand and brand.lower() not in user_hint.lower():
            merged = f"{brand} {user_hint}".strip()
            if len(merged) > len(user_hint):
                return merged[:200]
        return detected[:200]

    if brand and user_hint and brand.lower() not in user_hint.lower():
        return f"{brand} {user_hint}"[:200]

    return user_hint[:200]


def format_product_description(text: str, analysis: dict | None = None) -> str:
    """
    Normalize to 3–4 sentences separated by blank lines (not one dense paragraph).
    """
    analysis = analysis or {}
    raw_sentences = analysis.get("description_sentences")
    if isinstance(raw_sentences, list):
        cleaned = [str(s).strip() for s in raw_sentences if str(s).strip()]
        if len(cleaned) >= 2:
            return "\n\n".join(cleaned[:4])[:1000]

    source = (text or analysis.get("description") or "").strip()
    if not source:
        return ""

    sentences = split_description_sentences(source)
    if len(sentences) >= 2:
        return "\n\n".join(sentences[:4])[:1000]

    return source[:1000]


def enrich_product_copy(product, analysis: dict, profile) -> list[str]:
    """
    Apply improved name + formatted description from vision analysis.
    Returns list of updated model field names.
    """
    update_fields: list[str] = []
    analysis = analysis or {}

    if should_improve_product_name(product.name, analysis):
        new_name = improve_product_name(product.name, analysis)
        if new_name and new_name != product.name:
            product.name = new_name[:200]
            update_fields.append("name")
            from apps.products.commerce_links import ensure_commerce_slug

            product.commerce_slug = ""
            product.commerce_slug = ensure_commerce_slug(product, save=False, force=True)
            update_fields.append("commerce_slug")

    new_desc = format_product_description(product.description or "", analysis)
    should_update_desc = (
        not (product.description or "").strip()
        or (analysis.get("description_sentences") and "\n\n" not in (product.description or ""))
        or len((product.description or "").strip()) < 40
    )
    if should_update_desc and new_desc and new_desc != (product.description or "").strip():
        product.description = new_desc[:1000]
        update_fields.append("description")

    if update_fields:
        product.save(update_fields=[*update_fields, "updated_at"])

    from apps.products.commerce_seo import ensure_commerce_seo_copy

    if ensure_commerce_seo_copy(product, profile, analysis):
        if "description" not in update_fields:
            update_fields.append("description")

    return update_fields


def build_product_carousel_plan(
    product,
    analysis: dict | None,
    key_features: list[str] | None,
    *,
    max_photo_slides: int = 5,
) -> list[dict]:
    """
    Story-driven carousel plan: hook → story → benefits → price reveal.
    Each entry maps to one rendered slide before the closing CTA.
    """
    analysis = analysis or {}
    features = list(key_features or analysis.get("key_features") or [])

    sentences = analysis.get("description_sentences") or []
    if not sentences and analysis.get("description"):
        sentences = split_description_sentences(analysis["description"])

    angle = (analysis.get("campaign_angle") or "").strip()
    hook = angle[:90] if angle else ""
    if not hook and sentences:
        hook = sentences[0][:90]

    name = product.name
    price = product.display_price or ""
    num_images = len(product.carousel_image_urls or product.all_image_urls or [])
    if num_images == 0:
        num_images = 1

    plan: list[dict] = []

    plan.append({
        "layout": "hero_hook",
        "headline": name,
        "subtext": hook or "Swipe to see why customers love it →",
        "badge": "Just dropped" if price else "",
        "image_index": 0,
    })

    if sentences:
        plan.append({
            "layout": "story_card",
            "headline": "The details",
            "body": sentences[0],
            "image_index": min(1, num_images - 1),
        })

    benefit_layouts = ("benefit_bottom", "benefit_side", "benefit_badge")
    for i, feat in enumerate(features[:3]):
        headline = feat if feat.startswith(("✓", "✅", "•")) else f"✓ {feat}"
        plan.append({
            "layout": benefit_layouts[i % len(benefit_layouts)],
            "headline": headline[:120],
            "body": sentences[min(i + 1, len(sentences) - 1)] if len(sentences) > 1 else "",
            "image_index": min(i + 1, num_images - 1),
        })

    if price:
        price_body = sentences[-1] if sentences else "Tap the link in bio to order today."
        plan.append({
            "layout": "price_reveal",
            "headline": price,
            "body": price_body[:160],
            "subtext": name,
            "image_index": min(2, num_images - 1),
        })

    return plan[:max_photo_slides]
