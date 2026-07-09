"""
Campaign bundle spec — every activated campaign delivers a full marketing package.

v1 base-plan deliverables (when platforms are connected):
  - IG feed post
  - FB feed post
  - IG carousel (5–6 funnel slides)
  - IG story set (3 frames)
  - 1 reel per video platform (IG reel, FB reel, TikTok reel when connected)
  - LinkedIn + TikTok copy when those accounts are connected

Enforcement runs after the Create Agent LLM pass so structural gaps are filled
programmatically even when the model only returns one post per platform.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

BUNDLE_ROLE_KEY = "bundle_role"

# Funnel carousel: hook → problem → solution → proof → offer → CTA
FUNNEL_SLIDE_ROLES = ("hook", "problem", "solution", "proof", "offer", "cta")
CAROUSEL_MIN_SLIDES = 5
CAROUSEL_TARGET_SLIDES = 6
STORY_FRAME_COUNT = 3
REEL_PLATFORM_PRIORITY = ("instagram", "tiktok", "facebook")

BUNDLE_LABELS = {
    "ig_feed": "IG feed",
    "fb_feed": "FB post",
    "ig_carousel": "IG Carousel",
    "fb_carousel": "FB Carousel",
    "ig_story_1": "Story 1",
    "ig_story_2": "Story 2",
    "ig_story_3": "Story 3",
    "ig_reel": "IG Reel",
    "fb_reel": "FB Reel",
    "primary_reel": "Reel",  # legacy tag from older campaigns
    "linkedin_copy": "LinkedIn",
    "tiktok_copy": "TikTok",
}

BUNDLE_PROFILES = {
    "product": {
        "carousel_intent": "offer",
        "cta_primary": "Order now",
        "cta_whatsapp": "Order on WhatsApp",
        "cta_story": "Shop now — link in bio 👆",
        "include_shop_link": True,
        "reel_style": "product_showcase",
    },
    "service": {
        "carousel_intent": "faq",
        "cta_primary": "Book now",
        "cta_whatsapp": "Book on WhatsApp",
        "cta_story": "Book now — link in bio 👆",
        "include_shop_link": False,
        "reel_style": "service_showcase",
    },
    "professional": {
        "carousel_intent": "educational",
        "cta_primary": "Book a consultation",
        "cta_whatsapp": "DM for details",
        "cta_story": "Book a consultation — link in bio 👆",
        "include_shop_link": False,
        "reel_style": "authority",
    },
}


def _resolve_business_model(seed) -> str:
    profile = getattr(getattr(seed, "user", None), "profile", None)
    bm = (getattr(profile, "business_model", None) or "").strip()
    if bm in BUNDLE_PROFILES:
        return bm
    return "product"


def get_bundle_profile(seed) -> dict[str, Any]:
    return dict(BUNDLE_PROFILES[_resolve_business_model(seed)])


# Content-type filters selected by the merchant after product upload.
# Default = all. Keys match the proposal UI checkboxes.
CONTENT_TYPE_ALL = frozenset({"reels", "carousels", "text", "stories", "images"})

_ROLE_CONTENT_TYPES: dict[str, str] = {
    "ig_feed": "images",
    "fb_feed": "text",
    "ig_carousel": "carousels",
    "fb_carousel": "carousels",
    "ig_story_1": "stories",
    "ig_story_2": "stories",
    "ig_story_3": "stories",
    "ig_reel": "reels",
    "fb_reel": "reels",
    "primary_reel": "reels",
    "linkedin_copy": "text",
    "tiktok_copy": "reels",
}

# Map Post.post_format → content-type checkbox key
_FORMAT_CONTENT_TYPES: dict[str, str] = {
    "reel": "reels",
    "carousel": "carousels",
    "story": "stories",
    "image": "images",
    "text": "text",
}


def post_format_allowed(post_format: str, content_types: set[str] | list[str] | None) -> bool:
    """True if this post_format is in the merchant's selected content types."""
    allowed = normalize_content_types(content_types)
    if allowed >= set(CONTENT_TYPE_ALL):
        return True
    key = _FORMAT_CONTENT_TYPES.get((post_format or "text").lower().strip(), "text")
    return key in allowed


def normalize_content_types(selected: list[str] | set[str] | None) -> set[str]:
    """Return a set of content-type keys; empty/None means all."""
    if not selected:
        return set(CONTENT_TYPE_ALL)
    cleaned = {str(x).strip().lower() for x in selected if str(x).strip()}
    if not cleaned or "all" in cleaned:
        return set(CONTENT_TYPE_ALL)
    return cleaned & set(CONTENT_TYPE_ALL) or set(CONTENT_TYPE_ALL)


def content_types_from_seed(seed) -> set[str]:
    """Read merchant content-type selection from seed.blueprint."""
    blueprint = getattr(seed, "blueprint", None) or {}
    return normalize_content_types(blueprint.get("selected_content_types"))


