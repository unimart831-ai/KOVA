"""Industry-aware default packs for onboarding.

When a user picks an industry during Step 1, we can pre-populate sensible
defaults for the rest of the wizard (tone, pillars, goals, posting frequency,
CTA type) so the SME owner is not staring at empty fields. They can always
override any value during Step 2 or Step 3.

Each pack is keyed by `UserProfile.Industry.value`. Unknown / missing industries
fall back to `_DEFAULT_PACK`.

Field meanings:
    tone_attributes: list[str]
        Subset of the 12 tone choices from OnboardingStep2ReviewForm.TONE_CHOICES.
    content_pillars: list[str]
        Topic themes the Create agent uses as content axes.
    goals: list[str]
        Subset of the 7 goal choices from OnboardingStep2ReviewForm.GOAL_CHOICES.
    posting_frequency: int
        Target posts per week. Restaurants > consultants > legal services.
    default_cta_type: str
        Maps to UserProfile.default_cta_type. Channel SMEs in that industry
        typically convert on (whatsapp for service businesses, link for retail).
    visual_style: str
        Hint passed to the image-generation prompts (FLUX.1 etc.).

Apply with `apply_pack(profile, industry)` — only fills fields that are
currently empty / default, never overwrites user-entered data.
"""
from __future__ import annotations

from typing import Any


_DEFAULT_PACK: dict[str, Any] = {
    "tone_attributes": ["professional", "approachable", "confident"],
    "content_pillars": [
        "Behind the scenes",
        "Customer stories",
        "Tips & how-tos",
        "Product or service spotlights",
    ],
    "goals": ["brand_awareness", "generate_leads"],
    "posting_frequency": 4,
    "default_cta_type": "whatsapp",
    "visual_style": "clean",
}


