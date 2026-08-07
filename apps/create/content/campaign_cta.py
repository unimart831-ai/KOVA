"""
Default post CTAs — campaign landing page or Kova Commerce URL.

Priority for social links:
  1. /c/<campaign_slug>/ when the seed has a MarketingCampaign
  2. Product commerce page (/shop/.../item/)
  3. Public shop index (/shop/<handle>/)
  4. Profile default CTA URL (if configured)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _absolute_url(path: str, request=None) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    if request:
        return request.build_absolute_uri(path)
    from django.conf import settings

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site}{path}" if site else path


def get_marketing_campaign(seed):
    if not seed:
        return None
    try:
        return seed.marketing_campaign
    except Exception:
        return None


def resolve_post_commerce_url(seed, user=None, request=None) -> str:
    """
    Best Kova URL for post CTAs and first comments.

    Campaign page wins when a MarketingCampaign exists — closes the
    attribution loop: post → /c/ → shop/checkout → sale.
    """
    campaign = get_marketing_campaign(seed)
    if campaign:
        from apps.create.content.campaign_pages import campaign_page_url

        return campaign_page_url(campaign, request)

    owner = user or (getattr(seed, "user", None) if seed else None)
    if seed and getattr(seed, "product_id", None) and seed.product:
        from apps.commerce.products.product_cta import resolve_product_cta_url

        product_url = resolve_product_cta_url(seed.product, request)
        if product_url:
            return product_url

    if owner:
        profile = getattr(owner, "profile", None)
        if profile:
            from apps.commerce.products.commerce_links import resolve_page_slug

            slug = resolve_page_slug(profile)
            if slug:
                return _absolute_url(f"/shop/{slug}/", request)

            default_url = (getattr(profile, "default_cta_url", "") or "").strip()
            if default_url and getattr(profile, "default_cta_type", "none") == "link":
                return default_url

    return ""


def campaign_cta_label(seed, campaign=None) -> str:
    campaign = campaign or get_marketing_campaign(seed)
    if campaign:
        objective = getattr(campaign, "objective", "sales")
        title = (getattr(campaign, "title", "") or "this offer").strip()
        if objective == "bookings":
            return "Book now →"
        if objective == "leads":
            return "Get in touch →"
        if objective == "awareness":
            return f"Learn more →"
        return f"Shop {title} →"[:255]

    if seed and getattr(seed, "product_id", None) and seed.product:
        from apps.commerce.products.product_cta import primary_action_label_for

        return f"{primary_action_label_for(seed.product)} →"[:255]

    return "View offer →"


def apply_default_campaign_cta(post, user, seed=None) -> bool:
    """
    Set link CTA on a post to the campaign or commerce URL.

    Skips when CTA already set. Returns True when fields were updated.
    """
    if (post.cta_type and post.cta_type != "none") and (post.cta_url or "").strip():
        return False

    seed = seed or getattr(post, "seed", None)
    url = resolve_post_commerce_url(seed, user)
    if not url:
        return False

    campaign = get_marketing_campaign(seed)
    post.cta_type = "link"
    post.cta_text = campaign_cta_label(seed, campaign)[:255]
    post.cta_url = url[:500]
    post.populate_utm()
    post.save(
        update_fields=[
            "cta_type",
            "cta_text",
            "cta_url",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "updated_at",
        ],
    )
    return True


def commerce_url_for_first_comment(seed, user=None, request=None) -> str:
    """URL passed into first-comment composers (campaign page preferred)."""
    return resolve_post_commerce_url(seed, user, request)
