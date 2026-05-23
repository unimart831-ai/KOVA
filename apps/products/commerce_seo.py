"""SEO helpers for public Commerce Link and shop index pages."""

from __future__ import annotations

import json
import re
from typing import Any

from django.conf import settings

from apps.products.commerce_autopilot import is_placeholder_product_name
from apps.products.commerce_links import commerce_link_url, resolve_page_slug

MIN_SEO_DESCRIPTION_LEN = 40


def brand_name(profile, user) -> str:
    return profile.company_name or user.full_name or user.username or "Shop"


def absolute_media_url(request, url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if request:
        return request.build_absolute_uri(url)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    if not site:
        return url
    if url.startswith("/"):
        return f"{site}{url}"
    return f"{site}/{url}"


def shop_index_url(profile, request=None) -> str:
    page_slug = resolve_page_slug(profile)
    path = f"/shop/{page_slug}/"
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site}{path}" if site else path


def build_seo_title(product, profile, user, *, brand: str | None = None) -> str:
    brand = brand or brand_name(profile, user)
    parts = [product.name.strip()]
    price = product.display_price
    if price:
        parts.append(price)
    parts.append(brand)
    title = " · ".join(parts)
    return title[:70]


def build_seo_description(
    product,
    profile,
    user,
    *,
    brand: str | None = None,
    mpesa_available: bool = False,
    whatsapp_available: bool = False,
) -> str:
    brand = brand or brand_name(profile, user)
    desc = (product.description or "").strip()
    if len(desc) >= MIN_SEO_DESCRIPTION_LEN:
        return desc[:160]

    city = (profile.city or "").strip()
    price = product.display_price
    bits = [f"Buy {product.name}"]
    if price:
        bits.append(f"for {price}")
    bits.append(f"from {brand}")
    if city:
        bits.append(f"in {city}")
    generated = re.sub(r"\s+", " ", " ".join(bits)).strip()

    payment_bits = []
    if mpesa_available:
        payment_bits.append("M-Pesa")
    if whatsapp_available:
        payment_bits.append("WhatsApp")
    if payment_bits:
        generated += f". Pay with {' or '.join(payment_bits)}."
    else:
        generated += "."
    if desc:
        combined = f"{desc} {generated}"
        return combined[:160]
    return generated[:160]


def _schema_availability(product) -> str:
    from apps.products.models import Product

    if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
        return "https://schema.org/OutOfStock"
    if product.stock_status == Product.StockStatus.MADE_TO_ORDER:
        return "https://schema.org/PreOrder"
    return "https://schema.org/InStock"


def build_product_schema(
    product,
    profile,
    user,
    canonical_url: str,
    request=None,
    *,
    brand: str | None = None,
) -> dict[str, Any]:
    brand = brand or brand_name(profile, user)
    images = [
        absolute_media_url(request, url)
        for url in product.all_image_urls[:8]
        if url
    ]
    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": (product.description or build_seo_description(product, profile, user, brand=brand))[:500],
        "url": canonical_url,
        "brand": {"@type": "Brand", "name": brand},
    }
    if images:
        schema["image"] = images if len(images) > 1 else images[0]

    if product.price:
        schema["offers"] = {
            "@type": "Offer",
            "url": canonical_url,
            "priceCurrency": product.currency or "KES",
            "price": str(product.price),
            "availability": _schema_availability(product),
            "seller": {"@type": "Organization", "name": brand},
        }

    city = (profile.city or "").strip()
    if city:
        schema["areaServed"] = city

    return schema


def build_shop_schema(
    profile,
    user,
    products,
    canonical_url: str,
    request=None,
    *,
    brand: str | None = None,
) -> dict[str, Any]:
    brand = brand or brand_name(profile, user)
    page_slug = resolve_page_slug(profile)
    items = []
    for product in products[:50]:
        if not product.commerce_slug:
            continue
        item_url = commerce_link_url(product, request)
        entry: dict[str, Any] = {
            "@type": "Product",
            "name": product.name,
            "url": item_url,
        }
        if product.all_image_urls:
            entry["image"] = absolute_media_url(request, product.all_image_urls[0])
        items.append(entry)

    schema: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Store",
        "name": brand,
        "url": canonical_url,
        "identifier": page_slug,
    }
    headline = (profile.page_headline or "").strip()
    if headline:
        schema["description"] = headline
    city = (profile.city or "").strip()
    if city:
        schema["address"] = {"@type": "PostalAddress", "addressLocality": city}

    if items:
        schema["hasOfferCatalog"] = {
            "@type": "OfferCatalog",
            "name": f"{brand} products",
            "itemListElement": items,
        }
    return schema