def required_bundle_roles(
    connected_platforms: set[str] | list[str],
    *,
    content_types: set[str] | list[str] | None = None,
) -> list[str]:
    """Ordered list of bundle slots required for the user's connected platforms."""
    platforms = {p.lower() for p in connected_platforms}
    allowed = normalize_content_types(content_types)
    roles: list[str] = []

    if "instagram" in platforms:
        roles.extend([
            "ig_feed",
            "ig_carousel",
            "ig_story_1",
            "ig_story_2",
            "ig_story_3",
        ])
    if "facebook" in platforms:
        roles.extend(["fb_feed", "fb_carousel"])
    if "instagram" in platforms:
        roles.append("ig_reel")
    if "facebook" in platforms:
        roles.append("fb_reel")
    if "linkedin" in platforms:
        roles.append("linkedin_copy")
    if "tiktok" in platforms:
        roles.append("tiktok_copy")

    if allowed >= set(CONTENT_TYPE_ALL):
        return roles
    return [r for r in roles if _ROLE_CONTENT_TYPES.get(r, "text") in allowed]


def _bundle_role(post) -> str:
    dna = getattr(post, "content_dna", None) or {}
    role = (dna.get(BUNDLE_ROLE_KEY) or "").strip()
    return role


def _set_bundle_role(post, role: str) -> None:
    dna = dict(post.content_dna or {})
    dna[BUNDLE_ROLE_KEY] = role
    post.content_dna = dna
    post.save(update_fields=["content_dna", "updated_at"])


def _campaign_context(seed) -> dict[str, str]:
    """Extract names and hooks from seed + optional product."""
    idea = (getattr(seed, "idea", None) or "").strip()
    first_line = idea.split("\n")[0][:160] if idea else "Your next favourite find"
    product = getattr(seed, "product", None)
    name = (getattr(product, "name", None) or first_line[:80] or "this").strip()
    price = ""
    if product:
        price = (getattr(product, "display_price", None) or "").strip()
    campaign = getattr(seed, "marketing_campaign", None)
    title = (getattr(campaign, "title", None) or first_line[:120] or name).strip()
    return {
        "idea": idea,
        "hook": first_line,
        "name": name,
        "price": price,
        "title": title,
    }


def build_funnel_carousel_slides(seed, *, slide_count: int = CAROUSEL_TARGET_SLIDES) -> list[dict]:
    """Build 5–6 funnel-structured carousel slides from seed context."""
    from apps.media.carousel_strategy import CarouselStrategy

    blueprint = getattr(seed, "blueprint", None) or {}
    campaign = getattr(seed, "marketing_campaign", None)
    cs_data = blueprint.get("carousel_strategy")
    if not cs_data and campaign:
        cs_data = (campaign.proposal_meta or {}).get("carousel_strategy")
    strategy = CarouselStrategy.from_dict(cs_data)
    if strategy and strategy.slides:
        return strategy.to_carousel_slides()

    profile = get_bundle_profile(seed)
    ctx = _campaign_context(seed)
    name, price, title = ctx["name"], ctx["price"], ctx["title"]
    count = max(CAROUSEL_MIN_SLIDES, min(slide_count, len(FUNNEL_SLIDE_ROLES)))
    bm = _resolve_business_model(seed)

    if bm == "service":
        templates = [
            ("hook", f"Need {name}?", "Here's how we help — swipe to learn more 👉", f"Professional service hero, {name}, warm trust-building mood, square"),
            ("problem", "Sound familiar?", "Finding reliable service shouldn't be this hard.", "Relatable client moment, candid feel, square"),
            ("solution", f"Meet {name}", "Expert care, clear process, results you can count on.", f"{name} in action, clean professional setting, square"),
            ("proof", "What clients say", "Real reviews from people who booked and came back.", "Testimonial-style visual, bright natural light, square"),
            ("offer", title[:60] if title else "Ready to book?", f"{price + ' · ' if price else ''}Limited slots — reserve yours.", "Booking CTA energy, calm professional tones, square"),
            ("cta", "Book today", profile["cta_primary"] + " — link in bio 💾", "Clear booking CTA visual, brand-forward, square"),
        ]
    elif bm == "professional":
        templates = [
            ("hook", f"Why {name}?", "The insight your industry needs — swipe 👉", f"Authority visual for {name}, polished professional, square"),
            ("problem", "The challenge", "Most businesses struggle to stand out and convert attention.", "Business challenge visual, editorial style, square"),
            ("solution", "The approach", f"{name} — proven expertise, measurable outcomes.", f"Expert at work, {name}, authoritative mood, square"),
            ("proof", "Results delivered", "Case studies and client wins that speak for themselves.", "Results / portfolio visual, clean layout, square"),
            ("offer", title[:60] if title else "Work with us", f"{price + ' · ' if price else ''}Consultation slots available.", "Consultation CTA, premium professional tone, square"),
            ("cta", "Let's talk", profile["cta_primary"] + " — link in bio 💾", "Consultation booking CTA, square"),
        ]
    else:
        templates = [
            (
                "hook",
                f"Wait — {name}",
                f"Something special just dropped. Swipe to see why everyone's talking 👉",
                f"Eye-catching hero shot of {name}, vibrant lighting, premium product photography, 1:1 square",
            ),
            (
                "problem",
                "Sound familiar?",
                f"Tired of settling for less? You deserve {name} that actually delivers.",
                f"Relatable lifestyle moment showing frustration, warm tones, candid feel, square crop",
            ),
            (
                "solution",
                f"Meet {name}",
                "Designed for real life — quality you can feel from day one.",
                f"{name} in use, clean minimal background, aspirational but authentic, square",
            ),
            (
                "proof",
                "Why customers love it",
                "Real results. Happy customers. Repeat buyers. That's the standard.",
                f"Happy customer with {name}, social proof mood, bright natural light, square",
            ),
            (
                "offer",
                title[:60] if title else f"Get {name} today",
                f"{price + ' — ' if price else ''}Limited availability. Don't miss out.",
                f"{name} with subtle promo energy, bold colors, urgency without clutter, square",
            ),
            (
                "cta",
                "Ready?",
                f"Tap the link in bio to shop {name}. Save this post for later 💾",
                f"Clear CTA visual for {name}, bold headline space, brand-forward, square",
            ),
        ]

    slides = []
    for role, heading, body, image_prompt in templates[:count]:
        slides.append({
            "heading": heading[:60],
            "body": body[:150],
            "image_prompt": image_prompt[:500],
            "image_url": "",
            "funnel_role": role,
        })
    return slides


