"""
AI-powered suggestion engine — produces a concrete value for one missing
or thin profile field, in the user's brand voice.

Public entry point: `generate_suggestion(audit, field_name)`.

Some fields don't need an LLM at all (phone, email, website pulled
straight from UserProfile). Others (bio, description, page button copy)
do — those get a Claude call with brand-voice context.
"""
from __future__ import annotations

import logging
from typing import Optional

from apps.agents.llm import generate as llm_generate, parse_llm_json

logger = logging.getLogger(__name__)


# Per-platform character ceilings used in prompts + validation.
PLATFORM_CHAR_LIMITS = {
    "facebook": {"about": 255, "description": 1500, "phone": 30, "website": 200},
    "instagram": {"biography": 150, "name": 30, "website": 200},
    "linkedin": {"description": 2000, "specialties": 256, "website": 200, "headline": 220},
}


# Static-field generators: pull directly from UserProfile or related models —
# no LLM call needed.
def _from_user_profile(audit, field_name: str) -> Optional[str]:
    """Return a value sourced directly from the user's profile, or None
    if no source is available."""
    user = audit.user
    profile = getattr(user, "profile", None)
    if not profile:
        return None

    # Cross-platform field name mapping → UserProfile attribute
    mapping = {
        # Phone / email / website are user-supplied at signup or settings
        "phone": getattr(profile, "cta_phone", "") or getattr(user, "phone_number", ""),
        "emails": getattr(profile, "cta_email", "") or user.email,
        "website": getattr(profile, "website_url", ""),
        # LinkedIn org website uses same field
        "single_line_address": (
            f"{getattr(profile, 'city', '')}, {getattr(profile, 'country', '')}"
            if getattr(profile, "city", "") and getattr(profile, "country", "")
            else ""
        ),
    }
    val = (mapping.get(field_name) or "").strip()
    return val or None


def _category_for_industry(industry: str, platform: str) -> Optional[str]:
    """Map UserProfile.industry slug → platform-specific category enum.
    Returns None if the platform doesn't expose a category, or no good map."""
    # FB Page categories are free-form but recognize these common strings.
    # See https://developers.facebook.com/docs/pages/categories
    if platform == "facebook":
        return {
            "food_restaurant": "Restaurant",
            "wholesale_retail": "Retail Company",
            "fashion_beauty": "Clothing Store",
            "ecommerce": "E-commerce Website",
            "consulting": "Consulting Agency",
            "saas": "Software Company",
            "agency": "Marketing Agency",
            "creator": "Content Creator",
            "real_estate": "Real Estate Service",
            "finance": "Financial Service",
            "legal": "Legal Service",
            "education": "Education",
            "health": "Health & Wellness",
            "travel_tourism": "Travel Company",
            "agriculture": "Agriculture",
            "logistics_transport": "Cargo & Freight Company",
            "construction": "Construction Company",
            "nonprofit": "Non-Governmental Organization (NGO)",
            "media_entertainment": "Media",
        }.get(industry)
    return None


def generate_suggestion(audit, field_name: str) -> Optional[dict]:
    """Generate a suggestion dict for one missing/thin field.

    Returns None if we genuinely can't suggest anything for this field
    (e.g., 'hours' — we won't fabricate operating hours).

    Returns {"value": str, "reasoning": str} on success.
    """
    user = audit.user
    profile = getattr(user, "profile", None)
    platform = audit.social_account.platform

    # ── Static fields: pull from UserProfile ──────────────────────────
    static = _from_user_profile(audit, field_name)
    if static:
        return {
            "value": static[:_limit_for(platform, field_name)],
            "reasoning": "Pulled from your Kova profile.",
        }

    # ── Category: rule-based mapping ──────────────────────────────────
    if field_name == "category":
        industry = (getattr(profile, "industry", "") or "").strip()
        cat = _category_for_industry(industry, platform)
        if cat:
            return {
                "value": cat,
                "reasoning": f"Best match for your industry ({industry}).",
            }
        return None  # don't guess without a mapping

    # ── No-fabrication fields: never invent these ─────────────────────
    if field_name in ("hours", "cover", "picture", "profile_picture_url",
                      "logoV2", "vanityName", "industries", "primaryOrganizationType",
                      "username", "locale", "email_verified"):
        return None

    # ── LLM-generated fields: bio, description, about, headline, etc.
    return _generate_with_llm(audit, field_name)


