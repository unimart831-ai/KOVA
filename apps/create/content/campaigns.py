"""Marketing campaign lifecycle — wraps ContentSeed as the user-facing campaign unit."""

from __future__ import annotations

import logging
import re

from django.utils.text import slugify

logger = logging.getLogger(__name__)


def _slug_base(title: str, user_id) -> str:
    base = slugify(title)[:50] or "campaign"
    return f"{base}-{str(user_id)[:8]}"


def ensure_campaign_for_seed(
    seed,
    *,
    title: str = "",
    objective: str = "sales",
    proposal_meta: dict | None = None,
    business_asset=None,
):
    """
    Create or update MarketingCampaign for a ContentSeed.

    Called when a seed is activated (user picked a proposal or submitted an idea).
    """
    from apps.create.content.models import MarketingCampaign

    existing = getattr(seed, "marketing_campaign", None)
    if existing:
        return existing

    asset = business_asset
    if asset is None and seed.product_id:
        try:
            asset = seed.product.business_asset
        except Exception:
            pass

    display_title = (title or seed.idea or "Marketing campaign").strip().split("\n")[0][:200]
    obj = objective if objective in dict(MarketingCampaign.Objective.choices) else MarketingCampaign.Objective.SALES
    meta = proposal_meta or {}

    from apps.create.content.campaign_archive import default_campaign_expiry

    campaign = MarketingCampaign.objects.create(
        user=seed.user,
        content_seed=seed,
        business_asset=asset,
        title=display_title[:200],
        slug=_slug_base(display_title, seed.user_id),
        objective=obj,
        status=MarketingCampaign.Status.GENERATING,
        proposal_meta=meta,
        expires_at=default_campaign_expiry(objective=obj, proposal_meta=meta),
    )
    from apps.create.content.campaign_pages import ensure_campaign_commerce_url

    ensure_campaign_commerce_url(campaign, save=True)
    logger.info("MarketingCampaign %s created for seed %s", campaign.pk, seed.pk)
    return campaign


def sync_campaign_status_from_seed(seed) -> None:
    """Keep campaign status aligned with seed generation state."""
    from apps.create.content.models import ContentSeed, MarketingCampaign

    campaign = getattr(seed, "marketing_campaign", None)
    if not campaign:
        return

    new_status = campaign.status
    if seed.status == ContentSeed.SeedStatus.PROCESSING:
        new_status = MarketingCampaign.Status.GENERATING
    elif seed.status == ContentSeed.SeedStatus.COMPLETED:
        new_status = MarketingCampaign.Status.REVIEW
    elif seed.status == ContentSeed.SeedStatus.FAILED:
        new_status = MarketingCampaign.Status.FAILED

    if new_status != campaign.status:
        campaign.status = new_status
        campaign.save(update_fields=["status", "updated_at"])


def update_campaign_quality_from_posts(campaign) -> int | None:
    """Recompute campaign QA score and persist dimension breakdown."""
    from apps.create.content.campaign_qa import refresh_campaign_qa

    if not campaign:
        return None
    report = refresh_campaign_qa(campaign, user=campaign.user)
    return report.overall


def campaign_display_label(campaign) -> str:
    """User-facing label with optional quality score."""
    if campaign.quality_score is not None:
        return f"{campaign.title} · {campaign.quality_score}/100"
    return campaign.title