def _story_frame_content(seed, frame_index: int) -> dict[str, str]:
    """Three-part story arc: hook → value → CTA."""
    profile = get_bundle_profile(seed)
    ctx = _campaign_context(seed)
    name, price, title = ctx["name"], ctx["price"], ctx["title"]
    bm = _resolve_business_model(seed)
    if bm == "service":
        value_line = f"{price + ' · ' if price else ''}Trusted by clients who book again."
        cta_text = f"📅 {profile['cta_story']}\n\n💾 Save this!"
        cta_headline = "Book now"
    elif bm == "professional":
        value_line = "Expertise you can trust — real outcomes."
        cta_text = f"💼 {profile['cta_story']}\n\n💾 Save this!"
        cta_headline = "Consult"
    else:
        value_line = f"{price + ' · ' if price else ''}Quality that speaks for itself."
        cta_text = f"🛍️ {profile['cta_story']}\n\n💾 Save this!"
        cta_headline = "Shop now"
    frames = [
        {
            "content_text": f"🔥 {title[:40]}\n\nSwipe up 👆",
            "headline": title[:40],
            "body": "You need to see this",
            "image_prompt": (
                f"Vertical 9:16 story graphic, bold hook text area, energetic colors, "
                f"product {name} hero, no embedded text in image"
            ),
        },
        {
            "content_text": f"✨ Why {name}?\n\n{value_line}",
            "headline": f"Why {name}?",
            "body": "The details that matter",
            "image_prompt": (
                f"Vertical 9:16 lifestyle scene featuring {name}, warm authentic mood, "
                f"space for overlay text, no words in image"
            ),
        },
        {
            "content_text": cta_text,
            "headline": cta_headline,
            "body": "Link in bio",
            "image_prompt": (
                f"Vertical 9:16 CTA story frame, {name} with shop-now energy, "
                f"vibrant gradient background, no text in image"
            ),
        },
    ]
    idx = max(0, min(frame_index, len(frames) - 1))
    return frames[idx]


def _best_source_post(posts: list) -> Any | None:
    """Pick the richest post to clone angles/copy from."""
    if not posts:
        return None

    def score(p):
        s = len(p.content_text or "")
        if p.post_format in ("image", "carousel", "reel"):
            s += 50
        if getattr(p, "predicted_engagement_score", None):
            s += int(p.predicted_engagement_score)
        return s

    return max(posts, key=score)


def _post_slot_status(post) -> str:
    """ready | pending_media | missing (should not happen for existing post)."""
    if getattr(post, "needs_media", False):
        return "pending_media"
    if post.post_format in ("image", "carousel", "story", "reel") and not post.has_media:
        if post.post_format == "text":
            return "ready"
        return "pending_media"
    return "ready"


def _matches_ig_feed(post) -> bool:
    return (
        post.platform == "instagram"
        and post.post_format in ("image", "text")
        and post.post_format != "story"
    )


def _matches_ig_carousel(post) -> bool:
    return (
        post.platform == "instagram"
        and post.post_format == "carousel"
        and len(post.carousel_slides or []) >= CAROUSEL_MIN_SLIDES
    )


def _matches_fb_feed(post) -> bool:
    return post.platform == "facebook" and post.post_format in ("text", "image")


def _matches_fb_carousel(post) -> bool:
    return (
        post.platform == "facebook"
        and post.post_format == "carousel"
        and len(post.carousel_slides or []) >= 2
    )


def _matches_ig_reel(post) -> bool:
    return post.platform == "instagram" and post.post_format == "reel"


