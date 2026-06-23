"""Post-onboarding redirects — commerce-first when intent/industry warrants it."""

from __future__ import annotations

from django.conf import settings

from apps.accounts.setup_mission import get_onboarding_intent, is_commerce_industry


def should_use_commerce_first(user) -> bool:
    profile = user.profile
    if profile.business_model in ("product", "service"):
        return True
    if profile.business_model == "professional":
        return False
    intent = get_onboarding_intent(profile)
    if intent in ("sell", "both"):
        return True
    return is_commerce_industry(profile.industry)


def post_onboarding_redirect_url_name(user) -> str:
    profile = user.profile
    if profile.business_model == "service":
        from apps.bookings.models import BookingLink

        if BookingLink.objects.filter(user=user, is_active=True).exists():
            return "bookings:list"
        return "bookings:link_create"
    if should_use_commerce_first(user):
        return "products:snap"
    return "content:studio"


def post_onboarding_site_path(user) -> str:
    site = getattr(settings, "SITE_URL", "https://kovaagent.com").rstrip("/")
    profile = user.profile
    if profile.business_model == "service":
        from apps.bookings.models import BookingLink
        from apps.bookings.service_setup import booking_public_url

        link = BookingLink.objects.filter(user=user, is_active=True).first()
        if link:
            return booking_public_url(link)
        return f"{site}/bookings/links/new/"
    if should_use_commerce_first(user):
        return f"{site}/products/snap/"
    return f"{site}/brief/"
