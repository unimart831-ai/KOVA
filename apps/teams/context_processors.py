"""Template context for agency white-label theming."""

from apps.teams.branding import get_active_brand_for_user


def agency_theme(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    brand = get_active_brand_for_user(request.user)
    if not brand or not brand.theme_primary_color:
        return {"agency_brand_theme": None}

    logo_url = brand.logo_url or ""
    if not logo_url and brand.logo:
        try:
            logo_url = brand.logo.url
        except Exception:
            logo_url = ""

    return {
        "agency_brand_theme": {
            "primary_color": brand.theme_primary_color,
            "brand_name": brand.name,
            "logo_url": logo_url,
        },
        "client_brand_scope": brand.name if brand else "",
    }