def _matches_fb_reel(post) -> bool:
    return post.platform == "facebook" and post.post_format == "reel"


def _matches_reel(post) -> bool:
    return post.post_format == "reel" and post.platform in REEL_PLATFORM_PRIORITY


def _matches_linkedin(post) -> bool:
    return post.platform == "linkedin"


def _matches_tiktok(post) -> bool:
    return post.platform == "tiktok" and post.post_format == "reel"


def assign_bundle_roles(posts: list) -> dict[str, Any]:
    """
    Map bundle roles to posts. Tags content_dna and returns role → post dict.
    Legacy primary_reel tags map to ig_reel / fb_reel / tiktok_copy by platform.
    """
    from apps.content.models import Post

    role_map: dict[str, Any] = {}
    used: set = set()

    def claim(role: str, post) -> None:
        if role in role_map or post.pk in used:
            return
        role_map[role] = post
        used.add(post.pk)
        if not _bundle_role(post):
            _set_bundle_role(post, role)

    # Explicit tags win (normalize legacy primary_reel → platform reel roles)
    for post in posts:
        role = _bundle_role(post)
        if not role:
            continue
        if role == "primary_reel":
            if post.platform == "instagram":
                role = "ig_reel"
            elif post.platform == "facebook":
                role = "fb_reel"
            elif post.platform == "tiktok":
                role = "tiktok_copy"
        if role and role not in role_map:
            role_map[role] = post
            used.add(post.pk)

    # IG carousel — prefer most slides
    carousels = [p for p in posts if p.pk not in used and _matches_ig_carousel(p)]
    if carousels:
        claim("ig_carousel", max(carousels, key=lambda p: len(p.carousel_slides or [])))

    # FB carousel (multi-photo album)
    fb_carousels = [p for p in posts if p.pk not in used and _matches_fb_carousel(p)]
    if fb_carousels:
        claim("fb_carousel", max(fb_carousels, key=lambda p: len(p.carousel_slides or [])))

    # Platform reels
    ig_reels = [p for p in posts if p.pk not in used and _matches_ig_reel(p)]
    if ig_reels:
        claim("ig_reel", ig_reels[0])

    fb_reels = [p for p in posts if p.pk not in used and _matches_fb_reel(p)]
    if fb_reels:
        claim("fb_reel", fb_reels[0])

    # Legacy: unattributed reel → highest-priority platform slot still open
    reels = [p for p in posts if p.pk not in used and _matches_reel(p)]
    if reels:
        order = {plat: i for i, plat in enumerate(REEL_PLATFORM_PRIORITY)}
        best_reel = min(reels, key=lambda p: order.get(p.platform, 99))
        if best_reel.platform == "instagram" and "ig_reel" not in role_map:
            claim("ig_reel", best_reel)
        elif best_reel.platform == "facebook" and "fb_reel" not in role_map:
            claim("fb_reel", best_reel)
        elif best_reel.platform == "tiktok":
            claim("tiktok_copy", best_reel)

    # IG feed
    ig_feeds = [p for p in posts if p.pk not in used and _matches_ig_feed(p)]
    if ig_feeds:
        images = [p for p in ig_feeds if p.post_format == "image"]
        claim("ig_feed", images[0] if images else ig_feeds[0])

    # FB feed
    fb_feeds = [p for p in posts if p.pk not in used and _matches_fb_feed(p)]
    if fb_feeds:
        claim("fb_feed", fb_feeds[0])

    # IG stories — up to 3 story-format posts
    stories = [
        p for p in posts
        if p.pk not in used and p.platform == "instagram" and p.post_format == "story"
    ]
    for i, post in enumerate(stories[:STORY_FRAME_COUNT], start=1):
        claim(f"ig_story_{i}", post)

    # LinkedIn
    li_posts = [p for p in posts if p.pk not in used and _matches_linkedin(p)]
    if li_posts:
        claim("linkedin_copy", li_posts[0])

    # TikTok reel (if not already satisfied)
    if "tiktok_copy" not in role_map:
        tiktok_reels = [p for p in posts if p.pk not in used and _matches_tiktok(p)]
        if tiktok_reels:
            claim("tiktok_copy", tiktok_reels[0])

    return role_map


def audit_campaign_bundle(
    posts: list,
    connected_platforms: set[str] | list[str] | None = None,
    *,
    content_types: set[str] | list[str] | None = None,
    seed=None,
) -> dict[str, Any]:
    """Return completeness audit for a campaign's posts."""
    platforms = {p.lower() for p in (connected_platforms or [])}
    if not platforms and posts:
        platforms = {p.platform for p in posts if p.platform}

    types = content_types
    if types is None and seed is not None:
        types = content_types_from_seed(seed)
    required = required_bundle_roles(platforms, content_types=types)
    role_map = assign_bundle_roles(posts)

    slots: dict[str, dict] = {}
    ready = 0
    for role in required:
        post = role_map.get(role)
        if not post:
            slots[role] = {"status": "missing", "post_id": None}
            continue
        status = _post_slot_status(post)
        slots[role] = {"status": status, "post_id": str(post.pk)}
        if status == "ready":
            ready += 1

    total = len(required)
    return {
        "required": required,
        "slots": slots,
        "role_map": role_map,
        "ready_count": ready,
        "total_count": total,
        "complete": ready >= total and total > 0,
        "connected_platforms": sorted(platforms),
    }


