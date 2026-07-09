"""Storefront resolver — theme, layout, and shop content helpers for /shop/ pages."""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from apps.accounts.models import UserProfile

DEFAULT_PRIMARY = "#0066FF"
DEFAULT_SECONDARY = "#0F172A"

ARCHETYPE_BY_INDUSTRY: dict[str, str] = {
    UserProfile.Industry.FASHION_BEAUTY: "boutique",
    UserProfile.Industry.SALON_BEAUTY: "boutique",
    UserProfile.Industry.WHOLESALE_RETAIL: "market_stall",
    UserProfile.Industry.AGRICULTURE: "market_stall",
    UserProfile.Industry.FOOD_RESTAURANT: "market_stall",
    UserProfile.Industry.CREATOR: "reel_shop",
    UserProfile.Industry.MEDIA_ENTERTAINMENT: "reel_shop",
    UserProfile.Industry.CONSULTING: "studio",
    UserProfile.Industry.HEALTH: "studio",
    UserProfile.Industry.REAL_ESTATE: "studio",
    UserProfile.Industry.ECOMMERCE: "catalog",
    UserProfile.Industry.FINANCE: "catalog",
    UserProfile.Industry.LEGAL: "catalog",
    UserProfile.Industry.EDUCATION: "catalog",
    UserProfile.Industry.AGENCY: "modern_dark",
    UserProfile.Industry.SAAS: "modern_dark",
    UserProfile.Industry.TRAVEL_TOURISM: "boutique",
}

VIBE_BY_INDUSTRY: dict[str, str] = {
    UserProfile.Industry.WHOLESALE_RETAIL: "classic_shop",
    UserProfile.Industry.AGRICULTURE: "classic_shop",
    UserProfile.Industry.FOOD_RESTAURANT: "classic_shop",
    UserProfile.Industry.CONSTRUCTION: "classic_shop",
    UserProfile.Industry.FASHION_BEAUTY: "lookbook",
    UserProfile.Industry.SALON_BEAUTY: "lookbook",
    UserProfile.Industry.TRAVEL_TOURISM: "magazine",
    UserProfile.Industry.MEDIA_ENTERTAINMENT: "magazine",
    UserProfile.Industry.CREATOR: "reels_first",
    UserProfile.Industry.ECOMMERCE: "minimal_catalog",
    UserProfile.Industry.SAAS: "minimal_catalog",
    UserProfile.Industry.FINANCE: "minimal_catalog",
    UserProfile.Industry.LEGAL: "minimal_catalog",
}

SECTION_ORDER_BY_VIBE: dict[str, list[str]] = {
    "classic_shop": ["hero", "catalog", "reels", "featured", "about", "faq", "trust"],
    "magazine": ["hero", "featured", "catalog", "reels", "about", "faq", "trust"],
    "reels_first": ["hero", "reels", "featured", "catalog", "about", "faq", "trust"],
    "minimal_catalog": ["hero", "catalog", "trust"],
    "lookbook": ["hero", "featured", "reels", "catalog", "about", "faq"],
}

SECTION_ORDER_BY_BUSINESS_MODEL: dict[str, list[str]] = {
    "product": ["hero", "catalog", "reels", "featured", "about", "faq", "trust"],
    "service": ["hero", "services", "bookings", "reels", "testimonials", "about", "faq"],
    "professional": ["hero", "portfolio", "services", "testimonials", "about", "faq", "bookings"],
}

CATALOG_LABEL_BY_MODEL: dict[str, str] = {
    "product": "Shop our collection",
    "service": "Our services",
    "professional": "Work with us",
}

FONT_PAIR_BY_ARCHETYPE: dict[str, dict[str, str]] = {
    "boutique": {"heading": "Playfair Display", "body": "Plus Jakarta Sans"},
    "market_stall": {"heading": "Plus Jakarta Sans", "body": "Plus Jakarta Sans"},
    "studio": {"heading": "DM Serif Display", "body": "Plus Jakarta Sans"},
    "catalog": {"heading": "Plus Jakarta Sans", "body": "Plus Jakarta Sans"},
    "reel_shop": {"heading": "Plus Jakarta Sans", "body": "Plus Jakarta Sans"},
    "modern_dark": {"heading": "Plus Jakarta Sans", "body": "Inter"},
}

DARK_VISUAL_STYLES = frozenset({"dark_moody", "vibrant"})


def _valid_hex(raw: str) -> str:
    color = str(raw or "").strip()
    if color.startswith("#") and len(color) in (4, 7):
        return color
    if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
        return f"#{color}"
    return ""


