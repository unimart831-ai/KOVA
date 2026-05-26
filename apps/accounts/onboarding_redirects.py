"""Post-onboarding redirects — commerce-first when intent/industry warrants it."""

from __future__ import annotations

from django.conf import settings

from apps.accounts.setup_mission import get_onboarding_intent, is_commerce_industry


def should_use_commerce_first(user) -> bool:
    profile = user.profile
    intent = get_onboarding_intent(profile)
    if intent in ("sell", "both"):
        return True
    return is_commerce_industry(profile.industry)


def post_onboarding_redirect_url_name(user) -> str:
    if should_use_commerce_first(user):
        return "products:snap"
    return "content:studio"


def post_onboarding_site_path(user) -> str:
    site = getattr(settings, "SITE_URL", "https://kovaagent.com").rstrip("/")
    if should_use_commerce_first(user):
        return f"{site}/products/snap/"
    return f"{site}/brief/"
