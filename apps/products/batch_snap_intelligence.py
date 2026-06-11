"""
Market Day Mode intelligence for Batch Snap.

Parses stall voice briefs, builds batch-aware vision prompts, and generates
stall-wide launch copy (collection post + showcase reel + seller message).
"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("kova.batch_snap")

MARKET_DAY_COMMERCE_SOURCES = frozenset({"batch_snap"})


def is_market_day_mode(commerce_source: str | None = None) -> bool:
    """Batch Snap stall sessions use the Market Day Photoroom preset."""
    from django.conf import settings

    if not getattr(settings, "PHOTOROOM_MARKET_DAY_ENABLED", True):
        return False
    return (commerce_source or "") in MARKET_DAY_COMMERCE_SOURCES


def build_market_day_composition_prompt(stall_context: dict | None = None) -> str:
    """AI polish prompt for multi-product batch showcase heroes."""
    ctx = stall_context or {}
    stall_title = ctx.get("stall_title") or "market stall"
    market = (ctx.get("market_context") or "").strip()
    tagline = (ctx.get("stall_tagline") or "").strip()
    base = (
        f"Professional market-day collection photograph showing multiple products "
        f"arranged evenly on a clean branded studio surface with soft natural lighting "
        f"and cohesive shadows for '{stall_title}'"
    )
    if market:
        base += f". Setting: {market[:120]}"
    if tagline:
        base += f". Mood: {tagline[:80]}"
    return base


def _safe_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
        if d < 0:
            return None
        return d
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_stall_brief(
    *,
    transcript: str = "",
    stall_title: str = "",
    default_price=None,
    default_currency: str = "KES",
    offering_type: str = "product",
    item_count: int = 0,
    stall_notes: str = "",
) -> dict[str, Any]:
    """
    Turn seller voice/text brief into structured stall context for the batch agents.

    Falls back to rule-based parsing when LLM is unavailable.
    """
    base = {
        "stall_title": (stall_title or "").strip(),
        "stall_tagline": "",
        "market_context": "",
        "pricing_rules": {
            "default_price": float(_safe_decimal(default_price)) if _safe_decimal(default_price) else None,
            "default_currency": (default_currency or "KES").upper(),
            "bulk_price": None,
            "price_notes": "",
            "apply_default_to_blanks": True,
        },
        "category_hint": "",
        "size_variant_hint": "",
        "language_mix": "en",
        "swahili_phrases": [],
        "do_not_say": [],
        "campaign_tone": "energetic_market_day",
        "whatsapp_hook": "",
        "collection_angle": "fresh_stall_drop",
        "item_specific_hints": [],
        "brand_colors": {"primary": "", "secondary": ""},
        "surface_vibe": "",
        "scene_pack": "brand_studio",
    }

    combined = " ".join(
        part.strip()
        for part in (transcript, stall_notes)
        if part and part.strip()
    ).strip()
    if not combined and not stall_title:
        return base

    try:
        from apps.agents.llm import generate, get_model_for_task, parse_llm_json

        prompt = (
            "You are the Batch Snap strategist for Kova Agent — an AI marketing platform "
            "for African market sellers, boutiques, and pop-up stalls.\n\n"
            "A seller is launching MULTIPLE listings at once (market day / stall day). "
            "Parse their brief into structured JSON for downstream AI agents.\n\n"
            f"Offering type for this batch: {offering_type}\n"
            f"Number of photos/items in batch: {item_count}\n"
            f"Stall title (optional): {stall_title or 'not provided'}\n"
            f"Form default price: {default_price or 'not set'} {default_currency}\n\n"
            "Seller brief (voice transcript or typed notes):\n"
            f"\"\"\"{combined or stall_title}\"\"\"\n\n"
            "Return JSON ONLY:\n"
            "{\n"
            '  "stall_title": "Short catchy stall name if inferable, else empty string",\n'
            '  "stall_tagline": "One line for social (e.g. Fresh stock at Kawaida Market today)",\n'
            '  "market_context": "Where/when context: market name, pop-up, clearance, new shipment",\n'
            '  "pricing_rules": {\n'
            '    "default_price": number or null,\n'
            '    "default_currency": "KES|USD|... (3-letter code)",\n'
            '    "bulk_price": number or null if one price for many items,\n'
            '    "price_notes": "e.g. sizes M-L 800, XL 1000; negotiable on bulk",\n'
            '    "apply_default_to_blanks": true\n'
            "  },\n"
            '  "category_hint": "e.g. women\'s fashion, electronics, fresh produce",\n'
            '  "size_variant_hint": "e.g. mixed sizes on table, one price per row",\n'
            '  "language_mix": "en|sw|mixed — match how the seller spoke",\n'
            '  "swahili_phrases": ["natural Swahili/Sheng phrases to weave in if mixed", ...],\n'
            '  "do_not_say": ["words to avoid e.g. fake, replica"],\n'
            '  "campaign_tone": "energetic_market_day|premium_boutique|clearance_urgency|wholesale",\n'
            '  "whatsapp_hook": "Short WhatsApp-friendly line to share the shop link",\n'
            '  "collection_angle": "fresh_stall_drop|market_day_deals|new_arrivals|limited_table",\n'
            '  "item_specific_hints": [\n'
            '    {"hint": "optional per-item note if seller mentioned specific rows", "price": null}\n'
            "  ],\n"
            '  "brand_colors": {"primary": "#hex or empty", "secondary": "#hex or empty"},\n'
            '  "surface_vibe": "e.g. warm coral market table, cool boutique marble, rustic wood stall",\n'
            '  "scene_pack": "brand_studio|food_delivery|marketplace_white|fashion_flat|auto"\n'
            "}\n\n"
            "Rules:\n"
            "- Extract brand_colors from brief if seller mentions colors, stall branding, or surface mood.\n"
            "- surface_vibe captures the shared table/backdrop feel for all items in this stall session.\n"
            "- Prefer scene_pack brand_studio for market-day stalls unless food/fashion hints suggest otherwise.\n"
            "- Understand Kenyan/East African market speech: bei, shilingi, bob, nunua, leo, soko.\n"
            "- If seller says one price for everything, set bulk_price AND default_price.\n"
            "- Never invent a market name unless clearly stated.\n"
            "- Prefer KES when currency unclear.\n"
        )

        response = generate(
            prompt,
            system=(
                "You extract structured stall-day selling context for African SMEs. "
                "Respond with valid JSON only — no markdown."
            ),
            model=get_model_for_task("analysis"),
            json_mode=True,
            max_tokens=900,
        )
        parsed = parse_llm_json(response.content)
        if isinstance(parsed, dict):
            merged = {**base, **parsed}
            pr = merged.get("pricing_rules") or {}
            if not isinstance(pr, dict):
                pr = {}
            merged["pricing_rules"] = {**base["pricing_rules"], **pr}
            if merged["pricing_rules"].get("default_currency"):
                merged["pricing_rules"]["default_currency"] = str(
                    merged["pricing_rules"]["default_currency"]
                ).upper()[:5]
            return merged
    except Exception as exc:
        logger.warning("Stall brief LLM parse failed, using heuristics: %s", exc)

    return _heuristic_stall_parse(
        combined or stall_title,
        base,
        default_price=default_price,
        default_currency=default_currency,
    )


def _heuristic_stall_parse(
    text: str,
    base: dict,
    *,
    default_price=None,
    default_currency: str,
) -> dict:
    """Regex/heuristic fallback for voice brief parsing."""
    lower = text.lower()
    out = dict(base)
    if not out.get("stall_title"):
        out["stall_title"] = text.split(".")[0][:80].strip()

    # Price patterns: 800 bob, KES 500, sh 1200, bei 800
    price_match = re.search(
        r"(?:kes|ksh|sh\.?|bei)?\s*(\d{2,7}(?:\.\d{1,2})?)\s*(?:bob|ksh|sh|shilingi|/-)?",
        lower,
        re.I,
    )
    if not price_match:
        price_match = re.search(r"(\d{2,7}(?:\.\d{1,2})?)\s*bob", lower, re.I)
    if price_match:
        out["pricing_rules"]["default_price"] = float(price_match.group(1))
    elif _safe_decimal(default_price):
        out["pricing_rules"]["default_price"] = float(_safe_decimal(default_price))

    if "bei" in lower or "shilingi" in lower or "bob" in lower:
        out["language_mix"] = "mixed"
        out["swahili_phrases"] = ["Bei poa", "Karibu soko letu"]

    if "clearance" in lower or "discount" in lower:
        out["campaign_tone"] = "clearance_urgency"
    if "wholesale" in lower or "bulk" in lower:
        out["campaign_tone"] = "wholesale"

    out["pricing_rules"]["default_currency"] = default_currency
    out["market_context"] = text[:300]
    out.update(_heuristic_brand_from_text(text, out))
    return out


def _heuristic_brand_from_text(text: str, stall_context: dict) -> dict:
    """Rule-based brand colors / surface vibe when LLM is unavailable."""
    lower = text.lower()
    out: dict[str, Any] = {}

    color_map = {
        "coral": "FF6B5B",
        "orange": "FF8C42",
        "navy": "1A2B4A",
        "marble": "F5F0EB",
        "wood": "C4A882",
        "rustic": "D4C4A8",
        "gold": "D4AF37",
        "green": "2D6A4F",
        "mint": "98D8C8",
        "pink": "FFB6C1",
        "purple": "7B2CBF",
        "black": "1A1A1A",
        "white": "FAFAFA",
    }
    primary = ""
    for word, hex_val in color_map.items():
        if word in lower:
            primary = hex_val
            break
    if primary:
        out["brand_colors"] = {"primary": primary, "secondary": "000000"}

    if "boutique" in lower or "premium" in lower:
        out["surface_vibe"] = "clean boutique marble with soft premium lighting"
        out["scene_pack"] = "brand_studio"
        out["campaign_tone"] = stall_context.get("campaign_tone") or "premium_boutique"
    elif "food" in lower or "produce" in lower or "fresh" in lower:
        out["surface_vibe"] = "warm food-styling surface with natural daylight"
        out["scene_pack"] = "food_delivery"
    elif "fashion" in lower or "dress" in lower or "clothing" in lower:
        out["surface_vibe"] = "fashion flat-lay table with even studio lighting"
        out["scene_pack"] = "fashion_flat"
    elif "clearance" in lower:
        out["surface_vibe"] = "bright clearance table with energetic market-day feel"
        out["scene_pack"] = "marketplace_white"

    return out


def build_stall_brand_lock(
    stall_context: dict,
    *,
    profile,
    user_id,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Stall-wide brand template + scene pack — shared across every item in the batch session.

    Parsed from stall brief (colors, surface vibe) and stored on session.stall_context["brand_lock"].
    """
    from apps.products.photoroom_brand_template import build_photoroom_brand_template
    from apps.products.photoroom_plus import AI_BG_SEEDS
    from apps.products.scene_packs import (
        SCENE_PACK_AUTO,
        SCENE_PACK_BRAND_STUDIO,
        SCENE_PACK_FOOD_DELIVERY,
        SCENE_PACK_FASHION_FLAT,
        SCENE_PACK_MARKETPLACE_WHITE,
        normalize_scene_pack,
    )

    base_template = build_photoroom_brand_template(profile, user_id)
    brand_colors = stall_context.get("brand_colors") or {}
    if not isinstance(brand_colors, dict):
        brand_colors = {}
    primary = (brand_colors.get("primary") or "").strip().lstrip("#").upper()[:6]
    secondary = (brand_colors.get("secondary") or "000000").strip().lstrip("#").upper()[:6]

    if session_id:
        idx = abs(hash(str(session_id))) % len(AI_BG_SEEDS)
        ai_seed = AI_BG_SEEDS[idx]
    else:
        from apps.products.photoroom_brand_template import stable_ai_seed

        ai_seed = stable_ai_seed(user_id)

    tone = stall_context.get("campaign_tone", "energetic_market_day")
    tone_studio = {
        "energetic_market_day": "FFF8F0",
        "premium_boutique": "F5F0EB",
        "clearance_urgency": "FFFBF0",
        "wholesale": "F4F4F4",
    }
    studio_color = primary or tone_studio.get(tone, "FFFFFF")

    surface_vibe = (stall_context.get("surface_vibe") or "").strip()
    if not surface_vibe:
        surface_vibe = {
            "premium_boutique": "curated boutique marble with soft premium lighting",
            "clearance_urgency": "bright clearance table with energetic market-day feel",
            "wholesale": "clean wholesale display with even studio lighting",
        }.get(tone, "clean branded studio surface with soft natural lighting")

    stall_title = stall_context.get("stall_title") or "today's stall"
    tagline = (stall_context.get("stall_tagline") or "").strip()
    market = (stall_context.get("market_context") or "").strip()
    style_bits = [f"Cohesive market-day look for {stall_title}"]
    if surface_vibe:
        style_bits.append(f"Surface: {surface_vibe[:120]}")
    if tagline:
        style_bits.append(tagline[:120])
    if market:
        style_bits.append(market[:120])
    style_suffix = ". ".join(style_bits) + ". Consistent branded lighting across all stall items."

    scene_pack = normalize_scene_pack(stall_context.get("scene_pack") or SCENE_PACK_BRAND_STUDIO)
    category = (stall_context.get("category_hint") or "").lower()
    if scene_pack == SCENE_PACK_AUTO:
        if "food" in category or "produce" in category:
            scene_pack = SCENE_PACK_FOOD_DELIVERY
        elif "fashion" in category or "apparel" in category:
            scene_pack = SCENE_PACK_FASHION_FLAT
        elif tone == "clearance_urgency":
            scene_pack = SCENE_PACK_MARKETPLACE_WHITE
        else:
            scene_pack = SCENE_PACK_BRAND_STUDIO

    shadow_mode = base_template.shadow_mode if base_template.enabled else "ai.soft"
    padding = base_template.padding if base_template.enabled else "0.08"

    return {
        "enabled": True,
        "shadow_mode": shadow_mode,
        "padding": padding,
        "ai_background_seed": ai_seed,
        "outline_color_hex": secondary or "000000",
        "studio_color_hex": studio_color,
        "style_suffix": style_suffix,
        "scene_pack": scene_pack,
        "surface_vibe": surface_vibe,
        "source": "stall_brief",
    }


