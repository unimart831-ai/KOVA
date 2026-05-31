"""Agency / white-label branding helpers."""

from __future__ import annotations


def get_active_brand_for_user(user):
    """Primary active Brand with theming for commerce and reports."""
    from apps.teams.models import Brand, TeamMember

    if not user or not user.is_authenticated:
        return None

    client = (
        TeamMember.objects.filter(user=user, role=TeamMember.Role.CLIENT)
        .select_related("brand")
        .first()
    )
    if client and client.brand_id and client.brand.is_active:
        return client.brand

    return (
        Brand.objects.filter(
            team__members__user=user,
            is_active=True,
        )
        .exclude(theme_primary_color="", logo_url="")
        .order_by("name")
        .first()
    )


def get_report_branding(user):
    """Branding context for PDF/HTML client reports."""
    brand = get_active_brand_for_user(user)
    if not brand:
        return {
            "logo_url": "",
            "primary_color": "#4c1d95",
            "brand_name": "",
            "powered_by_kova": True,
        }

    logo_url = brand.logo_url or ""
    if not logo_url and brand.logo:
        try:
            logo_url = brand.logo.url
        except Exception:
            logo_url = ""

    return {
        "logo_url": logo_url,
        "primary_color": brand.theme_primary_color or "#4c1d95",
        "brand_name": brand.name,
        "powered_by_kova": False,
    }


def get_commerce_branding(user):
    """Theme tokens for public commerce pages."""
    brand = get_active_brand_for_user(user)
    if not brand:
        return {}

    primary = brand.theme_primary_color or "#059669"
    logo_url = brand.logo_url or ""
    if not logo_url and brand.logo:
        try:
            logo_url = brand.logo.url
        except Exception:
            logo_url = ""

    custom_domain = (brand.custom_domain or "").strip()
    return {
        "theme_primary_color": primary,
        "logo_url": logo_url,
        "custom_domain": custom_domain,
        "custom_domain_verified": brand.custom_domain_verified,
    }
