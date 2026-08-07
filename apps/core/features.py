"""Optional product-surface feature flags.

Apps stay installed (migrations), but URLs / nav / beat / middleware can be gated.

V1 defaults keep only the growth-loop surfaces ON (Business Brain, Campaigns,
Publishing, Leads/Growth, Coach). Re-enable postponed features via FEATURE_* env.
"""

from __future__ import annotations

from django.conf import settings


def feature_enabled(name: str, default: bool = True) -> bool:
    features = getattr(settings, "KOVA_FEATURES", None) or {}
    return bool(features.get(name, default))


def kova_features_context(request):
    """Template context: {{ kova_features.bookings }} etc."""
    return {
        "kova_features": getattr(settings, "KOVA_FEATURES", {}) or {},
    }


# Platforms allowed for new OAuth/connect in V1 growth loop.
V1_PUBLISH_PLATFORMS = frozenset({"whatsapp", "facebook", "instagram"})


def platform_connect_allowed(platform_key: str) -> bool:
    """Whether a platform may appear in the connect UI / new OAuth flows."""
    key = (platform_key or "").lower()
    if key in V1_PUBLISH_PLATFORMS:
        return True
    if key == "tiktok":
        return feature_enabled("tiktok", default=False)
    if key == "linkedin":
        return feature_enabled("linkedin", default=False)
    return False
