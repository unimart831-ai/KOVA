"""Service-business booking setup — link BusinessAsset services to BookingLink."""

from __future__ import annotations

from django.utils.text import slugify

from apps.bookings.models import BookingLink
from apps.products.models import BusinessAsset

DEFAULT_SERVICE_DURATION = 60

_INDUSTRY_FROM_TEMPLATE = {
    "salon": BookingLink.IndustryTemplate.SALON,
    "clinic": BookingLink.IndustryTemplate.CLINIC,
    "fitness": BookingLink.IndustryTemplate.FITNESS,
    "consultant": BookingLink.IndustryTemplate.CONSULTANT,
}


def _unique_slug(base: str) -> str:
    slug = slugify(base)[:36] or "book"
    candidate = slug
    i = 2
    while BookingLink.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{i}"[:40]
        i += 1
    return candidate


def ensure_primary_booking_link(user, *, label: str = "", industry: str = "generic") -> BookingLink:
    """Create or return the owner's primary booking page."""
    existing = BookingLink.objects.filter(user=user, is_active=True).order_by("created_at").first()
    if existing:
        return existing

    profile = getattr(user, "profile", None)
    label = (label or (profile.company_name if profile else "") or "Book with us").strip()[:200]
    slug_base = ""
    if profile and profile.page_slug:
        slug_base = profile.page_slug
    elif user.username:
        slug_base = user.username
    else:
        slug_base = label

    industry_key = (industry or "generic").lower()
    industry_choice = _INDUSTRY_FROM_TEMPLATE.get(industry_key, BookingLink.IndustryTemplate.GENERIC)
    if industry_key in dict(BookingLink.IndustryTemplate.choices):
        industry_choice = industry_key

    link = BookingLink.objects.create(
        user=user,
        slug=_unique_slug(slug_base),
        label=label,
        industry_template=industry_choice,
        services=[],
        owner_whatsapp=(getattr(user, "phone_number", "") or "").strip(),
        owner_email=(user.email or "").strip(),
    )
    link.working_hours = link.default_working_hours()
    link.save(update_fields=["working_hours"])
    return link


def service_entry_from_asset(asset: BusinessAsset) -> dict:
    """Map a service BusinessAsset to a BookingLink services JSON entry."""
    meta = asset.metadata or {}
    duration_raw = meta.get("duration_minutes") or meta.get("duration") or DEFAULT_SERVICE_DURATION
    try:
        duration = int(duration_raw)
    except (TypeError, ValueError):
        duration = DEFAULT_SERVICE_DURATION

    price_raw = meta.get("price_kes") or meta.get("price") or 0
    try:
        price = float(str(price_raw).replace(",", ""))
    except (TypeError, ValueError):
        price = 0.0

    return {
        "name": asset.title[:200],
        "duration_minutes": max(15, duration),
        "price_kes": price,
    }


def sync_service_asset_to_booking_link(user, asset: BusinessAsset) -> BookingLink | None:
    """Add a service asset as a bookable service on the owner's primary link."""
    if asset.asset_type != BusinessAsset.AssetType.SERVICE:
        return None

    link = ensure_primary_booking_link(
        user,
        label=getattr(user.profile, "company_name", "") or link_label_fallback(user),
    )
    services = list(link.services or [])
    entry = service_entry_from_asset(asset)
    existing_names = {s.get("name", "").lower() for s in services}
    if entry["name"].lower() not in existing_names:
        services.append(entry)
        link.services = services
        link.save(update_fields=["services", "updated_at"])
    return link


def sync_product_service_to_booking(user, product) -> BookingLink | None:
    """When a Product is a service offering, sync to booking link via BusinessAsset."""
    from apps.products.business_assets import sync_asset_from_product

    if not product or product.offering_type != product.OfferingType.SERVICE:
        return None
    asset = sync_asset_from_product(product)
    return sync_service_asset_to_booking_link(user, asset)


def link_label_fallback(user) -> str:
    profile = getattr(user, "profile", None)
    if profile and profile.company_name:
        return profile.company_name
    return "Book an appointment"


def booking_public_url(link: BookingLink) -> str:
    from django.conf import settings
    from django.urls import reverse

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    path = reverse("bookings:public_book", kwargs={"slug": link.slug})
    return f"{site}{path}"
