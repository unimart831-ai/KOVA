"""Magic Fill — auto-populate onboarding fields from a connected social profile.

When the user picks "Connect a social account to auto-fill" on the path-choice
screen, they go through the normal OAuth flow. After the SocialAccount is
created, this module:

  1. Runs `audit_social_account(account, generate_suggestions=False)` to pull
     a ProfileSnapshot (bio, description, website, phone, email, category,
     profile picture, etc.).
  2. Maps platform-agnostic fields onto UserProfile fields — but never
     overwrites values the user has already supplied.
  3. Attempts a soft industry inference from the platform `category` string.

Returns a list of UserProfile fields that were populated, so the view can
surface "We filled in X, Y, Z for you" to the user.

Intentionally synchronous — runs in the OAuth callback path immediately after
the account is created, so the user lands on Step 1 with everything ready.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Crude keyword → Industry mapping. Platform category strings are messy
# ("Local business", "Salon", "Hair Salon", "Beauty, Cosmetic & Personal
# Care", "Restaurant"). We scan lowercased for keywords in priority order
# and pick the first match.
_CATEGORY_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("salon", "barber", "spa", "nail", "lash", "wax", "beauty", "cosmetic", "personal care"), "salon_beauty"),
    (("restaurant", "cafe", "coffee", "bakery", "food", "kitchen", "bar", "eatery"), "food_restaurant"),
    (("hotel", "lodge", "travel", "tour", "safari"), "travel_tourism"),
    (("hospital", "clinic", "doctor", "dentist", "dental", "pharmacy", "wellness", "fitness", "gym"), "health"),
    (("law", "legal", "advocate", "attorney"), "legal"),
    (("school", "academy", "university", "college", "education", "training"), "education"),
    (("real estate", "property", "realtor", "realty"), "real_estate"),
    (("agency", "marketing", "advertising", "studio"), "agency"),
    (("consult", "advisory", "professional services"), "consulting"),
    (("retail", "shop", "store", "boutique", "market"), "wholesale_retail"),
    (("fashion", "clothing", "apparel"), "fashion_beauty"),
    (("farm", "agric", "produce"), "agriculture"),
    (("logist", "transport", "courier", "delivery"), "logistics_transport"),
    (("construction", "manufactur", "factory"), "construction"),
    (("software", "saas", "tech", "app"), "saas"),
    (("media", "production", "studio", "entertainment", "music"), "media_entertainment"),
    (("creator", "influencer", "blogger"), "creator"),
    (("nonprofit", "ngo", "charity", "foundation"), "nonprofit"),
    (("bank", "fintech", "finance", "credit", "loans"), "finance"),
]


def _infer_industry(category: str) -> Optional[str]:
    """Map a platform `category` string to one of our Industry choices."""
    if not category:
        return None
    cat = category.lower()
    for keywords, industry in _CATEGORY_KEYWORDS:
        if any(kw in cat for kw in keywords):
            return industry
    return None


def apply_magic_fill(user, account) -> list[str]:
    """Run a profile audit on `account` and copy useful fields onto the user.

    Args:
        user: the User whose profile we are filling.
        account: a SocialAccount (already created by the OAuth callback) that
            belongs to `user`. Should be `is_active=True` with a valid token.

    Returns the list of `UserProfile` fields that were populated.
    """
    from apps.profile_audit.auditor import audit_social_account

    audit = audit_social_account(account, generate_suggestions=False)
    if audit is None or audit.error:
        logger.info(
            "Magic Fill: audit failed for %s/%s — error=%r",
            user.email, account.platform, getattr(audit, "error", "no audit"),
        )
        return []

    fields_present = audit.fields_present or {}
    profile = user.profile
    applied: list[str] = []

    def _maybe_set(field: str, value, *, treat_as_empty=("",)):
        """Only fill a field if the current value is empty / default."""
        current = getattr(profile, field, None)
        if current in treat_as_empty or current is None:
            setattr(profile, field, value)
            applied.append(field)

    # ── Direct mappings (platform → UserProfile) ─────────────────────
    # Many providers expose: bio, description, website, phone, email,
    # address, category, profile_picture_url, page_button. See
    # apps/platforms/providers/base.py:ProfileSnapshot.

    bio = (fields_present.get("bio") or "").strip()
    description = (fields_present.get("description") or "").strip()
    # Prefer the longer of the two as a brand_voice starter — both often
    # contain the same content but description tends to be richer on FB/IG.
    voice_seed = description if len(description) > len(bio) else bio
    if voice_seed:
        _maybe_set("brand_voice", voice_seed)

    website = (fields_present.get("website") or "").strip()
    if website:
        _maybe_set("website_url", website)

    phone = (fields_present.get("phone") or "").strip()
    if phone:
        _maybe_set("cta_phone", phone)

    email = (fields_present.get("email") or "").strip()
    if email:
        _maybe_set("cta_email", email)

    logo_url = (fields_present.get("profile_picture_url") or "").strip()
    if logo_url:
        _maybe_set("brand_logo_url", logo_url)

    # company_name often lives on SocialAccount.display_name (the Page/Profile
    # display name), not in fields_present. Use that as a fallback.
    display_name = (account.display_name or account.username or "").strip()
    if display_name:
        _maybe_set("company_name", display_name)

    # ── Industry inference from platform category ────────────────────
    category = (fields_present.get("category") or "").strip()
    if category:
        inferred = _infer_industry(category)
        if inferred:
            # industry is a CharField with choices; "" means not set.
            _maybe_set("industry", inferred)

    if applied:
        profile.save(update_fields=applied)
        logger.info(
            "Magic Fill applied %d fields for %s from %s: %s",
            len(applied), user.email, account.platform, applied,
        )

    # ── Apply the industry starter pack now that we (maybe) have one ─
    # apply_pack is idempotent — only fills fields still empty.
    if profile.industry:
        from apps.accounts.industry_packs import apply_pack
        applied += apply_pack(profile, profile.industry)

    return applied
