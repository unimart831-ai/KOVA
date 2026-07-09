"""Business Hub — model-adaptive public page assembly.

Instead of one generic layout, the Hub renders the sections that matter for how
a business makes money, in the order that converts best for that model:

  product      → sell products     (bestsellers → catalog → buy)
  service      → book appointments  (book → services → portfolio → times)
  digital      → instant purchase   (featured → catalog → buy now)
  professional → win projects       (portfolio → proof → services → consult)

Every Hub must answer the five questions a visitor arrives with (see
`five_question_contract`). All queries are defensive — a public page must never
500 because one optional model is missing.
"""

from __future__ import annotations

from urllib.parse import quote

# Section order per business model. `hero` and `contact` bookend every layout;
# `salesperson` is injected only when there's inventory/FAQ to ground it.
SECTIONS_BY_MODEL = {
    "product": ["hero", "bestsellers", "salesperson", "catalog", "reviews", "contact"],
    "service": ["hero", "book", "services", "portfolio", "reviews", "salesperson", "contact"],
    "digital": ["hero", "featured", "salesperson", "catalog", "reviews", "contact"],
    "professional": ["hero", "portfolio", "reviews", "services", "salesperson", "contact"],
    "multiple": ["hero", "bestsellers", "services", "salesperson", "reviews", "contact"],
}
DEFAULT_MODEL = "product"


def resolve_business_model(profile, *, has_products: bool, has_booking: bool) -> str:
    """The explicit model wins; otherwise infer from what the business has."""
    bm = (getattr(profile, "business_model", "") or "").strip()
    if bm in SECTIONS_BY_MODEL:
        return bm
    if has_booking and not has_products:
        return "service"
    if has_products:
        return "product"
    return DEFAULT_MODEL


def build_hub_context(profile, user) -> dict:
    """Assemble the full, model-adaptive context for the public Business Hub."""
    from apps.products.commerce_social import resolve_shop_whatsapp

    products = _load_products(user)
    featured = [p for p in products if getattr(p, "is_featured", False)][:6]
    booking_link = _first_active_booking(user)
    portfolio = _load_assets(user, "portfolio")
    case_studies = _load_assets(user, "case_study")
    testimonials = _load_testimonials(user)

    business_model = resolve_business_model(profile, has_products=bool(products), has_booking=bool(booking_link))

    # Services: key_offerings first, then the booking link's service list.
    services = list(getattr(profile, "key_offerings", None) or [])
    if not services and booking_link:
        services = getattr(booking_link, "services", None) or []

    whatsapp = resolve_shop_whatsapp(profile, user)
    business_name = profile.company_name or user.full_name or "your business"
    wa_text = f"Hi, I found {business_name} on Kova and I'm interested. Can you help me?"
    wa_url = f"https://wa.me/{whatsapp}?text={quote(wa_text)}" if whatsapp else ""

    has_salesperson = bool(products or (getattr(profile, "common_questions", None) or []))

    sections = [
        s
        for s in SECTIONS_BY_MODEL.get(business_model, SECTIONS_BY_MODEL[DEFAULT_MODEL])
        if s != "salesperson" or has_salesperson
    ]

    from apps.products.commerce_links import resolve_page_slug
    from apps.products.commerce_seo import brand_name as storefront_brand_name
    from apps.teams.branding import get_commerce_branding

    brand = storefront_brand_name(profile, user)
    shop_slug = resolve_page_slug(profile)
    commerce_branding = get_commerce_branding(user, profile)
    page_title = brand or "Kova Page"
    seo_description = (getattr(profile, "page_headline", "") or "").strip() or f"{page_title} on Kova"

    return {
        "profile": profile,
        "user": user,
        "business_model": business_model,
        "sections": sections,
        "products": products,
        "featured_products": featured or products[:6],
        "booking_link": booking_link,
        "services": services,
        "portfolio": portfolio,
        "case_studies": case_studies,
        "testimonials": testimonials,
        "whatsapp": whatsapp,
        "wa_url": wa_url,
        "has_salesperson": has_salesperson,
        "five_questions": five_question_contract(
            profile,
            user,
            products=products,
            booking_link=booking_link,
            testimonials=testimonials,
            whatsapp=whatsapp,
        ),
        "page_title": page_title,
        "brand_name": brand,
        "shop_slug": shop_slug,
        "commerce_branding": commerce_branding,
        "seo_title": page_title,
        "seo_description": seo_description,
        "powered_by_kova": True,
    }


def five_question_contract(profile, user, *, products, booking_link, testimonials, whatsapp) -> dict:
    """Answer the five questions every visitor arrives with, from the Brain."""
    name = profile.company_name or user.full_name or "This business"
    headline = (getattr(profile, "page_headline", "") or "").strip()
    what = headline or (getattr(profile, "brand_voice", "") or "").strip()[:160]
    if profile.industry and not what:
        try:
            what = f"{name} — {profile.get_industry_display()}"
        except Exception:
            what = name

    trust_bits = []
    if testimonials:
        trust_bits.append(f"{len(testimonials)} happy customer{'s' if len(testimonials) != 1 else ''}")
    if getattr(profile, "founder_story", ""):
        trust_bits.append("founder-led")
    why_trust = ", ".join(trust_bits) or "Real work, real results"

    if booking_link:
        how_to_buy = "Book an appointment or message on WhatsApp"
    elif whatsapp:
        how_to_buy = "Message on WhatsApp — quick replies"
    else:
        how_to_buy = "Send an enquiry below"

    what_after = (getattr(profile, "shop_footer", "") or "").strip()
    if not what_after:
        what_after = (
            "We'll confirm your booking on WhatsApp" if booking_link else "We'll reach out to complete your order"
        )

    return {
        "what": what or name,
        "why_trust": why_trust,
        "whats_best": "Ask our assistant for a recommendation" if products else "Tell us what you need",
        "how_to_buy": how_to_buy,
        "what_after": what_after,
    }


# ── Defensive loaders ───────────────────────────────────────────────────────


def _load_products(user) -> list:
    try:
        from apps.products.models import Product

        return list(Product.objects.filter(user=user, is_active=True).order_by("-is_featured", "-created_at")[:24])
    except Exception:
        return []


def _first_active_booking(user):
    try:
        return user.booking_links.filter(is_active=True).first()
    except Exception:
        return None


def _load_assets(user, asset_type: str) -> list:
    try:
        from apps.products.models import BusinessAsset

        return list(
            BusinessAsset.objects.filter(
                user=user,
                asset_type=asset_type,
                status=BusinessAsset.Status.PUBLISHED,
            )[:8]
        )
    except Exception:
        return []


def _load_testimonials(user) -> list:
    """Positive review responses surfaced as public testimonials."""
    try:
        from apps.reviews.models import Review

        qs = Review.objects.filter(user=user).exclude(response_text="").order_by("-created_at")[:6]
        return [r for r in qs if (r.response_text or "").strip()]
    except Exception:
        return []
