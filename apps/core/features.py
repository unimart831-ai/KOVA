"""Optional product-surface feature flags.

Apps stay installed (migrations), but URLs / nav / beat / middleware can be gated.
Defaults keep current behavior ON.
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
