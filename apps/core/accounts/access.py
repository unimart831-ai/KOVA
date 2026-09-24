"""V1 access helpers — solo owner only (teams/agency removed)."""

from __future__ import annotations


def get_client_membership(user):
    """Agency clients removed in V1 — always None."""
    return None


def get_client_brand_scope(user):
    return None


def get_scoped_post_queryset(user):
    from apps.create.content.models import Post

    if not user or not user.is_authenticated:
        return Post.objects.none()
    return Post.objects.filter(user=user)


def filter_posts_by_brand_scope(qs, user):
    return qs.filter(user=user) if user and user.is_authenticated else qs.none()


def get_teammate_ids(user):
    if not user or not getattr(user, "id", None):
        return set()
    return {user.id}


def can_approve_post(user, post):
    return bool(user and post and post.user_id == user.id)


def can_edit_post(user, post):
    return can_approve_post(user, post)


def request_client_approval(campaign, *, requested_by) -> None:
    """No-op — agency client approval removed in V1."""
    return None


def client_approve_campaign(campaign, user) -> bool:
    """No-op — agency client approval removed in V1."""
    return False


def get_active_brand_for_user(user, session=None):
    """Agency Brand model removed — always None (profile branding used)."""
    return None


def get_agency_brands_for_user(user):
    return []


def get_report_branding(user):
    name = ""
    if user and user.is_authenticated:
        profile = getattr(user, "profile", None)
        name = (getattr(profile, "company_name", None) or "").strip()
        if not name:
            name = (getattr(user, "get_full_name", lambda: "")() or user.email or "").strip()
    return {
        "logo_url": "",
        "primary_color": "#0066FF",
        "brand_name": name,
        "powered_by_kova": True,
    }


def _profile_accent_color(profile) -> str:
    if not profile:
        return ""
    colors = getattr(profile, "brand_colors", None) or []
    for raw in colors:
        color = str(raw).strip()
        if color.startswith("#") and len(color) in (4, 7):
            return color
    return ""


def get_commerce_branding(user, profile=None):
    primary = "#0066FF"
    logo_url = ""
    brand_name = ""

    if profile is None and user and user.is_authenticated:
        profile = getattr(user, "profile", None)

    if profile:
        accent = _profile_accent_color(profile)
        if accent:
            primary = accent
        brand_name = (getattr(profile, "company_name", None) or "").strip()
        logo = getattr(profile, "logo", None) or getattr(profile, "avatar", None)
        if logo:
            try:
                logo_url = logo.url
            except Exception:
                logo_url = ""

    return {
        "primary_color": primary,
        "logo_url": logo_url,
        "brand_name": brand_name,
        "custom_domain": "",
        "custom_domain_verified": False,
        "powered_by_kova": True,
    }
