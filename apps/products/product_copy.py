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

# Rotating markers for social captions and carousel slides — avoids repetitive ✅ lines.
FEATURE_BULLET_EMOJIS: tuple[str, ...] = (
    "✨",
    "⚡",
    "🔥",
    "💎",
    "🎯",
    "⭐",
    "💡",
    "📦",
    "🛡️",
    "👌",
    "🚀",
    "✅",
)

_LEADING_BULLET_RE = re.compile(
    r"^[\s✅✓✔☑️⭐🌟💫🔥⚡✨💎🎯💡📦🛡️👌🚀•\-–—→]+",
)

# Vision models sometimes copy schema labels like "Sentence 1:" into output.
_SENTENCE_LABEL_RE = re.compile(
    r"^sentence\s+\d+\s*(\(\s*optional\s*\))?\s*[:\-\.]?\s*",
    re.I,
)


def strip_feature_bullet(text: str) -> str:
    """Remove an existing leading emoji/bullet so we can re-style consistently."""
    cleaned = (text or "").strip()
    while cleaned:
        nxt = _LEADING_BULLET_RE.sub("", cleaned).strip()
        if nxt == cleaned:
            break
        cleaned = nxt
    return cleaned


def _bullet_offset(seed: str, platform: str = "") -> int:
    key = f"{seed}:{platform}".encode()
    return sum(key) % len(FEATURE_BULLET_EMOJIS)


def format_feature_bullets(
    features: list[str],
    *,
    seed: str = "",
    platform: str = "",
    limit: int = 3,
) -> str:
    """Format key features with varied emoji bullets for captions."""
    if not features:
        return ""
    offset = _bullet_offset(seed or "kova", platform)
    lines: list[str] = []
    for i, raw in enumerate(features[:limit]):
        feat = strip_feature_bullet(str(raw))
        if not feat:
            continue
        emoji = FEATURE_BULLET_EMOJIS[(offset + i) % len(FEATURE_BULLET_EMOJIS)]
        lines.append(f"{emoji} {feat}")
    return "\n".join(lines)


def feature_slide_headline(feature: str, index: int, *, seed: str = "") -> str:
    """Single carousel slide headline with a rotated marker."""
    feat = strip_feature_bullet(feature)
    if not feat:
        return ""
    offset = _bullet_offset(seed or "kova")
    emoji = FEATURE_BULLET_EMOJIS[(offset + index + 2) % len(FEATURE_BULLET_EMOJIS)]
    return f"{emoji} {feat}"


def clean_description_sentence(text: str) -> str:
    """Strip schema placeholders like 'Sentence 1:' from customer-facing copy."""
    cleaned = (text or "").strip()
    cleaned = _SENTENCE_LABEL_RE.sub("", cleaned)
    return cleaned.strip()


def normalize_description_sentences(parts: list[str]) -> list[str]:
    return [s for s in (clean_description_sentence(p) for p in parts) if s]


MIN_DESCRIPTION_SENTENCES = 3
MAX_DESCRIPTION_SENTENCES = 4


def split_description_sentences(text: str) -> list[str]:
    """Split prose into sentence chunks."""
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def description_sentence_count(text: str) -> int:
    """Count customer-facing description sentences (paragraphs or split prose)."""
    if not (text or "").strip():
        return 0
    if "\n\n" in text:
        return len(normalize_description_sentences(text.split("\n\n")))
    return len(normalize_description_sentences(split_description_sentences(text)))


def expand_to_description_sentences(
    sentences: list[str],
    *,
    product_name: str = "",
    analysis: dict | None = None,
    brand: str = "",
    price: str = "",
) -> list[str]:
    """Ensure at least 3 and at most 4 plain sentences for shop copy."""
    analysis = analysis or {}
    out: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        s = clean_description_sentence(candidate)
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s if s.endswith((".", "!", "?")) else f"{s}.")

    for s in sentences:
        _add(s)
        if len(out) >= MAX_DESCRIPTION_SENTENCES:
            return out[:MAX_DESCRIPTION_SENTENCES]

    for s in split_description_sentences(analysis.get("description") or ""):
        _add(s)
        if len(out) >= MAX_DESCRIPTION_SENTENCES:
            return out[:MAX_DESCRIPTION_SENTENCES]

    name = (product_name or "This product").strip()
    for feat in analysis.get("key_features") or []:
        if len(out) >= MAX_DESCRIPTION_SENTENCES:
            break
        feat_text = strip_feature_bullet(str(feat))
        if feat_text:
            _add(f"Includes {feat_text.rstrip('.')}")

    audience = (analysis.get("target_audience") or "").strip().rstrip(".")
    if len(out) < MIN_DESCRIPTION_SENTENCES and audience:
        _add(f"Ideal for {audience}")

    angle = (analysis.get("campaign_angle") or "").strip().rstrip(".")
    if len(out) < MIN_DESCRIPTION_SENTENCES and angle:
        _add(angle)

    if len(out) < MIN_DESCRIPTION_SENTENCES and brand:
        _add(f"Available from {brand}")

    if len(out) < MIN_DESCRIPTION_SENTENCES and price:
        _add(f"Priced at {price}")

    if len(out) < MIN_DESCRIPTION_SENTENCES:
        _add(f"{name} is a quality pick for everyday use")

    return out[:MAX_DESCRIPTION_SENTENCES]


def format_product_description(
    text: str,
    analysis: dict | None = None,
    *,
    product_name: str = "",
    brand: str = "",
    price: str = "",
) -> str:
    """
    Normalize to 3–4 sentences separated by blank lines (not one dense paragraph).
    """
    analysis = analysis or {}
    sentences: list[str] = []

    if isinstance(analysis.get("description_sentences"), list):
        sentences = normalize_description_sentences(
            [str(s) for s in analysis["description_sentences"] if str(s).strip()]
        )

    source = (text or analysis.get("description") or "").strip()
    if source:
        if "\n\n" in source:
            for s in normalize_description_sentences(source.split("\n\n")):
                if s not in sentences:
                    sentences.append(s)
        else:
            for s in normalize_description_sentences(split_description_sentences(source)):
                if s not in sentences:
                    sentences.append(s)

    sentences = expand_to_description_sentences(
        sentences,
        product_name=product_name,
        analysis=analysis,
        brand=brand,
        price=price,
    )
    if len(sentences) >= MIN_DESCRIPTION_SENTENCES:
        return "\n\n".join(sentences[:MAX_DESCRIPTION_SENTENCES])[:1000]

    if sentences:
        return "\n\n".join(sentences)[:1000]

    single = clean_description_sentence(source)
    return single[:1000]


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

    from apps.products.commerce_seo import brand_name

    brand = brand_name(profile, product.user)
    new_desc = format_product_description(
        product.description or "",
        analysis,
        product_name=product.name,
        brand=brand,
        price=product.display_price or "",
    )
    current_count = description_sentence_count(product.description or "")
    new_count = description_sentence_count(new_desc)
    should_update_desc = (
        not (product.description or "").strip()
        or current_count < MIN_DESCRIPTION_SENTENCES
        or (new_count >= MIN_DESCRIPTION_SENTENCES and new_count > current_count)
        or (analysis.get("description_sentences") and new_desc != (product.description or "").strip())
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

    if num_images > 2:
        plan.append({
            "layout": "minimal_caption",
            "headline": name,
            "image_index": min(2, num_images - 1),
        })

    benefit_layouts = ("clean_split", "side_panel", "clean_split")
    for i, feat in enumerate(features[:3]):
        headline = feature_slide_headline(feat, i, seed=str(getattr(product, "pk", "")))
        if not headline:
            continue
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