PACKS: dict[str, dict[str, Any]] = {
    # ── Service businesses (high WhatsApp conversion) ────────────────
    "salon_beauty": {
        "tone_attributes": ["warm", "approachable", "playful", "confident"],
        "content_pillars": [
            "Transformations & before/after",
            "Service spotlights",
            "Beauty tips & care advice",
            "Behind the scenes / team",
            "Client love & testimonials",
        ],
        "goals": ["grow_followers", "generate_leads", "build_community"],
        "posting_frequency": 5,
        "default_cta_type": "whatsapp",
        "visual_style": "photography",
    },
    "food_restaurant": {
        "tone_attributes": ["warm", "playful", "approachable"],
        "content_pillars": [
            "Menu highlights & daily specials",
            "Behind the kitchen",
            "Customer love",
            "Local ingredients & sourcing",
            "Events & weekend specials",
        ],
        "goals": ["drive_traffic", "generate_leads", "build_community"],
        "posting_frequency": 6,
        "default_cta_type": "phone",
        "visual_style": "photography",
    },
    "health": {
        "tone_attributes": ["empathetic", "professional", "educational"],
        "content_pillars": [
            "Health tips & prevention",
            "Patient stories (with consent)",
            "Service explainers",
            "Team & facility tours",
            "Myth-busting common misconceptions",
        ],
        "goals": ["brand_awareness", "generate_leads", "thought_leadership"],
        "posting_frequency": 3,
        "default_cta_type": "whatsapp",
        "visual_style": "corporate",
    },
    "fashion_beauty": {
        "tone_attributes": ["bold", "playful", "confident"],
        "content_pillars": [
            "New arrivals & lookbooks",
            "Styling tips",
            "Customer fits & UGC",
            "Behind the brand",
            "Sales & limited drops",
        ],
        "goals": ["grow_followers", "drive_traffic", "generate_leads"],
        "posting_frequency": 5,
        "default_cta_type": "link",
        "visual_style": "vibrant",
    },

    # ── Retail / commerce ────────────────────────────────────────────
    "ecommerce": {
        "tone_attributes": ["approachable", "bold", "professional"],
        "content_pillars": [
            "Product launches",
            "Customer reviews & UGC",
            "Use-case demos",
            "Behind the brand",
            "Deals, drops, and bundles",
        ],
        "goals": ["drive_traffic", "generate_leads", "grow_followers"],
        "posting_frequency": 5,
        "default_cta_type": "link",
        "visual_style": "corporate",
    },
    "wholesale_retail": {
        "tone_attributes": ["approachable", "confident", "bold"],
        "content_pillars": [
            "Product highlights",
            "Customer testimonials",
            "Promotions & specials",
            "Behind the shop",
            "Tips for buyers",
        ],
        "goals": ["drive_traffic", "generate_leads", "brand_awareness"],
        "posting_frequency": 4,
        "default_cta_type": "whatsapp",
        "visual_style": "corporate",
    },

    # ── Professional services ────────────────────────────────────────
    "consulting": {
        "tone_attributes": ["authoritative", "professional", "educational"],
        "content_pillars": [
            "Case studies & client wins",
            "Frameworks & how-tos",
            "Industry insights",
            "Common mistakes & fixes",
            "Behind the practice",
        ],
        "goals": ["thought_leadership", "generate_leads", "brand_awareness"],
        "posting_frequency": 3,
        "default_cta_type": "link",
        "visual_style": "flat_design",
    },
    "agency": {
        "tone_attributes": ["confident", "witty", "professional"],
        "content_pillars": [
            "Client work & case studies",
            "Process & methodology",
            "Industry hot takes",
            "Team culture",
            "Trends & analysis",
        ],
        "goals": ["thought_leadership", "generate_leads", "brand_awareness"],
        "posting_frequency": 4,
        "default_cta_type": "link",
        "visual_style": "flat_design",
    },
    "legal": {
        "tone_attributes": ["authoritative", "professional", "empathetic"],
        "content_pillars": [
            "Know your rights",
            "Common legal mistakes to avoid",
            "Case explainers (anonymized)",
            "Practice updates",
            "Q&A from clients",
        ],
        "goals": ["thought_leadership", "brand_awareness", "generate_leads"],
        "posting_frequency": 2,
        "default_cta_type": "phone",
        "visual_style": "flat_design",
    },
    "finance": {
        "tone_attributes": ["authoritative", "educational", "approachable"],
        "content_pillars": [
            "Money tips for SMEs",
            "Common financial mistakes",
            "Product / service explainers",
            "Client success stories",
            "Market updates",
        ],
        "goals": ["thought_leadership", "generate_leads", "brand_awareness"],
        "posting_frequency": 3,
        "default_cta_type": "whatsapp",
        "visual_style": "corporate",
    },
    "real_estate": {
        "tone_attributes": ["confident", "approachable", "professional"],
        "content_pillars": [
            "New listings",
            "Neighborhood spotlights",
            "Buying & renting tips",
            "Client testimonials",
            "Market trends",
        ],
        "goals": ["generate_leads", "drive_traffic", "brand_awareness"],
        "posting_frequency": 4,
        "default_cta_type": "whatsapp",
        "visual_style": "corporate",
    },

    # ── Knowledge & creative ─────────────────────────────────────────
    "saas": {
        "tone_attributes": ["confident", "witty", "educational"],
        "content_pillars": [
            "Product updates & ship logs",
            "User wins & case studies",
            "Industry insights",
            "How-tos & tips",
            "Behind the build",
        ],
        "goals": ["thought_leadership", "generate_leads", "drive_traffic"],
        "posting_frequency": 4,
        "default_cta_type": "link",
        "visual_style": "flat_design",
    },
    "creator": {
        "tone_attributes": ["playful", "bold", "approachable"],
        "content_pillars": [
            "Day in the life",
            "Behind the scenes",
            "Lessons & frameworks",
            "Q&A and storytelling",
            "Collabs & community",
        ],
        "goals": ["grow_followers", "build_community", "thought_leadership"],
        "posting_frequency": 5,
        "default_cta_type": "link",
        "visual_style": "vibrant",
    },
    "education": {
        "tone_attributes": ["educational", "empathetic", "inspirational"],
        "content_pillars": [
            "Student success stories",
            "Course / programme highlights",
            "Study tips & resources",
            "Faculty & team",
            "Application & enrolment info",
        ],
        "goals": ["generate_leads", "brand_awareness", "build_community"],
        "posting_frequency": 4,
        "default_cta_type": "link",
        "visual_style": "corporate",
    },
    "media_entertainment": {
        "tone_attributes": ["playful", "bold", "witty"],
        "content_pillars": [
            "New releases & previews",
            "Behind the scenes",
            "Fan / audience spotlights",
            "Cultural moments",
            "Cast / talent features",
        ],
        "goals": ["grow_followers", "build_community", "drive_traffic"],
        "posting_frequency": 6,
        "default_cta_type": "link",
        "visual_style": "vibrant",
    },

    # ── Industrial / operations ──────────────────────────────────────
    "agriculture": {
        "tone_attributes": ["approachable", "educational", "confident"],
        "content_pillars": [
            "Farm & field updates",
            "Crop / livestock tips",
            "Buyer & market info",
            "Behind the farm",
            "Seasonal advice",
        ],
        "goals": ["generate_leads", "brand_awareness", "build_community"],
        "posting_frequency": 3,
        "default_cta_type": "whatsapp",
        "visual_style": "photography",
    },
    "logistics_transport": {
        "tone_attributes": ["professional", "confident", "approachable"],
        "content_pillars": [
            "Service & coverage areas",
            "Customer wins",
            "Behind the fleet",
            "Logistics tips for SMEs",
            "Tracking & technology",
        ],
        "goals": ["generate_leads", "brand_awareness", "customer_support"],
        "posting_frequency": 3,
        "default_cta_type": "whatsapp",
        "visual_style": "corporate",
    },
    "construction": {
        "tone_attributes": ["confident", "professional", "approachable"],
        "content_pillars": [
            "Project showcases",
            "Process & craftsmanship",
            "Client testimonials",
            "Safety & quality",
            "Team spotlights",
        ],
        "goals": ["generate_leads", "brand_awareness", "thought_leadership"],
        "posting_frequency": 3,
        "default_cta_type": "phone",
        "visual_style": "corporate",
    },
    "travel_tourism": {
        "tone_attributes": ["inspirational", "playful", "warm"],
        "content_pillars": [
            "Destinations & itineraries",
            "Guest stories",
            "Travel tips & packing",
            "Behind the experience",
            "Seasonal offers",
        ],
        "goals": ["generate_leads", "drive_traffic", "grow_followers"],
        "posting_frequency": 5,
        "default_cta_type": "whatsapp",
        "visual_style": "vibrant",
    },

    # ── Mission-driven ───────────────────────────────────────────────
    "nonprofit": {
        "tone_attributes": ["empathetic", "inspirational", "educational"],
        "content_pillars": [
            "Impact stories",
            "Programme updates",
            "Volunteer / donor spotlights",
            "Cause education",
            "Calls to action",
        ],
        "goals": ["brand_awareness", "build_community", "generate_leads"],
        "posting_frequency": 3,
        "default_cta_type": "link",
        "visual_style": "photography",
    },
}


