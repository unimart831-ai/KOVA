"""
Marketplace Partner API authentication.

Partners authenticate via the X-Kova-Partner-Key header.
This gives them access to partner-only endpoints (seller provisioning,
product sync) while scoping all operations to their marketplace.
"""

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from apps.partners.models import MarketplacePartner


class MarketplacePartnerUser:
    """
    Lightweight user-like object for DRF when a marketplace partner
    authenticates via API key (not as a Django user session).
    """

    def __init__(self, marketplace_partner):
        self.marketplace_partner = marketplace_partner
        self.partner = marketplace_partner.partner
        self.is_sandbox = bool(getattr(marketplace_partner, "is_sandbox", False))
        # DRF expects these attributes
        self.is_authenticated = True
        self.pk = marketplace_partner.pk

    def __str__(self):
        return f"MarketplacePartner:{self.marketplace_partner.slug}"


class MarketplaceAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate marketplace partners via X-Kova-Partner-Key header.

    Usage:
        GET /api/v1/partner/sellers/
        X-Kova-Partner-Key: kmp_a3x7...full_key_here
    """

    HEADER = "HTTP_X_KOVA_PARTNER_KEY"
    KEYWORD = "X-Kova-Partner-Key"

    def authenticate(self, request):
        raw_key = request.META.get(self.HEADER)
        if not raw_key:
            return None  # Not a partner request — let other auth backends handle it

        raw_key = raw_key.strip()
        if not raw_key:
            raise AuthenticationFailed("Empty API key provided.")

        mp, error = MarketplacePartner.authenticate(raw_key)
        if error:
            raise AuthenticationFailed(error)

        return (MarketplacePartnerUser(mp), raw_key)

    def authenticate_header(self, request):
        return self.KEYWORD


class IsMarketplacePartner(BasePermission):
    """Ensure the request was authenticated as a marketplace partner."""
    message = "This endpoint requires marketplace partner API key authentication."

    def has_permission(self, request, view):
        return isinstance(request.user, MarketplacePartnerUser)
