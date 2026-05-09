"""
Map UserProfile.industry (20 fine-grained choices) to the six canonical
industry buckets used by the holiday relevance system.

The canonical six are:
    retail | f_and_b | services | b2b | creative | health

These are the same buckets used in industry_holiday_boosts.yaml. Adding a
new UserProfile.industry choice? Add it to the map below.
"""
from __future__ import annotations

CANONICAL_INDUSTRIES = ("retail", "f_and_b", "services", "b2b", "creative", "health")

# Map from UserProfile.Industry value -> canonical bucket
PROFILE_TO_CANONICAL: dict[str, str] = {
    # Retail family
    "ecommerce": "retail",
    "wholesale_retail": "retail",
    "fashion_beauty": "retail",
    # Food & beverage
    "food_restaurant": "f_and_b",
    # Services (broad bucket — anything client-facing professional)
    "consulting": "services",
    "real_estate": "services",
    "finance": "services",
    "legal": "services",
    "travel_tourism": "services",
    "agriculture": "services",
    "logistics_transport": "services",
    "construction": "services",
    "education": "services",
    "nonprofit": "services",
    # B2B / software
    "saas": "b2b",
    "agency": "b2b",
    # Creative / media
    "creator": "creative",
    "media_entertainment": "creative",
    # Health / wellness
    "health": "health",
    # Fallback for "other" or anything unmapped
    "other": "services",
    "": "services",
}


def canonical_industry_for(profile_industry: str | None) -> str:
    """Return the canonical industry bucket for a UserProfile.industry value.
    Falls back to 'services' for unknown values (safe broad default)."""
    if not profile_industry:
        return "services"
    return PROFILE_TO_CANONICAL.get(profile_industry, "services")