def photoroom_template_from_stall_lock(brand_lock: dict | None):
    """Convert session brand_lock JSON into a PhotoroomBrandTemplate."""
    from apps.products.photoroom_brand_template import PhotoroomBrandTemplate, stable_ai_seed

    if not brand_lock or not brand_lock.get("enabled"):
        return None

    return PhotoroomBrandTemplate(
        enabled=True,
        shadow_mode=str(brand_lock.get("shadow_mode", "ai.soft")),
        padding=str(brand_lock.get("padding", "0.08")),
        ai_background_seed=int(brand_lock.get("ai_background_seed", stable_ai_seed("batch"))),
        outline_color_hex=str(brand_lock.get("outline_color_hex", "000000")),
        studio_color_hex=str(brand_lock.get("studio_color_hex", "FFFFFF")),
        style_suffix=str(brand_lock.get("style_suffix", "")),
        source=str(brand_lock.get("source", "stall_brief")),
    )


def build_batch_vision_system_prompt(*, offering_type: str, stall_context: dict) -> str:
    tone = stall_context.get("campaign_tone", "energetic_market_day")
    return (
        "You are a senior catalog analyst for Kova Agent's Batch Snap — Market Day Mode. "
        "Sellers photograph many items quickly at a market stall, pop-up, or clearance table. "
        "Your job: identify each item precisely, respect stall pricing rules, and write "
        "customer-ready copy that feels local and trustworthy — never generic dropshipping tone.\n\n"
        f"Offering type: {offering_type}\n"
        f"Campaign tone: {tone}\n"
        "Always respond with valid JSON only."
    )


