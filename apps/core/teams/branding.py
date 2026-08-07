"""Agency / white-label branding helpers."""

from __future__ import annotations


def get_agency_brands_for_user(user):
    """Brands an agency user can switch between (team owner/admin)."""
    from apps.core.teams.models import Brand, TeamMember

    if not user or not user.is_authenticated:
        return []

    team_ids = TeamMember.objects.filter(
        user=user,
        role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN],
    ).values_list("team_id", flat=True)
    if not team_ids:
        return []

    return list(
        Brand.objects.filter(team_id__in=team_ids, is_active=True).order_by("name")
    )


def _user_can_access_brand(user, brand) -> bool:
    from apps.core.teams.models import TeamMember

    return TeamMember.objects.filter(
        user=user,
        team_id=brand.team_id,
        role__in=[TeamMember.Role.OWNER, TeamMember.Role.ADMIN, TeamMember.Role.CLIENT],
    ).exists()


def get_active_brand_for_user(user, session=None):
    """Primary active Brand with theming for commerce and reports."""
    from apps.core.teams.models import Brand, TeamMember

    if not user or not user.is_authenticated:
        return None

    if session:
        brand_id = session.get("agency_active_brand_id")
        if brand_id:
            brand = Brand.objects.filter(pk=brand_id, is_active=True).first()
            if brand and _user_can_access_brand(user, brand):
                return brand

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
            "primary_color": "#0066FF",
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
        "primary_color": brand.theme_primary_color or "#0066FF",
        "brand_name": brand.name,
        "powered_by_kova": False,
    }


def _profile_accent_color(profile) -> str:
    """First brand color from profile, validated as hex."""
    if not profile:
        return ""
    colors = profile.brand_colors or []
    for raw in colors:
        color = str(raw).strip()
        if color.startswith("#") and len(color) in (4, 7):
            return color
    return ""


def get_commerce_branding(user, profile=None):
    """Theme tokens for public commerce pages (agency brand + profile fallbacks)."""
    brand = get_active_brand_for_user(user)
    primary = "#0066FF"
    logo_url = ""
    custom_domain = ""
    custom_domain_verified = False

    if brand:
        primary = brand.theme_primary_color or primary
        logo_url = brand.logo_url or ""
        if not logo_url and brand.logo:
            try:
                logo_url = brand.logo.url
            except Exception:
                logo_url = ""
        custom_domain = (brand.custom_domain or "").strip()
        custom_domain_verified = brand.custom_domain_verified

    if profile:
        if not logo_url and profile.brand_logo_url:
            logo_url = profile.brand_logo_url.strip()
        profile_accent = _profile_accent_color(profile)
        if profile_accent and (not brand or not brand.theme_primary_color):
            primary = profile_accent

    return {
        "theme_primary_color": primary,
        "logo_url": logo_url,
        "custom_domain": custom_domain,
        "custom_domain_verified": custom_domain_verified,
        "powered_by_kova": brand is None,
    }
