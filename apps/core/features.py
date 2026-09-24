"""Optional product-surface feature flags.

URLs / nav / beat / middleware can be gated via KOVA_FEATURES.
V1 publish platforms: WhatsApp, Facebook, Instagram only.
"""

from __future__ import annotations

from django.conf import settings


def feature_enabled(name: str, default: bool = True) -> bool:
    features = getattr(settings, "KOVA_FEATURES", None) or {}
    return bool(features.get(name, default))


def kova_features_context(request):
    """Template context: {{ kova_features.leads_nav }} etc."""
    return {
        "kova_features": getattr(settings, "KOVA_FEATURES", {}) or {},
    }


# Platforms allowed for new OAuth/connect in V1 growth loop.
V1_PUBLISH_PLATFORMS = frozenset({"whatsapp", "facebook", "instagram"})


def platform_connect_allowed(platform_key: str) -> bool:
    """Whether a platform may appear in the connect UI / new OAuth flows."""
    key = (platform_key or "").lower()
    return key in V1_PUBLISH_PLATFORMS