# Replace warm/bold/etc. that aren't in the 12-tone vocabulary with valid ones.
# The OnboardingStep2ReviewForm vocabulary is:
# confident, approachable, witty, professional, casual, bold, educational,
# inspirational, empathetic, authoritative, playful, minimalist.
# "warm" is not in that list — fold to "empathetic" or "approachable".
_TONE_ALIASES = {"warm": "empathetic"}


def _normalize_tones(tones: list[str]) -> list[str]:
    valid = {
        "confident", "approachable", "witty", "professional", "casual",
        "bold", "educational", "inspirational", "empathetic",
        "authoritative", "playful", "minimalist",
    }
    out: list[str] = []
    for t in tones:
        t = _TONE_ALIASES.get(t, t)
        if t in valid and t not in out:
            out.append(t)
    return out


def get_pack(industry: str | None) -> dict[str, Any]:
    """Return the starter pack for `industry`, falling back to defaults."""
    if not industry:
        return dict(_DEFAULT_PACK, tone_attributes=_normalize_tones(_DEFAULT_PACK["tone_attributes"]))
    pack = PACKS.get(industry, _DEFAULT_PACK)
    return dict(pack, tone_attributes=_normalize_tones(pack["tone_attributes"]))


def apply_pack(profile, industry: str | None) -> list[str]:
    """Fill empty profile fields from the industry pack.

    Returns the list of fields that were populated, so the view layer can tell
    the user which defaults were applied. Never overwrites user-supplied data.
    """
    pack = get_pack(industry)
    applied: list[str] = []

    if not profile.tone_attributes:
        profile.tone_attributes = pack["tone_attributes"]
        applied.append("tone_attributes")
    if not profile.content_pillars:
        profile.content_pillars = pack["content_pillars"]
        applied.append("content_pillars")
    if not profile.goals:
        profile.goals = pack["goals"]
        applied.append("goals")
    # posting_frequency has a non-zero model default (5); only apply if it
    # matches the model default — meaning the user hasn't touched it.
    if profile.posting_frequency in (None, 5):
        profile.posting_frequency = pack["posting_frequency"]
        applied.append("posting_frequency")
    # default_cta_type's model default is "none" (a non-empty string), and
    # visual_style's default is "auto". Treat both as "unset" for pack purposes.
    if not profile.default_cta_type or profile.default_cta_type == "none":
        profile.default_cta_type = pack["default_cta_type"]
        applied.append("default_cta_type")
    if not profile.visual_style or profile.visual_style == "auto":
        profile.visual_style = pack["visual_style"]
        applied.append("visual_style")

    if applied:
        profile.save(update_fields=applied)
        # Funnel marker — counted in admin dashboard adoption metrics.
        # `record_onboarding_step` is no-op on duplicate so it's safe to call
        # every time apply_pack runs (Magic Fill can call it a second time).
        try:
            profile.record_onboarding_step(f"industry_pack_applied:{industry or 'default'}")
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to record industry_pack_applied for %s", profile.user.email
            )
    return applied
