"""Public campaign landing pages — /c/<slug>/"""

from __future__ import annotations

import logging
from urllib.parse import quote

from django.utils.text import slugify

logger = logging.getLogger(__name__)


def campaign_page_path(campaign) -> str:
    slug = (getattr(campaign, "slug", None) or "").strip()
    if not slug:
        slug = slugify(getattr(campaign, "title", "") or "campaign")[:50] or str(campaign.pk)[:8]
    return f"/c/{slug}/"


def campaign_page_url(campaign, request=None) -> str:
    path = campaign_page_path(campaign)
    if request:
        return request.build_absolute_uri(path)
    from django.conf import settings

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site}{path}" if site else path


def ensure_campaign_commerce_url(campaign, *, save: bool = True) -> str:
    """Persist public campaign URL; return absolute-ready path."""
    url = campaign_page_path(campaign)
    if campaign.commerce_url != url:
        campaign.commerce_url = url
        if save:
            campaign.save(update_fields=["commerce_url", "updated_at"])
    return url


def resolve_public_campaign(campaign_slug: str):
    from apps.create.content.campaign_archive import is_campaign_publicly_live
    from apps.create.content.models import MarketingCampaign

    campaign = (
        MarketingCampaign.objects.select_related(
            "user",
            "user__profile",
            "content_seed",
            "content_seed__product",
            "business_asset",
            "business_asset__product",
        )
        .filter(slug=campaign_slug)
        .first()
    )
    if not campaign or not is_campaign_publicly_live(campaign):
        return None
    return campaign


def _campaign_product(campaign):
    product = None
    if campaign.business_asset_id and campaign.business_asset:
        product = getattr(campaign.business_asset, "product", None)
    if product is None and campaign.content_seed_id:
        product = getattr(campaign.content_seed, "product", None)
    return product


def _hero_image_url(campaign, product) -> str:
    if product:
        hero = getattr(product, "shop_hero_image_url", None)
        if hero:
            return hero
        urls = getattr(product, "all_image_urls", None) or []
        if urls:
            return urls[0]
    asset = campaign.business_asset
    if asset and asset.metadata:
        img = asset.metadata.get("image_url") or asset.metadata.get("hero_url")
        if img:
            return img
    return ""


def build_campaign_page_context(campaign, request) -> dict:
    from django.urls import reverse

    from apps.core.billing.models import get_user_plan_limits
    from apps.commerce.products.commerce_checkout import (
        build_campaign_order_wa_text,
        checkout_heading_for,
    )
    from apps.commerce.products.commerce_links import commerce_link_url, resolve_page_slug
    from apps.commerce.products.commerce_seo import brand_name
    from apps.commerce.products.commerce_social import get_public_social_links, resolve_shop_whatsapp
    from apps.commerce.products.storefront import resolve_storefront, storefront_body_classes

    profile = campaign.user.profile
    user = campaign.user
    product = _campaign_product(campaign)
    hero_image = _hero_image_url(campaign, product)
    brand = brand_name(profile, user)
    proposal = campaign.proposal_meta or {}
    rationale = (proposal.get("rationale") or "").strip()
    formats = proposal.get("suggested_formats") or []
    storefront = resolve_storefront(profile, user, [], [])

    wa_text = build_campaign_order_wa_text(campaign, product, brand, request=request)
    from apps.commerce.products.commerce_checkout import tracked_whatsapp_order_url

    wa_url = tracked_whatsapp_order_url(
        user, profile, brand,
        product=product, campaign=campaign, request=request, source="campaign",
    )
    if not wa_url:
        wa_phone = resolve_shop_whatsapp(profile, user)
        wa_url = f"https://wa.me/{wa_phone}?text={quote(wa_text)}" if wa_phone else ""
    social_links = get_public_social_links(user, profile, wa_text=wa_text)

    shop_slug = resolve_page_slug(profile)
    secondary_shop_url = commerce_link_url(product, request) if product else ""
    seller_limits = get_user_plan_limits(user)
    mpesa_commerce_enabled = bool(seller_limits.get("mpesa_commerce"))
    mpesa_available = bool(
        product
        and getattr(product, "offering_type", "product") == "product"
        and mpesa_commerce_enabled
        and product.price
        and product.currency == "KES"
        and getattr(product, "stock_status", "") != "out_of_stock"
    )
    mpesa_pay_url = ""
    if mpesa_available and product.commerce_slug:
        mpesa_pay_url = reverse(
            "public_commerce_pay",
            kwargs={"page_slug": shop_slug, "commerce_slug": product.commerce_slug},
        )

    can_purchase = bool(product) or bool(wa_url)
    checkout_heading = checkout_heading_for(product, whatsapp_available=bool(wa_url))
    if not product and wa_url:
        checkout_heading = "Order on WhatsApp"

    seo_title = f"{campaign.title} | {brand}"
    seo_description = rationale or (
        f"Order {campaign.title} from {brand} on WhatsApp — fast, personal service."
    )[:300]

    return {
        "campaign": campaign,
        "product": product,
        "profile": profile,
        "brand_name": brand,
        "hero_image": hero_image,
        "rationale": rationale,
        "suggested_formats": formats,
        "wa_url": wa_url,
        "social_links": social_links,
        "storefront": storefront,
        "storefront_body_class": storefront_body_classes(storefront, extra="campaign-landing"),
        "seo_title": seo_title,
        "seo_description": seo_description,
        "canonical_url": campaign_page_url(campaign, request),
        "og_image": hero_image,
        "objective": campaign.get_objective_display(),
        "quality_score": campaign.quality_score,
        "checkout_heading": checkout_heading,
        "checkout_wa_button_label": "Order on WhatsApp",
        "mpesa_available": mpesa_available,
        "mpesa_pay_url": mpesa_pay_url,
        "can_purchase": can_purchase,
        "secondary_shop_url": secondary_shop_url,
        "primary_action_url": "",
        "primary_action_label": "",
        "primary_action_external": False,
    }


def track_campaign_view(request, campaign):
    try:
        from apps.insight.analytics.models import Conversion
        from apps.create.content.campaign_attribution import create_attributed_conversion

        create_attributed_conversion(
            campaign.user,
            Conversion.ConversionType.CLICK,
            product=_campaign_product(campaign),
            campaign=campaign,
            event_name="campaign_page_view",
            utm_campaign=campaign.slug,
            metadata={
                "source": "campaign",
                "referrer": request.META.get("HTTP_REFERER", "")[:500],
            },
        )
    except Exception:
        logger.exception("campaign page view tracking failed for %s", campaign.pk)
