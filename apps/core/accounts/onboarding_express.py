"""Express onboarding helpers — minimal input, confirm-not-fill flow."""

from __future__ import annotations

INTENT_SELL = "sell"
INTENT_GROW = "grow"
INTENT_BOTH = "both"
VALID_INTENTS = frozenset({INTENT_SELL, INTENT_GROW, INTENT_BOTH})

BUSINESS_MODEL_PRODUCT = "product"
BUSINESS_MODEL_SERVICE = "service"
BUSINESS_MODEL_DIGITAL = "digital"
BUSINESS_MODEL_PROFESSIONAL = "professional"
BUSINESS_MODEL_MULTIPLE = "multiple"
VALID_BUSINESS_MODELS = frozenset({
    BUSINESS_MODEL_PRODUCT,
    BUSINESS_MODEL_SERVICE,
    BUSINESS_MODEL_DIGITAL,
    BUSINESS_MODEL_PROFESSIONAL,
    BUSINESS_MODEL_MULTIPLE,
})


def record_intent(profile, intent: str) -> None:
    if intent not in VALID_INTENTS:
        return
    profile.record_onboarding_step(f"intent_{intent}")


def record_business_model(profile, business_model: str) -> None:
    if business_model not in VALID_BUSINESS_MODELS:
        return
    profile.business_model = business_model
    profile.save(update_fields=["business_model"])
    profile.record_onboarding_step(f"business_model_{business_model}")
    if business_model == BUSINESS_MODEL_PRODUCT:
        record_intent(profile, INTENT_SELL)
    elif business_model == BUSINESS_MODEL_SERVICE:
        record_intent(profile, INTENT_SELL)
    elif business_model == BUSINESS_MODEL_DIGITAL:
        record_intent(profile, INTENT_SELL)
    elif business_model == BUSINESS_MODEL_PROFESSIONAL:
        record_intent(profile, INTENT_GROW)
    elif business_model == BUSINESS_MODEL_MULTIPLE:
        record_intent(profile, INTENT_BOTH)


def apply_business_model_defaults(profile, user) -> None:
    """Set sensible defaults after business model selection."""
    if not profile.business_model:
        profile.business_model = BUSINESS_MODEL_SERVICE

    if profile.business_model == BUSINESS_MODEL_SERVICE:
        profile.default_cta_type = profile.default_cta_type or "whatsapp"
        if not profile.goals:
            profile.goals = ["generate_leads", "book_appointments"]
    elif profile.business_model == BUSINESS_MODEL_PROFESSIONAL:
        profile.platform_priority = profile.platform_priority or {"linkedin": 1, "instagram": 2}
        if not profile.goals:
            profile.goals = ["generate_leads", "brand_awareness"]
        try:
            from apps.commerce.leads.defaults import ensure_professional_nurture_sequences

            ensure_professional_nurture_sequences(user)
        except Exception:
            pass
    elif profile.business_model == BUSINESS_MODEL_PRODUCT:
        profile.default_cta_type = profile.default_cta_type or "whatsapp"
        if not profile.goals:
            profile.goals = ["generate_leads", "drive_sales"]
    elif profile.business_model == BUSINESS_MODEL_DIGITAL:
        # Digital products optimise for instant, low-friction purchase.
        profile.default_cta_type = profile.default_cta_type or "link"
        if not profile.goals:
            profile.goals = ["drive_sales", "generate_leads"]
    elif profile.business_model == BUSINESS_MODEL_MULTIPLE:
        profile.default_cta_type = profile.default_cta_type or "whatsapp"
        if not profile.goals:
            profile.goals = ["generate_leads", "drive_sales"]
    profile.save()

    if profile.business_model == BUSINESS_MODEL_SERVICE:
        try:
            from apps.commerce.bookings.service_setup import ensure_primary_booking_link

            ensure_primary_booking_link(
                user,
                label=profile.company_name or "Book an appointment",
                industry=profile.industry or "generic",
            )
        except Exception:
            pass


def ensure_brand_defaults(profile, user) -> None:
    """Apply industry pack and safe defaults so preview → finish works without Step 2 edits."""
    from apps.core.accounts.industry_packs import apply_pack

    if profile.industry:
        apply_pack(profile, profile.industry)

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