def _theme_tokens(profile, user) -> dict[str, str]:
    colors = profile.brand_colors or []
    primary = _valid_hex(colors[0]) if colors else ""
    secondary = _valid_hex(colors[1]) if len(colors) > 1 else ""

    from apps.teams.branding import get_commerce_branding

    branding = get_commerce_branding(user, profile)
    agency_primary = (branding.get("theme_primary_color") or "").strip()
    if agency_primary:
        primary = agency_primary

    if not primary:
        primary = DEFAULT_PRIMARY
    if not secondary:
        secondary = DEFAULT_SECONDARY

    visual = (profile.visual_style or "auto").strip()
    archetype = resolve_archetype(profile)
    surface = "dark" if visual in DARK_VISUAL_STYLES or archetype == "modern_dark" else "light"

    return {
        "primary": primary,
        "secondary": secondary,
        "surface": surface,
    }


def resolve_business_model(profile) -> str:
    bm = (getattr(profile, "business_model", None) or "").strip()
    if bm in ("product", "service", "professional"):
        return bm
    return "product"


def resolve_business_layout(profile) -> dict[str, Any]:
    """Layout hints driven by business_model (service/professional vs product)."""
    bm = resolve_business_model(profile)
    return {
        "business_model": bm,
        "section_order": list(SECTION_ORDER_BY_BUSINESS_MODEL.get(bm, SECTION_ORDER_BY_BUSINESS_MODEL["product"])),
        "catalog_label": CATALOG_LABEL_BY_MODEL.get(bm, CATALOG_LABEL_BY_MODEL["product"]),
        "show_portfolio": bm == "professional",
        "show_bookings_cta": bm in ("service", "professional"),
        "hero_emphasis": "portfolio" if bm == "professional" else ("services" if bm == "service" else "catalog"),
    }


def portfolio_items_for_shop(user, *, limit: int = 6) -> list:
    """Published portfolio / case studies for professional shop pages."""
    from apps.products.models import BusinessAsset

    return list(
        BusinessAsset.objects.filter(
            user=user,
            asset_type__in=[
                BusinessAsset.AssetType.PORTFOLIO,
                BusinessAsset.AssetType.CASE_STUDY,
                BusinessAsset.AssetType.TESTIMONIAL,
            ],
            status=BusinessAsset.Status.PUBLISHED,
        ).order_by("-updated_at")[:limit]
    )


def service_offerings_for_shop(products, *, limit: int = 12) -> list:
    """Service-type products for service-business storefronts."""
    from apps.products.models import Product

    services = [
        p for p in (products or [])
        if getattr(p, "offering_type", None) == Product.OfferingType.SERVICE
    ]
    if services:
        return services[:limit]
    return list(products or [])[:limit]


def resolve_archetype(profile) -> str:
    bm = resolve_business_model(profile)
    if bm == "professional":
        return "studio"
    if bm == "service":
        return "boutique"
    industry = (profile.industry or "").strip()
    if industry in ARCHETYPE_BY_INDUSTRY:
        return ARCHETYPE_BY_INDUSTRY[industry]
    visual = (profile.visual_style or "").strip()
    if visual in DARK_VISUAL_STYLES:
        return "modern_dark"
    return "catalog"


def resolve_vibe(profile) -> str:
    stored = (getattr(profile, "storefront_vibe", None) or "").strip()
    if stored:
        return stored
    industry = (profile.industry or "").strip()
    return VIBE_BY_INDUSTRY.get(industry, "classic_shop")


def resolve_hero_mode(profile, products, shop_reels) -> str:
    """Pick hero treatment from catalog signals (audit-style heuristics)."""
    vibe = resolve_vibe(profile)
    reel_count = len(shop_reels or [])
    featured_count = sum(1 for p in (products or []) if getattr(p, "is_featured", False))

    if vibe == "reels_first" and reel_count >= 1:
        return "reels"
    if reel_count >= 2:
        return "reels"
    if featured_count >= 2 or (vibe in ("magazine", "lookbook") and featured_count >= 1):
        return "featured_carousel"
    headline = (profile.page_headline or "").strip()
    voice = (profile.brand_voice or "").strip()
    if len(headline) >= 40 or len(voice) >= 80:
        return "brand_story"
    if len(products or []) <= 3 or vibe == "minimal_catalog":
        return "compact"
    return "brand_story" if headline or voice else "compact"


def _powered_by_kova(user) -> bool:
    from apps.teams.branding import get_active_brand_for_user

    return get_active_brand_for_user(user) is None