def build_commerce_page_seo(
    request,
    product,
    profile,
    user,
    *,
    mpesa_available: bool = False,
    whatsapp_available: bool = False,
) -> dict[str, Any]:
    brand = brand_name(profile, user)
    canonical_url = commerce_link_url(product, request)
    seo_title = build_seo_title(product, profile, user, brand=brand)
    seo_description = build_seo_description(
        product,
        profile,
        user,
        brand=brand,
        mpesa_available=mpesa_available,
        whatsapp_available=whatsapp_available,
    )
    og_image = ""
    if product.all_image_urls:
        og_image = absolute_media_url(request, product.all_image_urls[0])

    schema = build_product_schema(
        product, profile, user, canonical_url, request, brand=brand,
    )
    return {
        "seo_title": seo_title,
        "seo_description": seo_description,
        "canonical_url": canonical_url,
        "og_image": og_image,
        "product_schema_json": json.dumps(schema, ensure_ascii=False),
        "shop_index_url": shop_index_url(profile, request),
    }


def build_shop_page_seo(request, profile, user, products) -> dict[str, Any]:
    brand = brand_name(profile, user)
    canonical_url = shop_index_url(profile, request)
    city = (profile.city or "").strip()
    count = len(products)
    headline = (profile.page_headline or "").strip()

    seo_title = f"{brand} Shop"
    if city:
        seo_title = f"{brand} · Shop in {city}"
    seo_title = seo_title[:70]

    if headline:
        seo_description = headline[:160]
    else:
        seo_description = f"Shop {count} product{'s' if count != 1 else ''} from {brand}"
        if city:
            seo_description += f" in {city}"
        seo_description += ". Pay with M-Pesa or WhatsApp."

    og_image = ""
    for product in products:
        if product.all_image_urls:
            og_image = absolute_media_url(request, product.all_image_urls[0])
            break

    schema = build_shop_schema(profile, user, products, canonical_url, request, brand=brand)
    return {
        "seo_title": seo_title,
        "seo_description": seo_description[:160],
        "canonical_url": canonical_url,
        "og_image": og_image,
        "shop_schema_json": json.dumps(schema, ensure_ascii=False),
    }


def ensure_commerce_seo_copy(product, profile, analysis: dict | None = None) -> bool:
    """Fill thin product descriptions for SEO. Returns True if updated."""
    desc = (product.description or "").strip()
    if len(desc) >= MIN_SEO_DESCRIPTION_LEN:
        return False

    user = product.user
    brand = brand_name(profile, user)
    city = (profile.city or "").strip()
    price = product.display_price

    if analysis and (analysis.get("description") or "").strip():
        new_desc = analysis["description"].strip()
    else:
        parts = [f"Shop {product.name}"]
        if price:
            parts.append(f"for {price}")
        parts.append(f"from {brand}")
        if city:
            parts.append(f"in {city}")
        new_desc = " ".join(parts) + ". Pay with M-Pesa or WhatsApp."

    product.description = new_desc[:1000]
    product.save(update_fields=["description", "updated_at"])
    return True


def commerce_seo_checklist(product, profile) -> dict[str, Any]:
    """Seller-facing checklist for commerce page discoverability."""
    user = product.user
    desc = (product.description or "").strip()
    has_photo = bool(product.image or product.additional_images)
    has_price = bool(product.price or (product.price_range_min and product.price_range_max))
    has_city = bool((profile.city or "").strip())
    has_whatsapp = bool((profile.cta_whatsapp or "").strip())
    has_slug = bool(product.commerce_slug)
    has_real_name = not is_placeholder_product_name(product.name)

    items = [
        {
            "id": "name",
            "label": "Clear product name",
            "done": has_real_name,
            "tip": "Use the real product name — not “New product”.",
        },
        {
            "id": "description",
            "label": "Product description (2+ sentences)",
            "done": len(desc) >= MIN_SEO_DESCRIPTION_LEN,
            "tip": "Add what it is, who it’s for, and why buy from you.",
        },
        {
            "id": "photo",
            "label": "Product photo",
            "done": has_photo,
            "tip": "Snap or upload a clear photo — used in Google & WhatsApp previews.",
        },
        {
            "id": "price",
            "label": "Price listed",
            "done": has_price,
            "tip": "Buyers and search snippets show your price when set.",
        },
        {
            "id": "city",
            "label": "City on your profile",
            "done": has_city,
            "tip": "Helps local search like “lotion Nairobi”. Update in Settings.",
        },
        {
            "id": "whatsapp",
            "label": "WhatsApp number",
            "done": has_whatsapp,
            "tip": "Lets customers chat after finding you on Google.",
        },
        {
            "id": "slug",
            "label": "Shareable commerce link",
            "done": has_slug,
            "tip": "Auto-created — copy your Commerce Link and post it everywhere.",
        },
    ]
    done_count = sum(1 for item in items if item["done"])
    return {
        "items": items,
        "done_count": done_count,
        "total": len(items),
        "score_pct": int(round(done_count / len(items) * 100)) if items else 0,
        "ready": done_count == len(items),
        "needs_profile_settings": not (has_city and has_whatsapp),
    }