def build_batch_identification_prompt(
    *,
    offering_type: str,
    name: str,
    display_price: str,
    photo_context: str,
    stall_context: dict,
    batch_index: int,
    batch_total: int,
    sibling_names: list[str],
    needs_name: bool,
) -> str:
    """Batch-aware vision prompt — one photo, full stall context."""
    from apps.products.tasks import _build_vision_prompt

    core = _build_vision_prompt(
        offering_type=offering_type,
        name=name if not needs_name else "Unknown — identify from photo",
        display_price=display_price or "not set",
        num_images=1,
        photo_context=photo_context,
        name_is_placeholder=needs_name,
    )

    stall_block = _format_stall_context_for_prompt(stall_context)
    sibling_block = ""
    if sibling_names:
        sibling_block = (
            "\n\nOther items already identified in this batch (avoid duplicate names):\n"
            + ", ".join(f'"{n}"' for n in sibling_names[:12])
        )

    batch_block = (
        f"\n\nBATCH CONTEXT: This is item {batch_index + 1} of {batch_total} "
        "in a Market Day batch — the seller is listing their whole table today.\n"
        f"{stall_block}"
        f"{sibling_block}\n"
    )

    extra_fields = (
        ',\n  "product_name": "Final catalog name for this item (specific, not generic)",\n'
        '  "product_category": "Category for shop grouping",\n'
        '  "variant_group": "null or shared group label if this is size/color variant of another item",\n'
        '  "price_confidence": "tag|voice_default|inferred|unknown",\n'
        '  "local_buyer_hook": "One sentence hook for Kenyan/East African buyers"\n'
    )

    if core.rstrip().endswith("}"):
        core = core.rstrip()[:-1] + extra_fields + "\n}"
    else:
        core += extra_fields

    if not needs_name and name:
        core += f"\nThe seller's working title for this item: {name}\n"

    return core + batch_block