def persist_bundle_audit(campaign, audit: dict) -> None:
    """Store bundle audit snapshot on MarketingCampaign.proposal_meta."""
    if not campaign:
        return
    meta = dict(campaign.proposal_meta or {})
    serializable_slots = {
        role: {"status": slot["status"], "post_id": slot.get("post_id")}
        for role, slot in (audit.get("slots") or {}).items()
    }
    meta["bundle_audit"] = {
        "complete": audit.get("complete", False),
        "ready_count": audit.get("ready_count", 0),
        "total_count": audit.get("total_count", 0),
        "slots": serializable_slots,
    }
    campaign.proposal_meta = meta
    campaign.save(update_fields=["proposal_meta", "updated_at"])


def _collapse_story_items(items: list[dict]) -> list[dict]:
    """Merge ig_story_1/2/3 into one Studio pill."""
    stories = [i for i in items if i["role"].startswith("ig_story_")]
    if not stories:
        return items
    other = [i for i in items if not i["role"].startswith("ig_story_")]
    ready = sum(1 for s in stories if s["ready"])
    total = len(stories)
    if ready == total:
        status = "ready"
    elif any(s["pending_media"] for s in stories):
        status = "pending_media"
    elif any(s["missing"] for s in stories):
        status = "missing"
    else:
        status = "pending_media"
    other.append({
        "role": "ig_stories",
        "label": f"Stories ({ready}/{total})",
        "status": status,
        "ready": status == "ready",
        "pending_media": status == "pending_media",
        "missing": status == "missing",
    })
    return other


def bundle_display_for_studio(posts: list, connected_platforms=None) -> dict[str, Any]:
    """Compact bundle checklist for Studio campaign cards."""
    audit = audit_campaign_bundle(posts, connected_platforms)
    items = []
    for role in audit["required"]:
        slot = audit["slots"].get(role, {})
        status = slot.get("status", "missing")
        label = BUNDLE_LABELS.get(role, role.replace("_", " ").title())
        if role.startswith("ig_story_"):
            label = f"Story {role[-1]}"
        items.append({
            "role": role,
            "label": label,
            "status": status,
            "ready": status == "ready",
            "pending_media": status == "pending_media",
            "missing": status == "missing",
        })

    display_items = _collapse_story_items(items)
    ready_labels = [it["label"] for it in display_items if it["ready"]]
    summary = " · ".join(ready_labels[:6]) if ready_labels else "Building campaign package…"

    return {
        "complete": audit["complete"],
        "ready_count": audit["ready_count"],
        "total_count": audit["total_count"],
        "items": items,
        "display_items": display_items,
        "summary_line": summary,
    }


def _adapt_caption(text: str, platform: str, max_len: int = 2200) -> str:
    from apps.content.post_copy import polish_post_caption

    cleaned = polish_post_caption(text or "", platform)
    if not cleaned:
        return ""
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def _reel_slot_payload(seed, platform: str) -> dict[str, Any]:
    """Build reel post fields for a specific platform."""
    from apps.content.models import Post

    ctx = _campaign_context(seed)
    hook = ctx["hook"][:120]
    if platform == "facebook":
        reel_caption = hook
        if ctx["price"]:
            reel_caption += f"\n\n{ctx['price']}"
        reel_caption += "\n\nWatch till the end 👇"
    elif platform == "tiktok":
        reel_caption = f"{hook[:80]} 🔥\n\n#fyp #smallbusiness"
    else:
        reel_caption = f"{hook}\n\n{'💰 ' + ctx['price'] + chr(10) if ctx['price'] else ''}Link in bio 👆"

    visual_meta: dict[str, Any] = {
        "image_prompt": (
            f"Vertical 9:16 premium product photography of {ctx['name']}, "
            f"clean minimal scene, soft natural light, reel-ready, no text in image"
        ),
        "bundle_synthesized": True,
    }
    product = getattr(seed, "product", None)
    if product:
        from apps.products.reel_curation import curate_reel_image_urls

        urls = list(getattr(product, "all_image_urls", None) or [])
        if urls:
            curated = curate_reel_image_urls(urls)
            visual_meta["source_images"] = curated
            if len(curated) >= 2:
                visual_meta["reel_compose_backend"] = "ffmpeg"
                visual_meta["prefer_photoroom_video"] = False

    label = {
        "instagram": "IG",
        "facebook": "Facebook",
        "tiktok": "TikTok",
    }.get(platform, platform.title())

    return {
        "platform": platform,
        "post_format": Post.PostFormat.REEL,
        "content_text": _adapt_caption(reel_caption, platform, 2200),
        "content_intent": "offer",
        "image_prompt": visual_meta["image_prompt"],
        "aspect_ratio": Post.AspectRatio.STORY,
        "visual_strategy": "ai_photo",
        "visual_metadata": visual_meta,
        "ai_angle": f"Campaign bundle — {label} motion reel",
    }


