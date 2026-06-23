"""Conversational onboarding — business type + goal chips, minimal fields."""

from __future__ import annotations

from typing import Any

from apps.accounts.onboarding_express import (
    BUSINESS_MODEL_PRODUCT,
    BUSINESS_MODEL_PROFESSIONAL,
    BUSINESS_MODEL_SERVICE,
    record_intent,
)

# Visual chips shown on the hire-Kova screen (maps to industry + business_model).
BUSINESS_TYPE_PRESETS: list[dict[str, Any]] = [
    {
        "id": "salon",
        "label": "Salon / Barber",
        "emoji": "💈",
        "industry": "salon_beauty",
        "business_model": BUSINESS_MODEL_SERVICE,
    },
    {
        "id": "restaurant",
        "label": "Restaurant / Café",
        "emoji": "🍽️",
        "industry": "food_restaurant",
        "business_model": BUSINESS_MODEL_PRODUCT,
    },
    {
        "id": "boutique",
        "label": "Boutique / Retail",
        "emoji": "👗",
        "industry": "fashion_beauty",
        "business_model": BUSINESS_MODEL_PRODUCT,
    },
    {
        "id": "electronics",
        "label": "Electronics store",
        "emoji": "📱",
        "industry": "wholesale_retail",
        "business_model": BUSINESS_MODEL_PRODUCT,
    },
    {
        "id": "agency",
        "label": "Agency",
        "emoji": "🎯",
        "industry": "agency",
        "business_model": BUSINESS_MODEL_PROFESSIONAL,
    },
    {
        "id": "consultant",
        "label": "Consultant",
        "emoji": "💼",
        "industry": "consulting",
        "business_model": BUSINESS_MODEL_PROFESSIONAL,
    },
    {
        "id": "health",
        "label": "Health / Wellness",
        "emoji": "🩺",
        "industry": "health",
        "business_model": BUSINESS_MODEL_SERVICE,
    },
    {
        "id": "other",
        "label": "Something else",
        "emoji": "✨",
        "industry": "",
        "business_model": "",
    },
]

GOAL_OPTIONS: list[dict[str, Any]] = [
    {
        "id": "sales",
        "label": "More sales",
        "intent": "sell",
        "goals": ["drive_sales", "generate_leads"],
    },
    {
        "id": "bookings",
        "label": "More bookings",
        "intent": "sell",
        "goals": ["book_appointments", "generate_leads"],
    },
    {
        "id": "leads",
        "label": "More leads",
        "intent": "sell",
        "goals": ["generate_leads"],
    },
    {
        "id": "customers",
        "label": "More customers",
        "intent": "both",
        "goals": ["generate_leads", "grow_followers"],
    },
    {
        "id": "awareness",
        "label": "More awareness",
        "intent": "grow",
        "goals": ["brand_awareness", "grow_followers"],
    },
]

_PRESET_BY_ID = {p["id"]: p for p in BUSINESS_TYPE_PRESETS}
_GOAL_BY_ID = {g["id"]: g for g in GOAL_OPTIONS}


def get_business_type_preset(type_id: str) -> dict[str, Any] | None:
    return _PRESET_BY_ID.get((type_id or "").strip())


def get_goal_option(goal_id: str) -> dict[str, Any] | None:
    return _GOAL_BY_ID.get((goal_id or "").strip())


def apply_business_type(
    profile,
    preset: dict[str, Any],
    *,
    company_name: str = "",
    industry: str = "",
    industry_other: str = "",
) -> None:
    """Persist business type chip selection onto profile."""
    from apps.accounts.industry_packs import apply_pack

    chosen_industry = industry or preset.get("industry") or ""
    if chosen_industry:
        profile.industry = chosen_industry
    if industry_other:
        profile.industry_other = industry_other.strip()[:100]
    if company_name:
        profile.company_name = company_name.strip()[:255]

    business_model = preset.get("business_model") or ""
    if business_model:
        profile.business_model = business_model

    profile.save()
    if profile.industry:
        apply_pack(profile, profile.industry)


def apply_goal_choice(profile, goal_id: str) -> None:
    """Map a goal chip to profile goals + recorded intent."""
    option = get_goal_option(goal_id)
    if not option:
        return
    profile.goals = option["goals"]
    profile.save(update_fields=["goals"])
    record_intent(profile, option["intent"])
