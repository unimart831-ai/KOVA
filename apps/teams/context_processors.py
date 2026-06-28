"""Template context for agency white-label theming."""

from apps.teams.branding import get_active_brand_for_user, get_agency_brands_for_user


def agency_theme(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    from django.core.cache import cache

    session = getattr(request, "session", None)
    active_id = session.get("active_brand_id", "") if session else ""
    cache_key = f"agency_theme:{request.user.pk}:{active_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    brand = get_active_brand_for_user(request.user, session=session)
    agency_brands = get_agency_brands_for_user(request.user)

    ctx = {
        "agency_brands": agency_brands,
        "active_agency_brand_id": str(brand.pk) if brand else "",
        "client_brand_scope": brand.name if brand else "",
    }

    if not brand or not brand.theme_primary_color:
        ctx["agency_brand_theme"] = None
        cache.set(cache_key, ctx, 120)
        return ctx

    logo_url = brand.logo_url or ""
    if not logo_url and brand.logo:
        try:
            logo_url = brand.logo.url
        except Exception:
            logo_url = ""

    ctx["agency_brand_theme"] = {
        "primary_color": brand.theme_primary_color,
        "brand_name": brand.name,
        "logo_url": logo_url,
    }
    cache.set(cache_key, ctx, 120)
    return ctx
