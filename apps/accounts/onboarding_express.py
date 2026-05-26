"""Express onboarding helpers — minimal input, confirm-not-fill flow."""

from __future__ import annotations

INTENT_SELL = "sell"
INTENT_GROW = "grow"
INTENT_BOTH = "both"
VALID_INTENTS = frozenset({INTENT_SELL, INTENT_GROW, INTENT_BOTH})


def record_intent(profile, intent: str) -> None:
    if intent not in VALID_INTENTS:
        return
    profile.record_onboarding_step(f"intent_{intent}")


def ensure_brand_defaults(profile, user) -> None:
    """Apply industry pack and safe defaults so preview → finish works without Step 2 edits."""
    from apps.accounts.industry_packs import apply_pack

    if profile.industry:
        apply_pack(profile, profile.industry)

    if not (profile.brand_voice or "").strip() and profile.industry:
        pack_voice = _default_voice_line(profile)
        if pack_voice:
            profile.brand_voice = pack_voice

    if not (profile.target_audience or "").strip() and profile.industry:
        profile.target_audience = (
            f"Customers and followers interested in {profile.get_industry_display().lower()} "
            f"— especially on Instagram, Facebook, and WhatsApp."
        )

    if not profile.goals:
        profile.goals = ["brand_awareness", "generate_leads"]

    if not profile.posting_frequency:
        profile.posting_frequency = 4

    if not profile.default_cta_type:
        profile.default_cta_type = "whatsapp"

    if not user.timezone:
        user.timezone = "Africa/Nairobi"

    if not profile.content_language:
        profile.content_language = "en"

    profile.save()
    user.save(update_fields=["timezone"])


def _default_voice_line(profile) -> str:
    name = profile.company_name or "We"
    industry = profile.get_industry_display() if profile.industry else "our space"
    tones = profile.tone_attributes or ["approachable", "confident"]
    tone_str = ", ".join(t.replace("_", " ") for t in tones[:3])
    return (
        f"{name} sounds {tone_str} — helpful, clear, and ready for social commerce "
        f"in {industry.lower()}."
    )