def _format_stall_context_for_prompt(stall_context: dict) -> str:
    if not stall_context:
        return ""

    pr = stall_context.get("pricing_rules") or {}
    lines = []
    if stall_context.get("stall_title"):
        lines.append(f"Stall / collection: {stall_context['stall_title']}")
    if stall_context.get("stall_tagline"):
        lines.append(f"Tagline: {stall_context['stall_tagline']}")
    if stall_context.get("market_context"):
        lines.append(f"Market context: {stall_context['market_context']}")
    if pr.get("default_price"):
        lines.append(
            f"Default price when not visible: {pr['default_currency']} {pr['default_price']}"
        )
    if pr.get("bulk_price"):
        lines.append(f"Bulk/table price: {pr['default_currency']} {pr['bulk_price']}")
    if pr.get("price_notes"):
        lines.append(f"Pricing notes: {pr['price_notes']}")
    if stall_context.get("category_hint"):
        lines.append(f"Category hint: {stall_context['category_hint']}")
    if stall_context.get("size_variant_hint"):
        lines.append(f"Variants: {stall_context['size_variant_hint']}")
    if stall_context.get("do_not_say"):
        lines.append(f"Avoid saying: {', '.join(stall_context['do_not_say'][:5])}")
    if stall_context.get("language_mix") == "mixed" and stall_context.get("swahili_phrases"):
        lines.append(
            "Weave in natural Swahili/Sheng sparingly: "
            + ", ".join(stall_context["swahili_phrases"][:3])
        )
    return "\n".join(lines)


