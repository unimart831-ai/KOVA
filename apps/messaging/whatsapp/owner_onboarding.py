"""
WhatsApp onboarding — "What business do you run?" → profile fields.

Runs on Kova master number when owner texts before web onboarding is complete.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

WA_ONBOARDING_KEY = "wa_onboarding_step"


def try_whatsapp_onboarding(user, text: str) -> str | None:
    """
    Returns reply text if handled, else None.
    Steps: ask business → ask industry hint → confirm + web link.
    """
    profile = getattr(user, "profile", None)
    if not profile or user.onboarding_completed:
        return None

    steps = dict(profile.onboarding_step_timestamps or {})
    step = steps.get(WA_ONBOARDING_KEY, "start")
    normalized = (text or "").strip()

    if step == "start" or normalized.lower() in {"hi", "hello", "start", "hire kova"}:
        steps[WA_ONBOARDING_KEY] = "awaiting_business"
        profile.onboarding_step_timestamps = steps
        profile.save(update_fields=["onboarding_step_timestamps", "updated_at"])
        return (
            "Welcome to Kova 👋\n\n"
            "What business do you run? (e.g. *Nairobi braids salon* or *electronics shop*)"
        )

    if step == "awaiting_business" and len(normalized) >= 3:
        profile.company_name = normalized[:200]
        if not profile.brand_voice:
            profile.brand_voice = f"Friendly, professional voice for {normalized[:80]}."
        steps[WA_ONBOARDING_KEY] = "awaiting_audience"
        profile.onboarding_step_timestamps = steps
        profile.save(update_fields=[
            "company_name", "brand_voice", "onboarding_step_timestamps", "updated_at",
        ])
        return "Who is your ideal customer? (e.g. *young professionals in Westlands*)"

    if step == "awaiting_audience" and len(normalized) >= 3:
        profile.target_audience = normalized[:500]
        steps[WA_ONBOARDING_KEY] = "done"
        steps["wa_onboarding_completed"] = True
        profile.onboarding_step_timestamps = steps
        profile.save(update_fields=["target_audience", "onboarding_step_timestamps", "updated_at"])
        from django.conf import settings

        site = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
        return (
            f"Perfect — Kova knows {profile.company_name}.\n\n"
            f"Finish setup on web (2 min):\n{site}/accounts/onboarding/\n\n"
            "Or send a product photo here to Snap to Sell."
        )

    return None
