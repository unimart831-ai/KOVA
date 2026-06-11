"""
Reel director — recipe rotation, slide roles, motion grammar, and hook copy.

Turns curated product images into a ReelComposePlan for FFmpeg composition.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

# Rotating commerce reel recipes (user: rotate + 5 slides + price on last frame only).
REEL_RECIPES: tuple[str, ...] = (
    "story_arc",
    "flash_drop",
    "lifestyle_story",
    "product_reveal",
)

RECIPE_TEMPLATES: dict[str, str] = {
    "story_arc": "story_arc",
    "flash_drop": "flash_commerce",
    "lifestyle_story": "story_arc",
    "product_reveal": "story_arc",
}

RECIPE_MOODS: dict[str, str] = {
    "story_arc": "upbeat",
    "flash_drop": "urgent",
    "lifestyle_story": "upbeat",
    "product_reveal": "upbeat",
}

# Category nudges rotation index (Phase C) — still rotates, bias by +0/+1.
CATEGORY_RECIPE_BIAS: dict[str, int] = {
    "food": 2,       # lifestyle_story
    "beauty": 2,
    "apparel": 0,    # story_arc
    "electronics": 1,  # flash_drop
    "jewelry": 0,
    "home": 2,
    "general": 0,
}

SLIDE_ROLE_HOOK = "hook"
SLIDE_ROLE_HERO = "hero"
SLIDE_ROLE_STAGING = "staging"
SLIDE_ROLE_ANGLE = "angle"
SLIDE_ROLE_DESIRE = "desire"
SLIDE_ROLE_CTA = "cta"

# Ken Burns variant index per role (maps to video_compose._ken_burns_filter).
ROLE_KEN_BURNS: dict[str, int] = {
    SLIDE_ROLE_HOOK: 0,
    SLIDE_ROLE_HERO: 1,
    SLIDE_ROLE_STAGING: 2,
    SLIDE_ROLE_ANGLE: 6,
    SLIDE_ROLE_DESIRE: 4,
    SLIDE_ROLE_CTA: 9,
}

# xfade transition into slide i (from slide i-1); length = num_slides - 1.
ROLE_TRANSITION_IN: dict[str, str] = {
    SLIDE_ROLE_HOOK: "fade",
    SLIDE_ROLE_HERO: "slideup",
    SLIDE_ROLE_STAGING: "dissolve",
    SLIDE_ROLE_ANGLE: "slideright",
    SLIDE_ROLE_DESIRE: "slideleft",
    SLIDE_ROLE_CTA: "zoomin",
}

REEL_MAX_SLIDES_DEFAULT = 5


@dataclass(frozen=True)
class ReelComposePlan:
    """Creative blueprint passed to video_compose.compose_motion_reel."""

    recipe_id: str
    template: str
    image_urls: list[str]
    slide_roles: list[str]
    hook_texts: list[str]
    music_mood: str
    transitions: list[str] = field(default_factory=list)
    ken_burns_variants: list[int] = field(default_factory=list)
    cta_audio_boost: bool = False
    transition_sec: float | None = None

    def to_metadata(self) -> dict[str, Any]:
        return {
            "reel_recipe_id": self.recipe_id,
            "reel_template": self.template,
            "reel_slide_roles": self.slide_roles,
            "music_mood": self.music_mood,
            "reel_cta_audio_boost": self.cta_audio_boost,
        }


def recipe_preference_for_seed(
    *,
    seed: str,
    category: str = "general",
    winning_recipe: str | None = None,
) -> str:
    """
    Phase E — prefer analyst-winning recipe when set; else rotate by seed.

    Store `winning_recipe` on post.visual_metadata or profile when learn loop ships.
    """
    if winning_recipe and winning_recipe in REEL_RECIPES:
        return winning_recipe
    return pick_recipe_id(seed=seed, category=category)


def pick_recipe_id(
    *,
    seed: str,
    category: str = "general",
    preferred: str | None = None,
) -> str:
    """Rotate recipes per product/post; optional category bias."""
    if preferred and preferred in REEL_RECIPES:
        return preferred

    recipes = list(REEL_RECIPES)
    digest = hashlib.sha256((seed or "default").encode()).hexdigest()
    base = int(digest[:8], 16) % len(recipes)
    bias = CATEGORY_RECIPE_BIAS.get((category or "general").lower(), 0)
    return recipes[(base + bias) % len(recipes)]


def _url_role(url: str) -> str:
    u = url.lower()
    if "channel_story" in u:
        return SLIDE_ROLE_HOOK
    if "edit_ai_staging" in u:
        return SLIDE_ROLE_STAGING
    if "edit_ai_angle" in u:
        return SLIDE_ROLE_ANGLE
    if "promo_frame" in u:
        return SLIDE_ROLE_CTA
    if any(
        m in u
        for m in (
            "studio_white",
            "studio_brand",
            "service_hero",
            "digital_desk_hero",
        )
    ):
        return SLIDE_ROLE_HERO
    if any(
        m in u
        for m in (
            "ai_scene_",
            "ai_creative_",
            "ai_lifestyle",
            "ai_contextual",
        )
    ):
        return SLIDE_ROLE_DESIRE
    return SLIDE_ROLE_DESIRE


def _order_urls_for_recipe(urls: list[str], recipe_id: str, *, max_slides: int) -> list[str]:
    """Pick and order up to max_slides URLs for a recipe arc."""
    from apps.products.reel_curation import curate_reel_image_urls

    pool = curate_reel_image_urls(urls, max_slides=max_slides * 2)
    if not pool:
        return []

    by_role: dict[str, list[str]] = {r: [] for r in ROLE_KEN_BURNS}
    for url in pool:
        role = _url_role(url)
        if url not in by_role[role]:
            by_role[role].append(url)

    def pop(role: str) -> str | None:
        if by_role[role]:
            return by_role[role].pop(0)
        return None

    ordered: list[str] = []
    seen: set[str] = set()

    def add(url: str | None) -> None:
        if url and url not in seen and len(ordered) < max_slides:
            ordered.append(url)
            seen.add(url)

    if recipe_id == "lifestyle_story":
        for role in (
            SLIDE_ROLE_HOOK,
            SLIDE_ROLE_STAGING,
            SLIDE_ROLE_ANGLE,
            SLIDE_ROLE_DESIRE,
            SLIDE_ROLE_CTA,
        ):
            add(pop(role) or pop(SLIDE_ROLE_HERO))
        # Fill gaps
        for url in pool:
            add(url)
        return ordered[:max_slides]

    if recipe_id == "flash_drop":
        for role in (
            SLIDE_ROLE_HOOK,
            SLIDE_ROLE_HERO,
            SLIDE_ROLE_DESIRE,
            SLIDE_ROLE_DESIRE,
            SLIDE_ROLE_CTA,
        ):
            add(pop(role) or pop(SLIDE_ROLE_STAGING) or pop(SLIDE_ROLE_ANGLE))
        for url in pool:
            add(url)
        return ordered[:max_slides]

    if recipe_id == "product_reveal":
        for role in (
            SLIDE_ROLE_HOOK,
            SLIDE_ROLE_HERO,
            SLIDE_ROLE_DESIRE,
            SLIDE_ROLE_STAGING,
            SLIDE_ROLE_CTA,
        ):
            add(pop(role) or pop(SLIDE_ROLE_ANGLE))
        for url in pool:
            add(url)
        return ordered[:max_slides]

    # story_arc (default cinematic)
    for role in (
        SLIDE_ROLE_HOOK,
        SLIDE_ROLE_HERO,
        SLIDE_ROLE_STAGING,
        SLIDE_ROLE_DESIRE,
        SLIDE_ROLE_CTA,
    ):
        add(pop(role) or pop(SLIDE_ROLE_ANGLE))
    for url in pool:
        add(url)
    return ordered[:max_slides]


def build_hook_texts(
    *,
    slide_count: int,
    slide_roles: list[str],
    product_name: str = "",
    price_label: str = "",
    hook_override: str = "",
    brand_name: str = "",
    cta_label: str = "Order on WhatsApp",
) -> list[str]:
    """Product name on hook; brand on hero; price + CTA on last frame."""
    texts = [""] * slide_count
    if slide_count == 0:
        return texts

    hook = (hook_override or product_name or "").strip()
    price = price_label.strip()[:40] if price_label else ""
    brand = (brand_name or "").strip()[:40]
    cta = (cta_label or "").strip()[:40]

    if slide_count == 1:
        if price and cta:
            texts[0] = f"{price}\n{cta}"
        elif price:
            texts[0] = price
        elif cta:
            texts[0] = cta
        elif hook:
            texts[0] = hook[:60]
        return texts

    if hook:
        texts[0] = hook[:60]

    if brand and slide_count >= 3:
        texts[1] = brand

    if price and cta:
        texts[-1] = f"{price}\n{cta}"
    elif price:
        texts[-1] = price
    elif cta and slide_count >= 2:
        texts[-1] = cta

    return texts


def build_transitions(slide_roles: list[str]) -> list[str]:
    """One transition per gap; first slide uses fade into frame 1 from black."""
    if len(slide_roles) <= 1:
        return []
    out: list[str] = []
    for i in range(1, len(slide_roles)):
        role = slide_roles[i]
        out.append(ROLE_TRANSITION_IN.get(role, "dissolve"))
    return out


def build_ken_burns_variants(slide_roles: list[str]) -> list[int]:
    variants = []
    for idx, role in enumerate(slide_roles):
        base = ROLE_KEN_BURNS.get(role, idx % 10)
        # Slight index offset so consecutive desire slides differ
        if role == SLIDE_ROLE_DESIRE:
            base = (4 + idx) % 10
        variants.append(base)
    return variants


def build_reel_plan(
    image_urls: list[str],
    *,
    seed: str,
    category: str = "general",
    product_name: str = "",
    price_label: str = "",
    hook_override: str = "",
    brand_name: str = "",
    cta_label: str = "Order on WhatsApp",
    recipe_id: str | None = None,
    max_slides: int | None = None,
) -> ReelComposePlan | None:
    """
    Build a full compose plan from raw studio polish URLs.
    """
    max_slides = max_slides or int(
        getattr(settings, "REEL_MAX_SLIDES", REEL_MAX_SLIDES_DEFAULT),
    )
    clean = [u for u in image_urls if u]
    if not clean:
        return None

    recipe = recipe_preference_for_seed(
        seed=seed,
        category=category,
        winning_recipe=recipe_id,
    )
    ordered = _order_urls_for_recipe(clean, recipe, max_slides=max_slides)
    if not ordered:
        from apps.products.reel_curation import curate_reel_image_urls

        ordered = curate_reel_image_urls(clean, max_slides=max_slides)
    if not ordered:
        return None

    roles = [_url_role(u) for u in ordered]
    # Last slide with promo or hero treated as CTA for motion
    if roles and roles[-1] not in (SLIDE_ROLE_CTA,):
        if "promo_frame" in (ordered[-1] or "").lower():
            roles[-1] = SLIDE_ROLE_CTA
        elif price_label:
            roles[-1] = SLIDE_ROLE_CTA

    template = RECIPE_TEMPLATES.get(recipe, "story_arc")
    mood = RECIPE_MOODS.get(recipe, "upbeat")
    hooks = build_hook_texts(
        slide_count=len(ordered),
        slide_roles=roles,
        product_name=product_name,
        price_label=price_label,
        hook_override=hook_override,
        brand_name=brand_name,
        cta_label=cta_label,
    )
    transitions = build_transitions(roles)
    ken = build_ken_burns_variants(roles)

    transition_sec = None
    if recipe == "flash_drop":
        transition_sec = 0.35

    return ReelComposePlan(
        recipe_id=recipe,
        template=template,
        image_urls=ordered,
        slide_roles=roles,
        hook_texts=hooks,
        music_mood=mood,
        transitions=transitions,
        ken_burns_variants=ken,
        cta_audio_boost=(recipe == "flash_drop"),
        transition_sec=transition_sec,
    )
