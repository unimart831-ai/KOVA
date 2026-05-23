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
    """Fill placeholder name from vision analysis and refresh shop slug."""
    update_fields: list[str] = []

    detected_name = sanitize_product_name(
        analysis.get("detected_name")
        or analysis.get("product_name")
        or analysis.get("service_name")
        or analysis.get("name_on_package")
        or analysis.get("label_text")
        or ""
    )
    brand = sanitize_product_name(analysis.get("brand") or analysis.get("brand_name") or "")
    if not detected_name and brand:
        variant = sanitize_product_name(analysis.get("variant") or analysis.get("product_line") or "")
        detected_name = sanitize_product_name(f"{brand} {variant}".strip())

    if detected_name and is_placeholder_product_name(product.name):
        product.name = detected_name[:200]
        update_fields.append("name")
        from apps.products.commerce_links import ensure_commerce_slug

        product.commerce_slug = ""
        slug = ensure_commerce_slug(product, save=False, force=True)
        product.commerce_slug = slug
        update_fields.append("commerce_slug")

    if update_fields:
        product.save(update_fields=[*update_fields, "updated_at"])

    from apps.products.commerce_seo import ensure_commerce_seo_copy

    profile = product.user.profile
    if ensure_commerce_seo_copy(product, profile, analysis):
        if "description" not in update_fields:
            update_fields.append("description")

    return update_fields


def initial_commerce_post_status(user) -> str:
    """Post status for Snap-generated carousel/reel posts."""
    if should_auto_publish_commerce(user):
        return Post.Status.APPROVED
    return Post.Status.PENDING_APPROVAL


def _profile(user) -> UserProfile | None:
    if isinstance(user, UserProfile):
        return user
    return getattr(user, "profile", None)
