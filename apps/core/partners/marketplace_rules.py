"""Marketplace partner enforcement helpers — platforms, approval, sandbox."""

from __future__ import annotations

from apps.create.content.models import Post


def get_active_marketplace_seller(user):
    """Return (marketplace, seller_account) for an active marketplace seller."""
    from apps.core.partners.models import MarketplaceSellerAccount

    seller = (
        MarketplaceSellerAccount.objects.filter(
            user=user,
            status=MarketplaceSellerAccount.Status.ACTIVE,
        )
        .select_related("marketplace")
        .first()
    )
    if seller:
        return seller.marketplace, seller
    return None, None


def marketplace_for_product(product):
    if product and getattr(product, "marketplace_partner_id", None):
        return product.marketplace_partner
    return None


def content_approval_required_for_user(user, product=None) -> bool:
    mp = marketplace_for_product(product)
    if not mp:
        _, seller = get_active_marketplace_seller(user)
        mp = seller.marketplace if seller else None
    if not mp:
        return False
    return bool(mp.get_setting("content_approval_required"))


def initial_marketplace_post_status(user, product=None) -> str | None:
    """Return PENDING_APPROVAL when marketplace requires seller approval."""
    if content_approval_required_for_user(user, product):
        return Post.Status.PENDING_APPROVAL
    return None


def is_platform_allowed(user, platform: str, product=None) -> bool:
    mp = marketplace_for_product(product)
    if not mp:
        mp, _ = get_active_marketplace_seller(user)
    if not mp:
        return True
    allowed = mp.get_setting("allowed_platforms")
    if not allowed:
        return True
    normalized = (platform or "").lower()
    return normalized in {p.lower() for p in allowed}


def is_sandbox_publish(user, product=None) -> bool:
    """True when this seller belongs to a sandbox marketplace (dry-run publish)."""
    mp = marketplace_for_product(product)
    if not mp:
        mp, _ = get_active_marketplace_seller(user)
    if not mp:
        return False
    return bool(getattr(mp, "is_sandbox", False))
