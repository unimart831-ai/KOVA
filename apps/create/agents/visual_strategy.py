"""
Visual Template System — the Create Agent picks the best visual type per post.

This module sits between the Create Agent's output and the visual generation
pipeline. It analyzes the content and decides:

  1. Should this post use an AI photo, a branded graphic, or a carousel?
  2. Which specific template/graphic type fits best?
  3. What content should be extracted for the visual?

The Create Agent's LLM output now includes a `visual_strategy` field that
this module interprets to generate the right visual.

Visual Strategy Types:
  - "ai_photo"      → Standard FLUX.1 AI image generation (existing pipeline)
  - "quote_card"    → Branded quote card graphic
  - "tip_graphic"   → Numbered tips/list graphic
  - "stat_highlight" → Big number + context graphic
  - "cta_banner"    → Promotional/action graphic
  - "carousel"      → Multi-slide carousel (2-10 slides)
  - "none"          → Text-only post (for platforms that support it)
"""

import logging

from apps.create.agents.carousel import generate_carousel
from apps.create.agents.graphics import GraphicType, generate_branded_graphic
from apps.create.content.image_gen import generate_post_image

logger = logging.getLogger(__name__)


# ─── VISUAL STRATEGY MAPPING ─────────────────────────────────────────────────

STRATEGY_TO_GRAPHIC = {
    "quote_card": GraphicType.QUOTE_CARD,
    "tip_graphic": GraphicType.TIP_GRAPHIC,
    "stat_highlight": GraphicType.STAT_HIGHLIGHT,
    "cta_banner": GraphicType.CTA_BANNER,
}

# Normalize common LLM aliases to canonical strategy names
STRATEGY_ALIASES = {
    "photo": "ai_photo",
    "image": "ai_photo",
    "picture": "ai_photo",
    "quote": "quote_card",
    "tips": "tip_graphic",
    "stat": "stat_highlight",
    "stats": "stat_highlight",
    "cta": "cta_banner",
    "banner": "cta_banner",
}


def apply_visual_strategy(post, visual_data: dict) -> str | None:
    """
    Apply the visual strategy chosen by the Create Agent.

    Args:
        post: Post instance (already created, needs visual attached)
        visual_data: Dict from LLM output with keys:
            - strategy (str): "ai_photo", "quote_card", "carousel", etc.
            - image_prompt (str): For ai_photo strategy
            - text (str): Main text for graphics
            - attribution (str): For quote cards
            - tips (list[str]): For tip graphics
            - stat_number (str): For stat highlights
            - stat_label (str): For stat highlights
            - headline (str): For CTA banners / tip titles
            - subtext (str): For CTA banners
            - cta_text (str): For CTA banners / carousel closing
            - slides (list[dict]): For carousels

    Returns:
        URL of generated media (or first slide URL for carousels), or None.
    """
    strategy = visual_data.get("strategy", "ai_photo")
    strategy = STRATEGY_ALIASES.get(strategy, strategy)  # normalize LLM aliases

    if strategy == "none":
        logger.debug("Visual strategy is 'none' for post %s — skipping", post.id)
        return None

    if strategy == "ai_photo":
        image_prompt = visual_data.get("image_prompt", "")
        if image_prompt:
            return generate_post_image(post, image_prompt)
        return None

    if strategy == "carousel":
        slides = visual_data.get("slides", [])
        if not slides:
            logger.warning("Carousel strategy but no slides for post %s", post.id)
            return None
        urls = generate_carousel(
            post,
            slides,
            title=visual_data.get("headline", ""),
            subtitle=visual_data.get("subtext", ""),
            closing_cta=visual_data.get("cta_text", "Follow for more"),
        )
        return urls[0] if urls else None

    graphic_type = STRATEGY_TO_GRAPHIC.get(strategy)
    if graphic_type:
        return generate_branded_graphic(
            post,
            graphic_type,
            text=visual_data.get("text", ""),
            attribution=visual_data.get("attribution", ""),
            tips=visual_data.get("tips"),
            stat_number=visual_data.get("stat_number", ""),
            stat_label=visual_data.get("stat_label", ""),
            context=visual_data.get("context", ""),
            headline=visual_data.get("headline", ""),
            subtext=visual_data.get("subtext", ""),
            cta_text=visual_data.get("cta_text", ""),
        )

    # Unknown strategy — fall back to ai_photo
    logger.warning("Unknown visual strategy '%s' for post %s, falling back to ai_photo", strategy, post.id)
    image_prompt = visual_data.get("image_prompt", "")
    if image_prompt:
        return generate_post_image(post, image_prompt)
    return None


def infer_visual_strategy(content_text: str, platform: str) -> str:
    """
    Simple heuristic to infer the best visual strategy when the LLM
    doesn't explicitly provide one (backward compatibility).

    This is used as a fallback when the old LLM output format (just
    image_prompt) is used instead of the new visual_strategy format.
    """
    text_lower = content_text.lower()

    # Detect listicle / tips pattern
    import re
    numbered_items = re.findall(r'(?:^|\n)\s*\d+[\.\)]\s', content_text)
    if len(numbered_items) >= 3:
        return "tip_graphic"

    # Detect stat / number-heavy content
    big_numbers = re.findall(r'\b\d{2,}[%+xX]\b|\b\d{1,3}(?:,\d{3})+\b', content_text)
    if big_numbers and len(content_text) < 200:
        return "stat_highlight"

    # Detect quote pattern
    if content_text.startswith('"') or content_text.startswith('\u201c'):
        return "quote_card"

    # Detect CTA / promotional
    cta_words = ["sign up", "join", "register", "download", "get started",
                 "shop now", "buy now", "limited time", "offer", "discount"]
    if any(w in text_lower for w in cta_words):
        return "cta_banner"

    # Carousel for long content on carousel-friendly platforms
    if platform in ("instagram", "linkedin", "threads") and len(content_text) > 800:
        return "carousel"

    # Default: AI photo
    return "ai_photo"