def _synthesize_slot_payload(
    role: str,
    seed,
    source_post,
    *,
    reel_platform: str | None = None,
) -> dict[str, Any]:
    """Build post field dict for a missing bundle slot."""
    from apps.content.models import Post

    ctx = _campaign_context(seed)
    source_text = (getattr(source_post, "content_text", None) or ctx["hook"]) if source_post else ctx["hook"]

    if role == "ig_feed":
        return {
            "platform": "instagram",
            "post_format": Post.PostFormat.IMAGE,
            "content_text": _adapt_caption(source_text, "instagram", 2200),
            "content_intent": "offer",
            "image_prompt": (
                f"Square Instagram feed photo of {ctx['name']}, premium product photography, "
                f"vibrant and scroll-stopping, no text in image"
            ),
            "aspect_ratio": Post.AspectRatio.SQUARE,
            "ai_angle": "Campaign bundle — IG feed hero",
        }

    if role == "fb_feed":
        return {
            "platform": "facebook",
            "post_format": Post.PostFormat.TEXT,
            "content_text": _adapt_caption(source_text, "facebook", 5000),
            "content_intent": "offer",
            "image_prompt": "",
            "ai_angle": "Campaign bundle — Facebook feed",
        }

    if role in ("ig_carousel", "fb_carousel"):
        platform = "facebook" if role == "fb_carousel" else "instagram"
        slides = build_funnel_carousel_slides(seed)
        caption = _adapt_caption(
            f"{ctx['title']}\n\nSwipe through 👉 Save for later 💾",
            platform,
        )
        return {
            "platform": platform,
            "post_format": Post.PostFormat.CAROUSEL,
            "content_text": caption,
            "content_intent": "solution",
            "carousel_slides": slides,
            "aspect_ratio": Post.AspectRatio.SQUARE,
            "visual_strategy": "carousel",
            "image_prompt": "",
            "ai_angle": f"Campaign bundle — {platform} funnel carousel",
        }

    if role.startswith("ig_story_"):
        frame_num = int(role.rsplit("_", 1)[-1])
        frame = _story_frame_content(seed, frame_num - 1)
        return {
            "platform": "instagram",
            "post_format": Post.PostFormat.STORY,
            "content_text": frame["content_text"],
            "content_intent": "offer" if frame_num == STORY_FRAME_COUNT else "awareness",
            "image_prompt": frame["image_prompt"],
            "aspect_ratio": Post.AspectRatio.STORY,
            "visual_strategy": "story_graphic",
            "ai_angle": f"Campaign bundle — story frame {frame_num}",
        }

    if role in ("ig_reel", "primary_reel"):
        return _reel_slot_payload(seed, reel_platform or "instagram")

    if role == "fb_reel":
        return _reel_slot_payload(seed, "facebook")

    if role == "linkedin_copy":
        li_text = _adapt_caption(source_text, "linkedin", 3000)
        if ctx["price"] and ctx["price"] not in li_text:
            li_text = f"{li_text}\n\n{ctx['price']}"
        return {
            "platform": "linkedin",
            "post_format": Post.PostFormat.TEXT,
            "content_text": li_text,
            "content_intent": "authority",
            "image_prompt": "",
            "ai_angle": "Campaign bundle — LinkedIn thought leadership",
        }

    if role == "tiktok_copy":
        return _reel_slot_payload(seed, "tiktok")

    return {}


def _apply_post_defaults(post, seed, user, platform: str) -> None:
    """CTA, UTM, and platform first-comments — mirrors create_agent essentials."""
    from apps.content.campaign_cta import apply_default_campaign_cta, commerce_url_for_first_comment
    from apps.content.professional_cta import apply_professional_cta_to_post
    from apps.agents.create_agent import _get_kova_page_url
    from apps.utils.first_comments import compose_first_comment

    post.populate_utm()
    profile = getattr(user, "profile", None)

    if not apply_professional_cta_to_post(post, user, seed):
        apply_default_campaign_cta(post, user, seed)

    commerce_url = commerce_url_for_first_comment(seed, user) if seed else ""
    kova_page_url = _get_kova_page_url(user)

    if platform == "facebook" and not (post.first_comment or "").strip():
        fc = compose_first_comment(
            platform="facebook",
            post=post,
            product=getattr(seed, "product", None) if seed else None,
            profile=profile,
            kova_page_url=kova_page_url,
            commerce_url=commerce_url,
        )
        if fc:
            post.first_comment = fc
            post.save(update_fields=["first_comment", "updated_at"])

    if platform == "instagram":
        ig_fc = ""
        if commerce_url:
            display_name = "our shop"
            try:
                display_name = seed.marketing_campaign.title or display_name
            except Exception:
                if seed and getattr(seed, "product", None):
                    display_name = seed.product.name or display_name
            ig_fc = f"💾 Save this! 🛍️ {display_name} — link in bio 👆"
        elif seed and getattr(seed, "product", None) and getattr(seed.product, "product_url", ""):
            ig_fc = f"💾 Save this! 🛍️ Shop {seed.product.name} — link in bio 👆"
        elif kova_page_url:
            ig_fc = "💾 Save this post for later! 🔗 Everything's at the link in bio 👆"
        else:
            ig_fc = "💾 Save this for later!"
        post.first_comment = ig_fc
        post.save(update_fields=["first_comment", "updated_at"])

    if platform == "linkedin" and not (post.first_comment or "").strip():
        li_fc = compose_first_comment(
            platform="linkedin",
            post=post,
            product=getattr(seed, "product", None) if seed else None,
            profile=profile,
            kova_page_url=kova_page_url,
            commerce_url=commerce_url,
        )
        if li_fc:
            post.first_comment = li_fc
            post.save(update_fields=["first_comment", "updated_at"])