def resolve_batch_item_price(
    *,
    product,
    analysis: dict,
    stall_context: dict,
    form_price,
) -> tuple[Decimal | None, str]:
    """
    Resolve price from: visible tag > form > voice default > bulk default.
    Returns (price, source_label).
    """
    pr = stall_context.get("pricing_rules") or {}

    detected = analysis.get("detected_price")
    if detected is not None:
        d = _safe_decimal(detected)
        if d is not None and d > 0:
            return d, "tag"

    if form_price is not None:
        d = _safe_decimal(form_price)
        if d is not None and d > 0:
            return d, "form"

    if pr.get("apply_default_to_blanks", True):
        for key in ("default_price", "bulk_price"):
            d = _safe_decimal(pr.get(key))
            if d is not None and d > 0:
                return d, f"voice_{key}"

    if product.price is not None:
        d = _safe_decimal(product.price)
        if d is not None and d > 0:
            return d, "existing"

    return None, "unknown"


def build_batch_seed_idea(
    *,
    offering_type: str,
    product,
    analysis: dict,
    stall_context: dict,
    features_text: str,
    audience_text: str,
    image_note: str,
) -> str:
    """Rich ContentSeed idea — batch-aware, stall tone."""
    from apps.products.tasks import _build_seed_idea

    angle = analysis.get("campaign_angle") or stall_context.get("collection_angle") or "showcase"
    hook = analysis.get("local_buyer_hook") or stall_context.get("stall_tagline") or ""

    base = _build_seed_idea(
        offering_type=offering_type,
        name=product.name,
        display_price=product.display_price,
        features_text=features_text,
        campaign_angle=angle,
        audience_text=audience_text,
        image_note=image_note,
        description_text=analysis.get("description") or product.description or "",
    )

    stall_title = stall_context.get("stall_title") or "today's stall"
    batch_note = (
        f"\n\nMARKET DAY BATCH: This post is part of '{stall_title}' — "
        "a multi-item stall launch. Make it feel fresh-today and specific to THIS item, "
        "not a generic catalog dump. "
    )
    if hook:
        batch_note += f"Buyer hook inspiration: {hook}. "
    if stall_context.get("market_context"):
        batch_note += f"Context: {stall_context['market_context'][:200]}. "

    tone_map = {
        "energetic_market_day": "High energy, same-day availability, friendly market seller voice.",
        "premium_boutique": "Curated, quality-first, boutique confidence.",
        "clearance_urgency": "Limited stock, today-only urgency without fake scarcity.",
        "wholesale": "Value packs, bulk-friendly, B2B-aware.",
    }
    batch_note += tone_map.get(
        stall_context.get("campaign_tone", ""),
        "Warm, trustworthy, mobile-first social commerce tone.",
    )

    return base + batch_note


