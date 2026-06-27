"""
Social post copy — human-native layout, spacing, and commerce captions.

Programmatic posts (Snap, quick post, carousels) and LLM output both pass
through polish_post_caption so published text reads like a person wrote it.
"""

from __future__ import annotations

import re
from typing import Any

from apps.products.product_copy import (
    clean_description_sentence,
    split_description_sentences,
    strip_feature_bullet,
)

# Platforms that prefer short reel captions below the video.
_REEL_SHORT_PLATFORMS = frozenset({"instagram", "tiktok", "facebook"})

_PLATFORM_LIMITS: dict[str, int] = {
    "instagram": 2200,
    "facebook": 5000,
    "linkedin": 3000,
    "tiktok": 4000,
    "twitter": 280,
    "threads": 500,
    "bluesky": 300,
    "pinterest": 500,
    "whatsapp": 4096,
    "youtube": 5000,
}

_EMOJI_BULLET_LINE = re.compile(
    r"^[\s✅✓✔☑️⭐🌟💫🔥⚡✨💎🎯💡📦🛡️👌🚀💰🛒•\-–—→]+\s*\S",
)

_CORPORATE_FILLER = (
    "discover the",
    "elevate your",
    "unlock the power",
    "game-changer",
    "look no further",
    "perfect for anyone",
    "don't miss out",
)


def normalize_caption_spacing(text: str) -> str:
    """Preserve paragraph breaks; collapse runaway blank lines and inline spaces."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in text.split("\n"):
        collapsed = re.sub(r"[ \t]+", " ", line.strip())
        lines.append(collapsed)

    out: list[str] = []
    blank_run = 0
    for line in lines:
        if not line:
            blank_run += 1
            if blank_run <= 1:
                out.append("")
            continue
        blank_run = 0
        out.append(line)

    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def _space_emoji_bullet_blocks(text: str) -> str:
    """Add breathing room around stacked emoji-bullet lines."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line and _EMOJI_BULLET_LINE.match(line):
            block: list[str] = []
            while i < len(lines) and lines[i] and _EMOJI_BULLET_LINE.match(lines[i]):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                if result and result[-1] != "":
                    result.append("")
                result.extend(block)
                result.append("")
            else:
                result.extend(block)
            continue
        result.append(line)
        i += 1
    return normalize_caption_spacing("\n".join(result))


def _trim_to_limit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1]
    cut = trimmed.rfind("\n\n")
    if cut > limit * 0.55:
        return trimmed[:cut].rstrip() + "…"
    cut = trimmed.rfind(". ")
    if cut > limit * 0.55:
        return trimmed[: cut + 1].rstrip()
    cut = trimmed.rfind(" ")
    if cut > limit * 0.7:
        return trimmed[:cut].rstrip() + "…"
    return trimmed.rstrip() + "…"


def polish_post_caption(
    text: str,
    platform: str = "",
    *,
    post_format: str = "text",
) -> str:
    """
    Final pass for any post body: spacing, bullet blocks, platform length.
    """
    if not text:
        return ""
    cleaned = normalize_caption_spacing(text.strip())
    cleaned = _space_emoji_bullet_blocks(cleaned)

    plat = (platform or "").lower().strip()
    if post_format == "reel" and plat in _REEL_SHORT_PLATFORMS:
        limit = 280 if plat == "instagram" else 400
    else:
        limit = _PLATFORM_LIMITS.get(plat, 2200)

    return _trim_to_limit(cleaned, limit)


def _hook_line(product, analysis: dict | None, seed: str) -> str:
    analysis = analysis or {}
    name = (product.name or "This").strip()
    angle = (analysis.get("campaign_angle") or "").strip()

    if angle and 12 <= len(angle) <= 100 and angle.lower() != name.lower():
        return clean_description_sentence(angle)

    short = name.split("—")[0].split("-")[0].strip()
    templates = (
        f"Just dropped — {short} ✨",
        f"If you've had your eye on {short}, today's the day.",
        f"Okay but {short} is actually worth the hype 👀",
        f"New in: {short}. Swipe for the details →",
        f"Restocked and ready — {short}.",
    )
    idx = sum(ord(c) for c in (seed or str(getattr(product, "pk", "")))) % len(templates)
    return templates[idx]


def _body_paragraphs(product, analysis: dict | None) -> list[str]:
    analysis = analysis or {}
    paragraphs: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        s = clean_description_sentence(candidate)
        if not s:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        if not s.endswith((".", "!", "?")):
            s = f"{s}."
        paragraphs.append(s)

    for block in (analysis.get("description_sentences") or [])[:3]:
        _add(str(block))
    if paragraphs:
        return paragraphs[:2]

    desc = (product.description or "").strip()
    if not desc:
        return paragraphs

    if "\n\n" in desc:
        for part in desc.split("\n\n")[:3]:
            _add(part.strip())
    else:
        for part in split_description_sentences(desc)[:3]:
            _add(part)

    return paragraphs[:2]


def _features_as_prose(features: list[str], *, seed: str = "") -> str:
    cleaned = [strip_feature_bullet(str(f)) for f in features if strip_feature_bullet(str(f))]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        line = cleaned[0]
        return line if line.endswith((".", "!", "?")) else f"{line}."
    if len(cleaned) == 2:
        a, b = cleaned[0].rstrip("."), cleaned[1].rstrip(".")
        return f"{a}, and {b[0].lower() + b[1:] if len(b) > 1 else b}."
    a, b, c = [x.rstrip(".") for x in cleaned[:3]]
    return f"{a}. {b}. Plus {c[0].lower() + c[1:] if len(c) > 1 else c}."


