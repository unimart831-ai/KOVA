"""Brand preview card for express onboarding Step 2."""

from __future__ import annotations

from apps.accounts.setup_mission import is_commerce_industry


def build_brand_preview(profile, user=None) -> dict:
    user = user or profile.user
    tones = list(profile.tone_attributes or [])[:5]
    pillars = list(profile.content_pillars or [])[:4]
    goals = list(profile.goals or [])[:3]

    voice = (profile.brand_voice or "").strip()
    audience = (profile.target_audience or "").strip()

    cta_label = profile.default_cta_type or "whatsapp"
    cta_display = {
        "whatsapp": "WhatsApp",
        "phone": "Phone call",
        "link": "Website link",
        "email": "Email",
        "dm": "Direct message",
    }.get(cta_label, cta_label.replace("_", " ").title())

    return {
        "company_name": profile.company_name or user.full_name or "Your business",
        "industry_label": profile.get_industry_display() if profile.industry else "",
        "is_commerce": is_commerce_industry(profile.industry),
        "brand_voice": voice,
        "brand_voice_preview": _truncate(voice, 220),
        "target_audience": audience,
        "target_audience_preview": _truncate(audience, 180),
        "tones": tones,
        "pillars": pillars,
        "goals": goals,
        "posting_frequency": profile.posting_frequency or 4,
        "cta_display": cta_display,
        "website_url": profile.website_url or "",
        "has_rich_profile": bool(voice or audience or tones or pillars),
    }


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
