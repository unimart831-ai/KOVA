"""Commerce Autopilot — snap a photo, agents handle listing → content → publish."""

from __future__ import annotations

from apps.accounts.models import UserProfile
from apps.content.models import Post

SNAP_PLACEHOLDER_NAMES = frozenset({
    "new product",
    "new service",
    "new digital product",
    "snap listing",
})

INVALID_PRODUCT_NAMES = frozenset({
    "null",
    "none",
    "unknown",
    "n/a",
    "na",
    "undefined",
    "nil",
})


def sanitize_product_name(value) -> str:
    """Reject empty, null-like, and junk names from forms or vision AI."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in INVALID_PRODUCT_NAMES:
        return ""
    if lowered in ("null", "none") or lowered.startswith("null "):
        return ""
    return text


def commerce_autopilot_active(user) -> bool:
    """True when Commerce Autopilot is on and emergency pause is off."""
    profile = _profile(user)
    if not profile or profile.emergency_pause:
        return False
    return bool(profile.commerce_autopilot)


def should_auto_publish_commerce(user) -> bool:
    """Auto-approve + auto-schedule commerce and content posts."""
    profile = _profile(user)
    if not profile or profile.emergency_pause:
        return False
    return bool(profile.commerce_autopilot or profile.auto_approve_posts)


def placeholder_name_for_offering(offering_type: str) -> str:
    return {
        "service": "New service",
        "digital": "New digital product",
    }.get(offering_type, "New product")


def unique_placeholder_name(user, offering_type: str) -> str:
    """Placeholder name that won't collide with existing catalog entries."""
    from apps.products.models import Product

    base = placeholder_name_for_offering(offering_type)
    if not Product.objects.filter(user=user, name__iexact=base, is_active=True).exists():
        return base
    n = 2
    while Product.objects.filter(user=user, name__iexact=f"{base} {n}", is_active=True).exists():
        n += 1
    return f"{base} {n}"


def is_placeholder_product_name(name: str) -> bool:
    n = sanitize_product_name(name).lower()
    if not n:
        return True
    if n in SNAP_PLACEHOLDER_NAMES:
        return True
    if n in INVALID_PRODUCT_NAMES:
        return True
    if "ai naming" in n:
        return True
    for prefix in ("new product", "new service", "new digital product", "snap listing"):
        if n == prefix or n.startswith(f"{prefix} "):
            return True
    for prefix in ("product ", "service ", "digital product "):
        if n.startswith(prefix):
            return True
    return False


def apply_ai_detected_product_fields(product, analysis: dict) -> list[str]:
    """Improve name/description from vision analysis and refresh shop slug when needed."""
    from apps.products.product_copy import enrich_product_copy

    profile = product.user.profile
    return enrich_product_copy(product, analysis, profile)


def initial_commerce_post_status(user, product=None) -> str:
    """Post status for Snap-generated carousel/reel posts."""
    from apps.partners.marketplace_rules import initial_marketplace_post_status

    marketplace_status = initial_marketplace_post_status(user, product)
    if marketplace_status:
        return marketplace_status
    if should_auto_publish_commerce(user):
        return Post.Status.APPROVED
    return Post.Status.PENDING_APPROVAL


def _profile(user) -> UserProfile | None:
    if isinstance(user, UserProfile):
        return user
    return getattr(user, "profile", None)