def _natural_price_line(price_label: str, platform: str) -> str:
    if not price_label:
        return ""
    plat = (platform or "").lower()
    if plat == "linkedin":
        return f"Priced at {price_label}."
    return f"Available for {price_label}."


def _platform_cta(platform: str, offering_type: str = "product") -> str:
    plat = (platform or "").lower()
    if plat == "instagram":
        return "Tap the link in bio to order 👆"
    if plat == "facebook":
        return "Message us or comment ORDER — we'll send you the link."
    if plat == "linkedin":
        if offering_type == "service":
            return "Book a quick call — link in the first comment ↓"
        return "Full details in the first comment ↓"
    if plat == "tiktok":
        return "Link in bio if you want one 🔗"
    if plat == "twitter":
        return "DM us to order."
    if plat == "whatsapp":
        return "Reply to order — we're online."
    return "Order today — link in bio."


def _commerce_hashtags(product, platform: str) -> str:
    plat = (platform or "").lower()
    if plat not in ("instagram", "tiktok"):
        return ""
    tags: list[str] = []
    name_words = [
        w.lower()
        for w in re.split(r"\W+", product.name or "")
        if len(w) > 3 and w.lower() not in {"with", "from", "this", "that"}
    ]
    for word in name_words[:2]:
        tags.append(f"#{word}")

    category = ""
    if getattr(product, "category_id", None) and product.category:
        category = product.category.name
    if category:
        tag = re.sub(r"\W+", "", category.lower())
        if tag and f"#{tag}" not in tags:
            tags.append(f"#{tag}")

    defaults = {
        "instagram": ["#smallbusiness", "#shoplocal", "#newarrival"],
        "tiktok": ["#fyp", "#smallbusiness"],
    }
    for tag in defaults.get(plat, []):
        if len(tags) >= 5:
            break
        if tag not in tags:
            tags.append(tag)

    return " ".join(tags[:5])


def build_commerce_caption(
    product,
    *,
    platform: str,
    key_features: list[str] | None = None,
    analysis: dict | None = None,
    post_format: str = "image",
    include_price: bool = True,
    include_hashtags: bool = True,
) -> str:
    """
    Human-native caption for Snap / carousel / reel / quick-post flows.
    """
    analysis = analysis or {}
    features = list(key_features or analysis.get("key_features") or [])
    seed = str(getattr(product, "pk", ""))
    plat = (platform or "").lower()
    offering = getattr(product, "offering_type", "product") or "product"
    price_label = (product.display_price or "").strip() if include_price else ""

    sections: list[str] = []

    if post_format == "reel":
        hook = _hook_line(product, analysis, seed)
        if hook:
            sections.append(hook)
        if price_label and plat != "tiktok":
            sections.append(_natural_price_line(price_label, plat))
        cta = _platform_cta(plat, offering)
        if cta:
            sections.append(cta)
        if include_hashtags and plat == "tiktok":
            tags = _commerce_hashtags(product, plat)
            if tags:
                sections.append(tags)
        text = "\n\n".join(sections)
        return polish_post_caption(text, plat, post_format="reel")

    hook = _hook_line(product, analysis, seed)
    if hook:
        sections.append(hook)

    body = _body_paragraphs(product, analysis)
    feature_prose = _features_as_prose(features, seed=seed)
    body_blob = " ".join(body).lower()
    if feature_prose and feature_prose.lower() not in body_blob:
        body.append(feature_prose)
    if body:
        sections.append("\n\n".join(body))

    if price_label:
        sections.append(_natural_price_line(price_label, plat))

    cta = _platform_cta(plat, offering)
    if cta:
        sections.append(cta)

    if include_hashtags:
        tags = _commerce_hashtags(product, plat)
        if tags:
            sections.append(tags)

    text = "\n\n".join(s for s in sections if s)
    return polish_post_caption(text, plat, post_format=post_format)


def build_quick_post_caption(product, *, platform: str) -> str:
    """Short photo post — no raw URLs on link-sensitive platforms."""
    plat = (platform or "").lower()
    link_sensitive = plat in ("instagram", "facebook", "linkedin")

    sections = [_hook_line(product, {}, str(product.pk))]
    body = _body_paragraphs(product, None)
    if body:
        sections.append(body[0])
    if product.display_price:
        sections.append(_natural_price_line(product.display_price, plat))

    if link_sensitive:
        sections.append(_platform_cta(plat, getattr(product, "offering_type", "product")))
    else:
        from apps.products.product_cta import resolve_product_cta_url

        url = resolve_product_cta_url(product)
        if url:
            sections.append(f"Shop here: {url}")

    text = "\n\n".join(sections)
    return polish_post_caption(text, plat, post_format="image")


HUMAN_COPY_RULES = """
## HUMAN VOICE & LAYOUT (NON-NEGOTIABLE)

Write like a real small-business owner posting from their phone — warm, specific,
and easy to scan. NOT like an AI brochure, spec sheet, or marketing template.

STRUCTURE — use a blank line between each block:
1. Hook — one line that stops the scroll (question, bold claim, or direct "you")
2. Body — 2–4 short paragraphs (1–3 sentences each). Flowing prose, not lists.
3. CTA — one clear line (platform-native: "link in bio", "first comment ↓", etc.)
4. Hashtags — Instagram/TikTok only, after a blank line, 3–5 niche tags max

NEVER:
- Stack emoji bullet lists (✨ line / ⚡ line / 🔥 line) — weave benefits into sentences
- Open with only the product name and nothing else
- Publish one wall of text with zero line breaks
- Use filler phrases: "Discover", "Elevate your", "Unlock the power", "game-changer"
- Repeat the product name in every paragraph
- Use markdown (**bold**, *italic*) — platforms show asterisks literally

Read each caption aloud before returning it. If it sounds robotic, rewrite it.
"""