def resolve_storefront(profile, user, products, shop_reels) -> dict[str, Any]:
    """Resolve storefront theme and layout for public shop pages."""
    archetype = resolve_archetype(profile)
    vibe = resolve_vibe(profile)
    hero_mode = resolve_hero_mode(profile, products, shop_reels)
    theme_tokens = _theme_tokens(profile, user)
    surface_mode = theme_tokens["surface"]
    font_pair = FONT_PAIR_BY_ARCHETYPE.get(archetype, FONT_PAIR_BY_ARCHETYPE["catalog"])
    business_layout = resolve_business_layout(profile)
    section_order = business_layout["section_order"]
    if vibe == "minimal_catalog" and business_layout["business_model"] == "product":
        section_order = list(SECTION_ORDER_BY_VIBE.get("minimal_catalog", section_order))

    return {
        "archetype": archetype,
        "vibe": vibe,
        "theme_tokens": theme_tokens,
        "hero_mode": hero_mode,
        "section_order": section_order,
        "surface_mode": surface_mode,
        "font_pair": font_pair,
        "powered_by_kova": _powered_by_kova(user),
        **business_layout,
    }


def storefront_body_classes(storefront: dict[str, Any], *, extra: str = "") -> str:
    """CSS hook classes for shop templates."""
    parts = [
        "shop-site",
        "shop-site--v2",
        f"shop-site--{storefront.get('archetype', 'catalog')}",
        f"shop-site--vibe-{storefront.get('vibe', 'classic_shop')}",
        f"shop-site--surface-{storefront.get('surface_mode', 'light')}",
        f"shop-site--hero-{storefront.get('hero_mode', 'compact')}",
        f"shop-site--model-{storefront.get('business_model', 'product')}",
    ]
    if extra:
        parts.append(extra.strip())
    return " ".join(p for p in parts if p)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def about_blurb(profile) -> str:
    """Short about text — first two sentences of brand voice, else key offerings."""
    voice = (profile.brand_voice or "").strip()
    if voice:
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(voice) if s.strip()]
        if sentences:
            return " ".join(sentences[:2])

    offerings = profile.key_offerings or []
    if offerings:
        labels = [str(o).strip() for o in offerings[:4] if str(o).strip()]
        if labels:
            return f"We offer {', '.join(labels)}."

    headline = (profile.page_headline or "").strip()
    return headline


def shop_faq_items(profile, *, limit: int = 3) -> list[dict[str, str]]:
    """Top FAQ rules formatted for shop footer."""
    items: list[dict[str, str]] = []
    for rule in (profile.wa_faq_answers or [])[:limit]:
        if not isinstance(rule, dict):
            continue
        reply = (rule.get("reply") or "").strip()
        if not reply:
            continue
        keywords = rule.get("keywords") or []
        label = ", ".join(str(k).strip() for k in keywords[:3] if str(k).strip())
        items.append({
            "question": label or "FAQ",
            "answer": reply,
        })
    return items


def shop_footer_data(profile) -> dict[str, str]:
    """Optional footer fields — hours, delivery note, policy URL."""
    raw = getattr(profile, "shop_footer", None) or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "hours": (raw.get("hours") or "").strip(),
        "delivery_note": (raw.get("delivery_note") or "").strip(),
        "policy_url": (raw.get("policy_url") or "").strip(),
    }


def featured_products(products, *, limit: int = 6) -> list:
    """Featured items first; backfill with in-stock products that have photos."""
    featured = [p for p in products if getattr(p, "is_featured", False)]
    if len(featured) >= limit:
        return featured[:limit]

    seen = {p.pk for p in featured}
    for product in products:
        if product.pk in seen:
            continue
        if product.all_image_urls:
            featured.append(product)
            seen.add(product.pk)
        if len(featured) >= limit:
            break
    return featured[:limit]


def hero_promo_products(products, *, limit: int = 6) -> list:
    """Side promo cards for marketplace hero — featured first, then catalog fill."""
    promos = featured_products(products, limit=limit)
    if len(promos) >= limit:
        return promos

    seen = {p.pk for p in promos}
    for product in products:
        if product.pk in seen:
            continue
        promos.append(product)
        seen.add(product.pk)
        if len(promos) >= limit:
            break
    return promos[:limit]


