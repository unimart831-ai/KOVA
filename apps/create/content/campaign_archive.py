"""Auto-archive marketing campaigns when offers expire."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# Default offer windows by campaign objective / angle.
_OFFER_ANGLES = frozenset({
    "weekend_offer", "flash", "last_chance", "limited_slots", "book_now",
})
_DEFAULT_EXPIRY_DAYS = {
    "sales": 7,
    "bookings": 14,
    "leads": 14,
    "awareness": 30,
}


def default_campaign_expiry(
    *,
    objective: str = "sales",
    proposal_meta: dict | None = None,
):
    """Compute expires_at for a new campaign."""
    meta = proposal_meta or {}
    if meta.get("expires_at"):
        return meta["expires_at"]

    days = meta.get("offer_expires_days")
    if days is None:
        angle = meta.get("angle") or meta.get("proposal", {}).get("angle") or ""
        intent = meta.get("intent") or meta.get("proposal", {}).get("intent") or ""
        if angle in _OFFER_ANGLES or intent == "offer":
            days = 7
        else:
            days = _DEFAULT_EXPIRY_DAYS.get(objective, 14)

    return timezone.now() + timedelta(days=int(days))


def is_campaign_publicly_live(campaign) -> bool:
    """Whether the campaign page should still be served."""
    from apps.create.content.models import MarketingCampaign

    if not campaign:
        return False
    if campaign.status == MarketingCampaign.Status.ARCHIVED:
        return False
    if campaign.expires_at and campaign.expires_at <= timezone.now():
        return False
    return True


def archive_expired_campaigns(*, batch_size: int = 200) -> dict:
    """Daily task — archive campaigns past expires_at."""
    from apps.create.content.models import MarketingCampaign

    now = timezone.now()
    qs = (
        MarketingCampaign.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        .exclude(status=MarketingCampaign.Status.ARCHIVED)
        .order_by("expires_at")[:batch_size]
    )

    archived = 0
    for campaign in qs:
        campaign.status = MarketingCampaign.Status.ARCHIVED
        campaign.save(update_fields=["status", "updated_at"])
        archived += 1
        logger.info("Archived expired campaign %s (%s)", campaign.pk, campaign.slug)

    return {"archived": archived, "checked_at": now.isoformat()}