def _queue_bundle_media(post, seed, image_prompt: str, visual_strategy_data: dict | None = None) -> bool:
    """Queue async image/reel generation for a bundle post."""
    from apps.content.models import Post

    product = getattr(seed, "product", None)
    if product and getattr(product, "image", None):
        if post.post_format in (
            Post.PostFormat.CAROUSEL,
            Post.PostFormat.REEL,
            Post.PostFormat.STORY,
        ):
            from apps.content.product_visuals import try_apply_product_polished_media

            if try_apply_product_polished_media(post):
                return True
        if post.post_format == Post.PostFormat.IMAGE:
            try:
                urls = list(product.all_image_urls or [])
                if urls:
                    post.media_urls = [urls[0]]
                    post.media_status = Post.MediaStatus.UPLOADED
                    post.save(update_fields=["media_urls", "media_status", "updated_at"])
                    return True
            except Exception as exc:
                logger.warning("Bundle: product image attach failed for %s: %s", post.pk, exc)

    meta = post.visual_metadata or {}
    source_images = meta.get("source_images") or []
    if post.post_format == Post.PostFormat.REEL and source_images:
        from apps.products.reel_curation import curate_reel_image_urls

        upload_only = product and product.uses_upload_images_only
        curated = curate_reel_image_urls(source_images, upload_only=upload_only)
        meta = dict(meta)
        meta["source_images"] = curated
        if len(curated) >= 2 or upload_only:
            meta["prefer_photoroom_video"] = False
            meta["reel_compose_backend"] = "ffmpeg"
        post.visual_metadata = meta
        post.media_urls = curated
        post.media_status = Post.MediaStatus.UPLOADED
        post.save(update_fields=["visual_metadata", "media_urls", "media_status", "updated_at"])
        from apps.content.tasks import _queue_reel_compose
        _queue_reel_compose(str(post.pk))
        return True

    if not image_prompt and post.post_format not in (Post.PostFormat.CAROUSEL, Post.PostFormat.STORY, Post.PostFormat.REEL):
        return False

    from apps.billing.models import get_user_plan_limits
    from django.utils import timezone as tz

    plan_limits = get_user_plan_limits(seed.user)
    if not plan_limits.get("ai_image_generation", False):
        return False

    monthly_limit = plan_limits.get("ai_images_per_month", 5)
    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    images_this_month = Post.objects.filter(
        user=seed.user,
        media_status="generated",
        created_at__gte=month_start,
    ).count()
    if images_this_month >= monthly_limit:
        post.media_status = Post.MediaStatus.NONE
        post.save(update_fields=["media_status", "updated_at"])
        return False

    post.media_status = Post.MediaStatus.PENDING
    post.media_prompt = image_prompt or post.media_prompt
    post.save(update_fields=["media_status", "media_prompt", "updated_at"])

    try:
        from apps.utils import fire_task
        if post.post_format in (Post.PostFormat.STORY, Post.PostFormat.REEL, Post.PostFormat.CAROUSEL):
            from apps.content.tasks import generate_post_images
            fire_task(generate_post_images, str(post.pk))
        elif image_prompt:
            from apps.content.tasks import async_generate_image
            fire_task(
                async_generate_image,
                str(post.pk),
                image_prompt,
                visual_strategy_data if visual_strategy_data and visual_strategy_data.get("strategy") else None,
            )
        return True
    except Exception as exc:
        logger.warning("Bundle: failed to queue media for %s: %s", post.pk, exc)
        return False