def hero_carousel_slides(
    shop_reels,
    products,
    *,
    featured: list | None = None,
    brand_name: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Build center hero carousel slides from reels, featured images, or brand fallback."""
    slides: list[dict[str, Any]] = []
    featured = featured if featured is not None else featured_products(products)

    for reel in shop_reels or []:
        slides.append({"kind": "reel", "reel": reel})

    seen_slugs: set[str] = set()
    for reel in shop_reels or []:
        seen_slugs.add(reel.get("commerce_slug") or "")

    for product in featured:
        slug = getattr(product, "commerce_slug", "") or ""
        if slug and slug in seen_slugs:
            continue
        image = getattr(product, "shop_hero_image_url", None) or ""
        if not image and getattr(product, "all_image_urls", None):
            image = product.all_image_urls[0]
        if not image:
            continue
        slides.append({
            "kind": "product",
            "product": product,
            "image_url": image,
            "commerce_slug": slug,
            "title": product.name,
            "price": getattr(product, "display_price", "") or "",
        })
        if slug:
            seen_slugs.add(slug)

    if not slides:
        for product in products or []:
            image = getattr(product, "shop_hero_image_url", None) or ""
            if not image and getattr(product, "all_image_urls", None):
                image = product.all_image_urls[0]
            if not image:
                continue
            slides.append({
                "kind": "product",
                "product": product,
                "image_url": image,
                "commerce_slug": getattr(product, "commerce_slug", "") or "",
                "title": product.name,
                "price": getattr(product, "display_price", "") or "",
            })
            if len(slides) >= 3:
                break

    if not slides and brand_name:
        slides.append({"kind": "brand", "title": brand_name})

    return slides[:limit]


def _carousel_commerce_slugs(carousel_slides: list[dict[str, Any]]) -> set[str]:
    slugs: set[str] = set()
    for slide in carousel_slides or []:
        if slide.get("kind") == "reel":
            slugs.add((slide.get("reel") or {}).get("commerce_slug") or "")
        elif slide.get("kind") == "product":
            slugs.add(slide.get("commerce_slug") or "")
    slugs.discard("")
    return slugs


def resolve_hero_layout(
    products: list,
    promos: list,
    carousel_slides: list[dict[str, Any]],
) -> str:
    """
    Pick hero density so small catalogs are not repeated across side promos + carousel.

    Returns: ``spotlight`` | ``carousel`` | ``marketplace``
    """
    count = len(products or [])
    distinct_promos = len({p.pk for p in (promos or [])})
    if count <= 2 and distinct_promos <= 2:
        return "spotlight"
    carousel_slugs = _carousel_commerce_slugs(carousel_slides)
    side_candidates = [
        p for p in (promos or [])
        if (getattr(p, "commerce_slug", "") or "") not in carousel_slugs
    ]
    if count < 6 or len(side_candidates) < 2:
        return "carousel"
    if count < 12:
        return "carousel"
    return "marketplace"


def split_marketplace_hero_promos(
    promos: list,
    carousel_slides: list[dict[str, Any]],
    *,
    per_side: int = 2,
) -> tuple[list, list]:
    """Side promo columns — skip SKUs already featured in the center carousel."""
    carousel_slugs = _carousel_commerce_slugs(carousel_slides)
    available: list = []
    seen_pks: set[int] = set()
    for product in promos or []:
        if product.pk in seen_pks:
            continue
        slug = getattr(product, "commerce_slug", "") or ""
        if slug and slug in carousel_slugs:
            continue
        available.append(product)
        seen_pks.add(product.pk)
    return available[:per_side], available[per_side : per_side * 2]


def catalog_section_label(products_by_category: list[dict[str, Any]]) -> str:
    """Avoid redundant 'Shop our collection' + 'All offers' double headings."""
    if len(products_by_category) == 1:
        name = (products_by_category[0].get("name") or "").strip()
        if name.lower() in {"all offers", "all products"}:
            return "Products"
    return "Shop our collection"


def products_by_category(products) -> list[dict[str, Any]]:
    """Group products by category for shop index sections."""
    groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
    uncategorized: list = []

    for product in products:
        cat = getattr(product, "category", None)
        if cat and getattr(cat, "name", None):
            key = str(cat.pk)
            if key not in groups:
                groups[key] = {"name": cat.name, "products": []}
            groups[key]["products"].append(product)
        else:
            uncategorized.append(product)

    result = list(groups.values())
    if uncategorized:
        result.append({"name": "All offers", "products": uncategorized})
    elif not result:
        result.append({"name": "All offers", "products": list(products)})
    return result


def shop_breadcrumb_items(
    profile,
    user,
    *,
    product=None,
    shop_index_url: str = "",
) -> list[dict[str, str]]:
    """Visual + JSON-LD breadcrumb trail."""
    from apps.products.commerce_seo import brand_name

    brand = brand_name(profile, user)
    items = [{"label": brand, "url": shop_index_url}]
    if product:
        if product.category and product.category.name:
            items.append({"label": product.category.name, "url": ""})
        items.append({"label": product.name, "url": ""})
    return items
