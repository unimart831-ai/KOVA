"""UNIMART marketplace partner lookup — single canonical slug with legacy fallback."""

from __future__ import annotations

# Production / docs canonical slug (join URL, CLI --partner-slug, API examples).
CANONICAL_UNIMART_SLUG = "unimart-africa"

# Prefer unimart-africa; fall back to legacy unimart if that is what exists in DB.
UNIMART_SLUG_CANDIDATES = (CANONICAL_UNIMART_SLUG, "unimart")


def resolve_unimart_partner():
    """Return the UNIMART MarketplacePartner row, or None if not configured."""
    from apps.core.partners.models import MarketplacePartner

    for slug in UNIMART_SLUG_CANDIDATES:
        mp = MarketplacePartner.objects.filter(slug=slug).first()
        if mp:
            return mp
    return None