def _limit_for(platform: str, field_name: str) -> int:
    return PLATFORM_CHAR_LIMITS.get(platform, {}).get(field_name, 1000)


def _generate_with_llm(audit, field_name: str) -> Optional[dict]:
    user = audit.user
    profile = getattr(user, "profile", None)
    platform = audit.social_account.platform
    char_limit = _limit_for(platform, field_name)

    business_name = (getattr(profile, "company_name", "") or "").strip() or user.full_name or "your business"
    brand_voice = (getattr(profile, "brand_voice", "") or "").strip()
    industry = (getattr(profile, "industry", "") or "").strip()
    city = (getattr(profile, "city", "") or "").strip()
    country = (getattr(profile, "country", "") or "").strip()
    audience = (getattr(profile, "target_audience", "") or "").strip()

    # Products — top 3 names
    products_summary = ""
    try:
        product_names = list(
            user.products.filter(is_active=True)
            .values_list("name", flat=True)[:3]
        )
        if product_names:
            products_summary = ", ".join(product_names)
    except Exception:
        pass

    if not brand_voice and not products_summary:
        # Insufficient context — don't generate generic AI slop.
        return None

    field_label = field_name.replace("_", " ").title()

    system_prompt = (
        f"You are Kova's profile completion agent. Generate one concise "
        f"{field_label} for a {platform} profile, in the user's brand voice.\n\n"
        "HARD RULES:\n"
        f"- Stay under {char_limit} characters (HARD LIMIT — count carefully).\n"
        "- Be specific to the business — name the product/service or angle.\n"
        "- No generic phrases ('passionate about', 'one-stop shop', "
        "'we strive to', 'on this special day').\n"
        "- No invented stats, awards, customer counts, or testimonials.\n"
        "- No emoji unless the platform conventionally uses them "
        f"({'yes' if platform == 'instagram' else 'no'} for {platform}).\n"
        "- Return JSON with two keys: 'value' (the text), 'reasoning' "
        "(one short sentence explaining the angle).\n"
    )

    user_prompt = (
        f"Business: {business_name}\n"
        f"Industry: {industry or '(unspecified)'}\n"
        f"Location: {(city + ', ' + country).strip(', ') or '(unspecified)'}\n"
        f"Brand voice: {brand_voice or '(no explicit voice set — keep it warm and specific)'}\n"
        f"Target audience: {audience or '(not specified)'}\n"
        f"Main products / services: {products_summary or '(not provided)'}\n\n"
        f"Field: {field_name}\n"
        f"Platform: {platform}\n"
        f"Character limit: {char_limit}\n\n"
        "Generate the field value. Return JSON only."
    )

    try:
        response = llm_generate(
            prompt=user_prompt,
            system=system_prompt,
            json_mode=True,
            max_tokens=600,
            temperature=0.7,
            user=user,
        )
    except Exception as exc:
        logger.warning("LLM call for profile field %s failed: %s", field_name, exc)
        return None

    if not response.content or not response.content.strip():
        return None

    try:
        data = parse_llm_json(response.content)
    except Exception as exc:
        logger.warning("LLM response not parseable JSON for field %s: %s", field_name, exc)
        return None

    value = (data.get("value") or "").strip()
    if not value:
        return None
    if len(value) > char_limit:
        # Soft trim — defensive against LLM ignoring the cap
        value = value[: char_limit - 1].rstrip() + "…"
    reasoning = (data.get("reasoning") or "").strip()[:300]
    return {"value": value, "reasoning": reasoning or "AI-generated to match your brand voice."}
