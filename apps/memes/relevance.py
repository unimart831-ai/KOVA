"""
MSME-focused meme relevance — industry fit, city context, fit copy for cards.
"""

from __future__ import annotations

from apps.memes.models import MemePreferences, TrendingMeme

# Categories boosted per industry (MSME-focused)
INDUSTRY_CATEGORY_BOOST: dict[str, dict[str, int]] = {
    "wholesale_retail": {"business": 18, "social": 15, "food": 10, "general": 12},
    "food_restaurant": {"food": 22, "social": 15, "business": 10, "general": 8},
    "salon_beauty": {"social": 20, "entertainment": 12, "business": 10, "general": 10},
    "fashion_beauty": {"social": 18, "entertainment": 15, "music": 10},
    "health": {"education": 15, "social": 12, "business": 10, "general": 8},
    "finance": {"business": 20, "education": 12, "social": 8},
    "real_estate": {"business": 18, "social": 12, "general": 10},
    "agriculture": {"business": 15, "food": 12, "social": 10, "general": 10},
    "logistics_transport": {"social": 18, "business": 12, "general": 10},
    "construction": {"business": 15, "social": 12, "general": 10},
    "education": {"education": 20, "social": 12, "general": 8},
    "consulting": {"business": 18, "education": 12, "authority": 10},
    "creator": {"entertainment": 18, "music": 15, "social": 15},
    "ecommerce": {"business": 15, "social": 15, "tech": 10},
    "travel_tourism": {"social": 18, "food": 12, "entertainment": 10},
}

DEFAULT_EXCLUDED_CATEGORIES = ["political"]

# Recurring MSME life moments (injected into discovery + event context)
MSME_MOMENTS = [
    {
        "name": "Salary Day / Mwezi iko corner",
        "tags": ["payday", "salary", "hustle", "broke"],
        "meme_angles": ["January broke", "Waiting for salary", "M-Pesa notification joy"],
    },
    {
        "name": "School Fees Season",
        "tags": ["school_fees", "parents", "term"],
        "meme_angles": ["Back to school shopping", "Parent wallet pain", "Term two pressure"],
    },
    {
        "name": "Long Rains / Traffic",
        "tags": ["rain", "traffic", "nairobi", "floods"],
        "meme_angles": ["Matatu in rain", "Flooded roads", "Umbrella economics"],
    },
    {
        "name": "Waiting for Payment",
        "tags": ["invoice", "b2b", "payment", "hustle"],
        "meme_angles": ["Client said 'next week'", "Checking M-Pesa again", "Small business cash flow"],
    },
    {
        "name": "Customer Story Hour",
        "tags": ["retail", "customer", "shop"],
        "meme_angles": ["That one regular customer", "Price negotiation Olympics", "Closed but customer knocking"],
    },
]

CATEGORY_FIT_COPY = {
    "business": "relatable hustle / business humor",
    "food": "food & hospitality vibes",
    "social": "everyday relatable content",
    "entertainment": "fun, shareable entertainment angle",
    "education": "helpful, educational spin",
    "general": "broad audience appeal",
    "sports": "sports fan engagement",
    "tech": "tech-savvy audience",
    "music": "music & culture crowd",
}


def get_meme_prefs(user):
    """Get or create prefs with MSME-safe defaults."""
    prefs, created = MemePreferences.objects.get_or_create(user=user)
    updated = False
    if not prefs.excluded_categories:
        prefs.excluded_categories = list(DEFAULT_EXCLUDED_CATEGORIES)
        updated = True
    if updated:
        prefs.save(update_fields=["excluded_categories"])
    return prefs


def score_meme_for_user(meme: TrendingMeme, profile, prefs: MemePreferences | None = None) -> int:
    """Personalized relevance score for ranking the discover feed."""
    score = meme.overall_score

    industry = (profile.industry or "other").lower()
    for cat, boost in INDUSTRY_CATEGORY_BOOST.get(industry, {}).items():
        if meme.category == cat:
            score += boost

    if prefs:
        if prefs.preferred_categories and meme.category in prefs.preferred_categories:
            score += 12
        if prefs.excluded_categories and meme.category in prefs.excluded_categories:
            score -= 80
        if prefs.preferred_humor_types and meme.humor_type in prefs.preferred_humor_types:
            score += 8

    city = (getattr(profile, "city", None) or "").strip().lower()
    if city and meme.tags:
        tag_blob = " ".join(str(t).lower() for t in meme.tags)
        if city in tag_blob:
            score += 10
        elif "nairobi" in city and "nairobi" in tag_blob:
            score += 8

    demographics = meme.target_demographics or []
    audience = (profile.target_audience or "").lower()
    if audience:
        for demo in demographics:
            if str(demo).lower() in audience:
                score += 6

    return score


def meme_fit_line(meme: TrendingMeme, profile) -> str:
    """Plain-language reason this meme fits the user's business."""
    company = profile.company_name or "your business"
    industry_label = (
        profile.industry_other
        if profile.industry == "other" and profile.industry_other
        else (profile.get_industry_display() if profile.industry else "small business")
    )
    city = getattr(profile, "city", None) or ""
    angle = CATEGORY_FIT_COPY.get(meme.category, "on-brand humor")

    parts = [f"Good for {company} ({industry_label}) — {angle}"]
    if city and meme.tags:
        tag_blob = " ".join(str(t).lower() for t in meme.tags)
        if city.lower() in tag_blob or "kenya" in tag_blob:
            parts.append(f"local {city} vibe")
    if meme.brand_safety_score >= 75:
        parts.append("brand-safe")
    elif meme.brand_safety_score < 50:
        parts.append("edgy — review carefully")
    return ". ".join(parts[:2]) + "."


def rank_memes_for_user(memes, profile, prefs=None, topic_hint: str = ""):
    """Return list of {meme, score, fit_line} sorted by personalized score."""
    hint = (topic_hint or "").lower()
    ranked = []
    for meme in memes:
        score = score_meme_for_user(meme, profile, prefs)
        if hint:
            blob = f"{meme.title} {meme.description} {' '.join(meme.tags or [])}".lower()
            if hint in blob or any(word in blob for word in hint.split() if len(word) > 3):
                score += 25
        ranked.append({
            "meme": meme,
            "score": score,
            "fit_line": meme_fit_line(meme, profile),
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


def industry_relevance_for_trend(meme: TrendingMeme, profile) -> int:
    """Score 0-100 for Trend Alert matching."""
    base = meme.cultural_relevance_score
    industry = (profile.industry or "other").lower()
    boosts = INDUSTRY_CATEGORY_BOOST.get(industry, {})
    base += boosts.get(meme.category, 0)
    return min(100, max(0, base))


def msme_moments_context() -> str:
    """Text block for discovery LLM prompt."""
    lines = ["=== MSME LIFE MOMENTS (always relatable for Kenyan small business) ==="]
    for moment in MSME_MOMENTS:
        lines.append(
            f"- {moment['name']}: tags {moment['tags']}; angles: {', '.join(moment['meme_angles'][:3])}"
        )
    return "\n".join(lines)