def build_stall_launch_campaign(
    *,
    stall_context: dict,
    products: list,
    profile,
    shop_url: str,
) -> dict[str, Any]:
    """
    Generate stall-wide launch assets: collection seed idea, reel caption, seller WhatsApp text.
    """
    product_lines = []
    for p in products[:12]:
        price = p.display_price or "Price on request"
        product_lines.append(f"- {p.name} ({price})")

    catalog_block = "\n".join(product_lines) or "- (items loading)"
    stall_title = (
        stall_context.get("stall_title")
        or profile.company_name
        or profile.user.full_name
        or "Today's stall"
    )

    fallback = {
        "collection_idea": (
            f"🛍️ {stall_title} is LIVE — {len(products)} fresh listing"
            f"{'s' if len(products) != 1 else ''} just dropped. "
            f"Browse the full table: {shop_url}"
        ),
        "reel_caption": (
            f"{stall_title} 🔥\n"
            f"{len(products)} items ready today.\n"
            f"Shop: {shop_url}"
        ),
        "reel_hook_text": stall_context.get("stall_tagline") or f"{stall_title} — open now",
        "whatsapp_message": (
            f"✅ Your stall is live on Kova!\n\n"
            f"{len(products)} product{'s' if len(products) != 1 else ''} listed.\n"
            f"Share your shop: {shop_url}"
        ),
        "hashtags": ["ShopLocal", "MarketDay", "SmallBusiness"],
    }

    try:
        from apps.agents.llm import generate, get_model_for_task, parse_llm_json

        brand = profile.brand_voice or profile.company_name or "the seller"
        prompt = (
            "You are Kova's Create Agent writing a MARKET DAY launch bundle for an African seller.\n\n"
            f"Brand voice: {brand[:400]}\n"
            f"Stall context JSON:\n{json.dumps(stall_context, ensure_ascii=False)[:2000]}\n\n"
            f"Shop URL: {shop_url}\n\n"
            "Items in this batch:\n"
            f"{catalog_block}\n\n"
            "Return JSON ONLY:\n"
            "{\n"
            '  "collection_idea": "Detailed brief for AI to write a multi-product stall announcement post (2-4 sentences of direction, not the post itself)",\n'
            '  "reel_caption": "Short reel caption with line breaks, emoji-light, includes shop URL",\n'
            '  "reel_hook_text": "3-6 word on-screen hook for first reel frame",\n'
            '  "whatsapp_message": "Message TO THE SELLER (not buyer) confirming stall is live + shop link to forward to customers. Max 320 chars.",\n'
            '  "hashtags": ["3-6 relevant hashtags without # prefix"]\n'
            "}\n\n"
            "Tone: energetic, trustworthy, mobile-first. Mix English/Swahili only if stall context says mixed."
        )

        response = generate(
            prompt,
            system=(
                "You write high-converting social commerce launch copy for East African market sellers. "
                "JSON only."
            ),
            model=get_model_for_task("create"),
            json_mode=True,
            max_tokens=800,
        )
        parsed = parse_llm_json(response.content)
        if isinstance(parsed, dict):
            return {**fallback, **parsed}
    except Exception as exc:
        logger.warning("Stall launch campaign LLM failed: %s", exc)

    return fallback


def is_batch_placeholder_name(name: str) -> bool:
    """True when the seller did not provide a real name — AI should rename."""
    if not name or not name.strip():
        return True
    n = name.strip()
    if n.startswith("Listing ") and n[8:].isdigit():
        return True
    if n.startswith("Product ") and n[8:].isdigit():
        return True
    if n.lower() in {"untitled", "item", "new item", "new product"}:
        return True
    return False
