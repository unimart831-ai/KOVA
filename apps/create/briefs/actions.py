"""Shared Daily Brief actions — web UI and WhatsApp reply-to-act."""

from __future__ import annotations

from django.urls import reverse

from apps.create.content.models import ContentSeed
from apps.core.platforms.models import SocialAccount


def asset_type_for_brief_idea(profile) -> str:
    """Map business model to BusinessAsset type for proposal generation."""
    from apps.commerce.products.models import BusinessAsset

    bm = (getattr(profile, "business_model", None) or "").strip()
    if bm == "service":
        return BusinessAsset.AssetType.SERVICE
    if bm == "professional":
        return BusinessAsset.AssetType.PORTFOLIO
    return BusinessAsset.AssetType.OFFER


def ensure_brief_idea_asset(
    user,
    idea: str,
    *,
    context: str = "",
    platform_hint: str = "",
    source: str = "brief",
):
    """Create a BusinessAsset from a brief idea — proposals screen picks the angle."""
    from apps.commerce.products.models import BusinessAsset

    profile = user.profile
    asset_type = asset_type_for_brief_idea(profile)
    wa_source = source in ("whatsapp", "wa")

    return BusinessAsset.objects.create(
        user=user,
        asset_type=asset_type,
        title=(idea or "Brief idea")[:200],
        description=(context or "")[:2000],
        metadata={
            "brief_idea": True,
            "platform_hint": platform_hint,
            "campaign_angle": (idea or "")[:400],
            "source": source,
        },
        status=BusinessAsset.Status.DRAFT,
        source=BusinessAsset.Source.WHATSAPP if wa_source else BusinessAsset.Source.MANUAL,
    )


def proposals_url_for_asset(asset, request=None) -> str:
    path = reverse("content:asset_proposals", kwargs={"asset_id": asset.pk})
    if request:
        return request.build_absolute_uri(path)
    from django.conf import settings

    site = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site}{path}" if site else path


def create_seed_from_brief_idea(
    user,
    idea: str,
    *,
    context: str = "",
    platform_hint: str = "",
    action_type: str = "whatsapp",
) -> ContentSeed:
    """Turn a brief suggestion into a ContentSeed."""
    active_platforms = set(
        SocialAccount.objects.filter(user=user, is_active=True)
        .values_list("platform", flat=True)
    )
    if platform_hint:
        hint_platforms = [p.strip() for p in platform_hint.split(",") if p.strip()]
        target_platforms = [p for p in hint_platforms if p in active_platforms] or list(active_platforms)[:3]
    else:
        target_platforms = list(active_platforms)[:3]

    seed_idea = idea.strip()
    if context:
        seed_idea += f"\n\nContext: {context.strip()}"

    return ContentSeed.objects.create(
        user=user,
        idea=seed_idea,
        notes=f"Created from Daily Brief ({action_type})",
        target_platforms=target_platforms[:3],
    )