def _create_bundle_post(
    seed,
    user,
    account,
    role: str,
    payload: dict,
    *,
    initial_status: str,
) -> Any:
    from apps.content.models import Post

    platform = payload.get("platform") or account.platform
    visual_meta = dict(payload.get("visual_metadata") or {})
    if payload.get("image_prompt"):
        visual_meta.setdefault("image_prompt", payload["image_prompt"])

    post = Post.objects.create(
        user=user,
        seed=seed,
        product=seed.product if getattr(seed, "product_id", None) else None,
        social_account=account,
        platform=account.platform,
        content_text=payload.get("content_text", ""),
        content_type="original",
        content_intent=payload.get("content_intent", ""),
        post_format=payload.get("post_format", Post.PostFormat.TEXT),
        carousel_slides=payload.get("carousel_slides", []),
        aspect_ratio=payload.get("aspect_ratio", Post.AspectRatio.SQUARE),
        status=initial_status,
        generated_by_agent="create",
        predicted_engagement_score=70.0,
        ai_reasoning="Synthesized to complete campaign bundle spec.",
        ai_angle=payload.get("ai_angle", ""),
        ai_framework="Hook → Value → CTA",
        ai_original_text=payload.get("content_text", ""),
        visual_strategy=payload.get("visual_strategy", "none"),
        visual_metadata=visual_meta,
    )

    dna = dict(post.content_dna or {})
    dna[BUNDLE_ROLE_KEY] = role
    dna["bundle_synthesized"] = True
    post.content_dna = dna
    post.save(update_fields=["content_dna", "updated_at"])

    _apply_post_defaults(post, seed, user, platform)

    image_prompt = payload.get("image_prompt", "")
    visual_strategy_data = {"strategy": payload.get("visual_strategy", "none")}
    _queue_bundle_media(post, seed, image_prompt, visual_strategy_data)

    return post


def ensure_campaign_bundle(
    seed,
    user,
    existing_posts: list,
    *,
    account_map: dict,
    initial_status: str,
    force_pending: bool = False,
) -> list:
    """
    Fill missing campaign bundle slots. Returns newly created Post objects.

    Called at the end of run_create_agent so every activated campaign ships
  the full Growth-equivalent package.
    """
    from apps.content.models import Post

    connected_platforms = set(account_map.keys())
    selected_types = content_types_from_seed(seed)
    audit = audit_campaign_bundle(
        existing_posts, connected_platforms, content_types=selected_types, seed=seed,
    )
    missing = [
        role for role in audit["required"]
        if audit["slots"].get(role, {}).get("status") == "missing"
    ]

    if not missing:
        campaign = getattr(seed, "marketing_campaign", None)
        persist_bundle_audit(
            campaign,
            audit_campaign_bundle(
                existing_posts, connected_platforms, content_types=selected_types, seed=seed,
            ),
        )
        return []

    source = _best_source_post(existing_posts)

    created: list = []

    for role in missing:
        existing_reel = None
        for reel_role in ("ig_reel", "fb_reel", "primary_reel"):
            existing_reel = audit["role_map"].get(reel_role)
            if existing_reel:
                break
        if role == "tiktok_copy" and existing_reel and existing_reel.platform == "tiktok":
            continue

        payload = _synthesize_slot_payload(role, seed, source)
        if not payload:
            continue

        platform = payload.get("platform")
        account = account_map.get(platform)
        if not account:
            logger.info("Bundle: skip %s — no %s account connected", role, platform)
            continue

        post = _create_bundle_post(
            seed, user, account, role, payload, initial_status=initial_status,
        )
        created.append(post)
        logger.info("Bundle: synthesized %s post %s for seed %s", role, post.pk, seed.pk)

    all_posts = list(existing_posts) + created
    final_audit = audit_campaign_bundle(
        all_posts, connected_platforms, content_types=selected_types, seed=seed,
    )
    campaign = getattr(seed, "marketing_campaign", None)
    persist_bundle_audit(campaign, final_audit)

    if created:
        filled = ", ".join(
            BUNDLE_LABELS.get(r, r) for r in missing if r in final_audit["role_map"]
        )
        from apps.agents.create_agent import log_gen_step
        log_gen_step(
            seed, "bundle",
            f"Campaign package completed — added {len(created)} deliverable{'s' if len(created) != 1 else ''}.",
            filled or "Reel, carousel, stories, and platform posts.",
        )

    return created


def campaign_bundle_prompt_section(connected_platforms: set[str] | list[str]) -> str:
    """Optional LLM hint — structural gaps are still filled post-generation."""
    platforms = {p.lower() for p in connected_platforms}
    lines = [
        "### CAMPAIGN BUNDLE (deliver the full package)",
        "This seed activates a **marketing campaign**, not a single post. When possible, include:",
    ]
    if "instagram" in platforms:
        lines.append("- Instagram: feed image post AND/OR carousel (5–6 slides) AND story frames AND reel")
    if "facebook" in platforms:
        lines.append("- Facebook: feed post (text or image) AND vertical reel (post_format=reel)")
    if "linkedin" in platforms:
        lines.append("- LinkedIn: thought-leadership text post")
    if "tiktok" in platforms:
        lines.append("- TikTok: vertical reel (post_format=reel)")
    lines.append(
        "Use distinct angles per deliverable. Carousel slides must follow funnel structure: "
        "hook → problem → solution → proof → offer → CTA."
    )
    return "\n".join(lines)
